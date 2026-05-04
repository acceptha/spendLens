from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import jwt as pyjwt

from app.settings import settings

_ALGORITHM = "HS256"


def _access_ttl() -> timedelta:
    return timedelta(minutes=settings.jwt_access_ttl_minutes)


def _refresh_ttl() -> timedelta:
    return timedelta(days=settings.jwt_refresh_ttl_days)


def create_access_token(user_id: UUID) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + _access_ttl()).timestamp()),
    }
    return pyjwt.encode(payload, settings.jwt_secret, algorithm=_ALGORITHM)


def create_refresh_token(user_id: UUID) -> tuple[str, UUID]:
    jti = uuid4()
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "jti": str(jti),
        "type": "refresh",
        "iat": int(now.timestamp()),
        "exp": int((now + _refresh_ttl()).timestamp()),
    }
    return pyjwt.encode(payload, settings.jwt_secret, algorithm=_ALGORITHM), jti


def decode_token(token: str) -> dict[str, Any]:
    return pyjwt.decode(token, settings.jwt_secret, algorithms=[_ALGORITHM])
