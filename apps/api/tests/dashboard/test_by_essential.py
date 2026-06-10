from uuid import uuid4

import httpx
from httpx import ASGITransport

from app.main import app


async def _client():
    return httpx.AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    )


async def _signup(ac):
    email = f"_w4-be-{uuid4()}@example.com"
    r = await ac.post("/auth/signup", json={"email": email, "password": "abcd1234"})
    return r.json()["access_token"], email


async def _ins(conn, email, *, amount, category, override=None):
    u = await conn.fetchrow("SELECT id FROM users WHERE email=$1", email)
    await conn.execute(
        "INSERT INTO transactions (user_id, source_type, txn_date, amount, merchant_raw, category, essential_override, dedup_hash, raw_row) "
        "VALUES ($1,'test','2026-05-10',$2,'M',$3,$4,$5,'{}'::jsonb)",
        u["id"], amount, category, override, str(uuid4()))


async def test_by_essential_default_and_override(test_db_pool):
    async with await _client() as ac:
        token, email = await _signup(ac)
        async with test_db_pool.acquire() as conn:
            await _ins(conn, email, amount=10000, category="housing")             # 기본 필수
            await _ins(conn, email, amount=5000, category="coffee")               # 기본 비필수
            await _ins(conn, email, amount=3000, category="coffee", override=True) # 오버라이드→필수

        r = await ac.get("/dashboard/by-essential?month=2026-05",
                         headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200, r.text
        buckets = {b["essential"]: b for b in r.json()}
        assert float(buckets[True]["amount"]) == 13000   # housing + override coffee
        assert buckets[True]["count"] == 2
        assert float(buckets[False]["amount"]) == 5000    # 기본 coffee


async def test_by_essential_invalid_month_400(test_db_pool):
    async with await _client() as ac:
        token, _ = await _signup(ac)
        r = await ac.get("/dashboard/by-essential?month=bad",
                         headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 400
