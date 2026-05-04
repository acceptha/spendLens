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
async def test_refresh_rotates_jti(test_db_pool, seeded_user):
    from app.main import app
    email, pwd = seeded_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://test") as client:
        login_resp = await client.post("/auth/login", json={"email": email, "password": pwd})
        assert login_resp.status_code == 200
        cookies1 = login_resp.cookies

        refresh_resp = await client.post("/auth/refresh", cookies=cookies1)
        assert refresh_resp.status_code == 200
        assert "access_token" in refresh_resp.json()
        assert "refresh_token" in refresh_resp.cookies

    async with test_db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT jti, revoked_at FROM refresh_tokens ORDER BY expires_at")
    assert len(rows) == 2
    assert rows[0]["revoked_at"] is not None
    assert rows[1]["revoked_at"] is None


@pytest.mark.asyncio
async def test_refresh_without_cookie_returns_401(seeded_user):
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://test") as client:
        resp = await client.post("/auth/refresh")
    assert resp.status_code == 401
