from uuid import UUID

import jwt as pyjwt
from fastapi import Header, HTTPException

from app.auth.jwt import decode_token


async def current_user_id(authorization: str | None = Header(default=None)) -> UUID:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="MISSING_BEARER")
    token = authorization[7:]
    try:
        payload = decode_token(token)
    except pyjwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=401, detail="TOKEN_EXPIRED") from exc
    except pyjwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail="INVALID_TOKEN") from exc

    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="WRONG_TOKEN_TYPE")
    return UUID(payload["sub"])
