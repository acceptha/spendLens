from datetime import timedelta
from uuid import uuid4

import jwt as pyjwt
import pytest

from app.auth.jwt import create_access_token, create_refresh_token, decode_token


def test_create_access_token_contains_sub_and_type():
    user_id = uuid4()
    token = create_access_token(user_id)
    payload = decode_token(token)
    assert payload["sub"] == str(user_id)
    assert payload["type"] == "access"


def test_create_refresh_token_contains_jti():
    user_id = uuid4()
    token, jti = create_refresh_token(user_id)
    payload = decode_token(token)
    assert payload["sub"] == str(user_id)
    assert payload["type"] == "refresh"
    assert payload["jti"] == str(jti)


def test_decode_invalid_signature_raises():
    user_id = uuid4()
    token = create_access_token(user_id)
    tampered = token[:-3] + "AAA"
    with pytest.raises(pyjwt.InvalidTokenError):
        decode_token(tampered)


def test_decode_expired_raises(monkeypatch):
    user_id = uuid4()
    monkeypatch.setattr("app.auth.jwt._access_ttl", lambda: timedelta(seconds=-10))
    token = create_access_token(user_id)
    with pytest.raises(pyjwt.ExpiredSignatureError):
        decode_token(token)
