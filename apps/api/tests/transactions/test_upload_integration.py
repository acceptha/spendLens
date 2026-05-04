from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.password import hash_password
from app.auth.seed import ensure_admin_user
from app.settings import settings

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "samsung-card-fixture.xlsx"


@pytest.fixture
async def auth_headers(test_db_pool, monkeypatch):
    pwd_hash = hash_password("hunter2")
    monkeypatch.setattr(settings, "admin_password_hash", pwd_hash)
    async with test_db_pool.acquire() as conn:
        await conn.execute("DELETE FROM users")
        await ensure_admin_user(conn)
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://test") as client:
        login = await client.post("/auth/login",
                                  json={"email": settings.admin_email, "password": "hunter2"})
        token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}, app


@pytest.mark.asyncio
async def test_upload_then_list(auth_headers):
    headers, app = auth_headers
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://test") as client:
        with FIXTURE.open("rb") as f:
            files = {"file": ("samsung-card-fixture.xlsx", f.read(),
                              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
            up = await client.post("/transactions/upload", headers=headers, files=files)
        assert up.status_code == 200
        body = up.json()
        assert body["uploaded"] >= 6
        assert body["skipped"] == 0

        lst = await client.get("/transactions", headers=headers)
        assert lst.status_code == 200
        assert len(lst.json()) >= 6


@pytest.mark.asyncio
async def test_upload_idempotent_on_second_run(auth_headers):
    headers, app = auth_headers
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://test") as client:
        with FIXTURE.open("rb") as f:
            data = f.read()
        files1 = {"file": ("samsung-card-fixture.xlsx", data,
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        first = await client.post("/transactions/upload", headers=headers, files=files1)
        assert first.json()["uploaded"] >= 6

        files2 = {"file": ("samsung-card-fixture.xlsx", data,
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        second = await client.post("/transactions/upload", headers=headers, files=files2)
        assert second.json()["uploaded"] == 0
        assert second.json()["skipped"] >= 6
