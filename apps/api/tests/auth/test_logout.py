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
async def test_logout_revokes_refresh(test_db_pool, seeded_user):
    from app.main import app
    email, pwd = seeded_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://test") as client:
        login_resp = await client.post("/auth/login", json={"email": email, "password": pwd})
        cookies = login_resp.cookies

        logout_resp = await client.post("/auth/logout", cookies=cookies)
        assert logout_resp.status_code == 204

        refresh_resp = await client.post("/auth/refresh", cookies=cookies)
        assert refresh_resp.status_code == 401

    async with test_db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT revoked_at FROM refresh_tokens")
    assert len(rows) == 1
    assert rows[0]["revoked_at"] is not None
