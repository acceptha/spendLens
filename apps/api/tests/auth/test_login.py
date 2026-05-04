import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.password import hash_password
from app.auth.seed import ensure_admin_user
from app.settings import settings


@pytest.fixture
async def seeded_user(test_db_pool, monkeypatch):
    pwd_hash = hash_password("hunter2")
    monkeypatch.setattr(settings, "admin_password_hash", pwd_hash)
    async with test_db_pool.acquire() as conn:
        await conn.execute("DELETE FROM users")
        await ensure_admin_user(conn)
    return settings.admin_email, "hunter2"


@pytest.mark.asyncio
async def test_login_success(seeded_user):
    from app.main import app
    email, pwd = seeded_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/auth/login", json={"email": email, "password": pwd})
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert body["token_type"] == "Bearer"
    assert "refresh_token" in resp.cookies


@pytest.mark.asyncio
async def test_login_wrong_password(seeded_user):
    from app.main import app
    email, _ = seeded_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/auth/login", json={"email": email, "password": "wrong"})
    assert resp.status_code == 401
