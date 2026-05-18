from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt as pyjwt
from asyncpg.exceptions import UniqueViolationError
from fastapi import APIRouter, Cookie, HTTPException, Request, Response, status

from app.auth.jwt import create_access_token, create_refresh_token, decode_token
from app.auth.password import (
    PasswordPolicyError,
    hash_password,
    validate_password_policy,
    verify_password,
)
from app.auth.schemas import (
    LoginRequest,
    LoginResponse,
    RefreshResponse,
    SignupRequest,
    SignupResponse,
)
from app.common import rate_limit
from app.db import acquire
from app.settings import settings

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest, request: Request, response: Response) -> LoginResponse:
    await rate_limit.check(
        "login", request.client.host, max_attempts=5, window_seconds=3600
    )
    async with acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, password_hash FROM users WHERE email = $1", req.email
        )
        if row is None or not verify_password(row["password_hash"], req.password):
            raise HTTPException(status_code=401, detail="INVALID_CREDENTIALS")

        user_id = row["id"]
        access = create_access_token(user_id)
        refresh, jti = create_refresh_token(user_id)
        expires_at = datetime.now(UTC) + timedelta(days=settings.jwt_refresh_ttl_days)

        await conn.execute(
            "INSERT INTO refresh_tokens (jti, user_id, expires_at) VALUES ($1, $2, $3)",
            jti, user_id, expires_at,
        )

    response.set_cookie(
        key="refresh_token",
        value=refresh,
        max_age=settings.jwt_refresh_ttl_days * 86400,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/auth",
    )
    return LoginResponse(access_token=access)


@router.post("/refresh", response_model=RefreshResponse)
async def refresh(
    response: Response, refresh_token: str | None = Cookie(default=None)
) -> RefreshResponse:
    if not refresh_token:
        raise HTTPException(status_code=401, detail="MISSING_REFRESH")

    try:
        payload = decode_token(refresh_token)
    except pyjwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=401, detail="TOKEN_EXPIRED") from exc
    except pyjwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="INVALID_TOKEN") from exc

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="WRONG_TOKEN_TYPE")

    user_id = UUID(payload["sub"])
    jti = UUID(payload["jti"])

    async with acquire() as conn:
        row = await conn.fetchrow(
            "SELECT revoked_at FROM refresh_tokens WHERE jti = $1", jti
        )
        if row is None or row["revoked_at"] is not None:
            raise HTTPException(status_code=401, detail="TOKEN_REVOKED")

        await conn.execute(
            "UPDATE refresh_tokens SET revoked_at = now() WHERE jti = $1", jti
        )

        new_access = create_access_token(user_id)
        new_refresh, new_jti = create_refresh_token(user_id)
        expires_at = datetime.now(UTC) + timedelta(days=settings.jwt_refresh_ttl_days)

        await conn.execute(
            "INSERT INTO refresh_tokens (jti, user_id, expires_at) VALUES ($1, $2, $3)",
            new_jti, user_id, expires_at,
        )

    response.set_cookie(
        key="refresh_token",
        value=new_refresh,
        max_age=settings.jwt_refresh_ttl_days * 86400,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/auth",
    )
    return RefreshResponse(access_token=new_access)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response, refresh_token: str | None = Cookie(default=None)) -> None:
    if refresh_token:
        try:
            payload = decode_token(refresh_token)
            jti = UUID(payload["jti"])
            async with acquire() as conn:
                await conn.execute(
                    "UPDATE refresh_tokens"
                    " SET revoked_at = now() WHERE jti = $1 AND revoked_at IS NULL",
                    jti,
                )
        except (pyjwt.InvalidTokenError, KeyError, ValueError):
            pass
    response.delete_cookie("refresh_token", path="/auth")


@router.post("/signup", response_model=SignupResponse)
async def signup(
    req: SignupRequest, request: Request, response: Response
) -> SignupResponse:
    await rate_limit.check(
        "signup", request.client.host, max_attempts=5, window_seconds=3600
    )

    try:
        validate_password_policy(req.password)
    except PasswordPolicyError as exc:
        raise HTTPException(status_code=400, detail="WEAK_PASSWORD") from exc

    pwd_hash = hash_password(req.password)

    async with acquire() as conn:
        try:
            row = await conn.fetchrow(
                "INSERT INTO users (email, password_hash) VALUES ($1, $2) RETURNING id",
                req.email,
                pwd_hash,
            )
        except UniqueViolationError as exc:
            raise HTTPException(status_code=409, detail="EMAIL_ALREADY_EXISTS") from exc

        user_id = row["id"]
        access = create_access_token(user_id)
        refresh, jti = create_refresh_token(user_id)
        expires_at = datetime.now(UTC) + timedelta(days=settings.jwt_refresh_ttl_days)

        await conn.execute(
            "INSERT INTO refresh_tokens (jti, user_id, expires_at) VALUES ($1, $2, $3)",
            jti, user_id, expires_at,
        )

    response.set_cookie(
        key="refresh_token",
        value=refresh,
        max_age=settings.jwt_refresh_ttl_days * 86400,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/auth",
    )
    return SignupResponse(access_token=access)
