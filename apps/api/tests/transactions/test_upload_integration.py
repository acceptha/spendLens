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
        rows = lst.json()
        assert len(rows) >= 6
        # 업로드 시 merchant_normalized가 채워진다(정규화 엔진 배선 확인)
        assert all(t.get("merchant_normalized") for t in rows)
        starbucks = [t for t in rows if "스타벅스" in t["merchant_raw"]]
        assert starbucks and starbucks[0]["merchant_normalized"] == "스타벅스"


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


@pytest.mark.asyncio
async def test_upload_xls_then_xlsx_dedups(auth_headers):
    from tests.parsers.test_xls import xlsx_to_xls

    headers, app = auth_headers
    data = FIXTURE.read_bytes()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://test") as client:
        up = await client.post(
            "/transactions/upload", headers=headers,
            files={"file": ("statement.xls", xlsx_to_xls(data), "application/vnd.ms-excel")},
        )
        assert up.status_code == 200, up.text
        assert up.json()["uploaded"] >= 6

        # 같은 명세서를 .xlsx로 다시 올리면 전부 중복으로 스킵된다(dedup 해시 동일).
        again = await client.post(
            "/transactions/upload", headers=headers,
            files={"file": ("statement.xlsx", data,
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        assert again.json()["uploaded"] == 0
        assert again.json()["skipped"] == up.json()["uploaded"]


async def _seed_override(test_db_pool, email, merchant_raw, override, *, d="2026-01-01"):
    import datetime
    from uuid import uuid4

    from app.categorization.merchant import normalize_merchant

    async with test_db_pool.acquire() as conn:
        uid = await conn.fetchval("SELECT id FROM users WHERE email = $1", email)
        await conn.execute(
            "INSERT INTO transactions (user_id, source_type, txn_date, amount, merchant_raw, "
            "merchant_normalized, category, user_category_override, dedup_hash, raw_row) "
            "VALUES ($1,'test',$2,1000,$3,$4,'coffee',$5,$6,'{}'::jsonb)",
            uid, datetime.date.fromisoformat(d), merchant_raw,
            normalize_merchant(merchant_raw), override, str(uuid4()),
        )


@pytest.mark.asyncio
async def test_upload_learns_category_from_users_past_override(auth_headers, test_db_pool):
    headers, app = auth_headers
    # 다른 지점이라도 같은 브랜드(정규화)면 학습 적용, 가장 최근 수정이 우선.
    await _seed_override(test_db_pool, settings.admin_email, "스타벅스 역삼점", "dinner",
                         d="2026-01-01")
    await _seed_override(test_db_pool, settings.admin_email, "스타벅스 선릉점", "snack_late",
                         d="2026-02-01")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://test") as client:
        up = await client.post(
            "/transactions/upload", headers=headers,
            files={"file": ("s.xlsx", FIXTURE.read_bytes(),
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        assert up.status_code == 200, up.text
        rows = (await client.get("/transactions?limit=200", headers=headers)).json()

    uploaded = [t for t in rows if t["merchant_raw"] == "스타벅스 강남대로점"]
    assert uploaded, "fixture should contain 스타벅스 강남대로점"
    assert uploaded[0]["auto_category"] == "snack_late"
    assert uploaded[0]["user_category_override"] is None  # 학습은 자동 분류로 들어간다


@pytest.mark.asyncio
async def test_upload_ignores_other_users_overrides(auth_headers, test_db_pool):
    headers, app = auth_headers
    async with test_db_pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO users (email, password_hash) VALUES ('_other@example.com', 'x')"
        )
    await _seed_override(test_db_pool, "_other@example.com", "스타벅스 역삼점", "dinner")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://test") as client:
        await client.post(
            "/transactions/upload", headers=headers,
            files={"file": ("s.xlsx", FIXTURE.read_bytes(),
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        rows = (await client.get("/transactions?limit=200", headers=headers)).json()

    starbucks = [t for t in rows if t["merchant_raw"] == "스타벅스 강남대로점"]
    assert starbucks[0]["auto_category"] == "coffee"
