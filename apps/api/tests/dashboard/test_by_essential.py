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
        "INSERT INTO transactions (user_id, source_type, txn_date, amount, merchant_raw, "
        "category, essential_override, dedup_hash, raw_row) "
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


async def test_by_essential_excludes_transfer_and_savings(test_db_pool):
    async with await _client() as ac:
        token, email = await _signup(ac)
        async with test_db_pool.acquire() as conn:
            await _ins(conn, email, amount=10000, category="housing")    # 필수, 포함
            await _ins(conn, email, amount=50000, category="transfer")   # 제외(성격 불명)
            await _ins(conn, email, amount=30000, category="savings")    # 제외(비소비)

        r = await ac.get("/dashboard/by-essential?month=2026-05",
                         headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200, r.text
        buckets = {b["essential"]: b for b in r.json()}
        # transfer/savings 제외 → 필수 housing 10000만, 비필수 버킷 없음
        assert float(buckets[True]["amount"]) == 10000
        assert buckets[True]["count"] == 1
        assert False not in buckets


async def test_by_essential_includes_transfer_reclassified_to_spending(test_db_pool):
    """사용자가 이체를 실제 지출 카테고리로 재분류하면 다시 집계에 포함(effective 기준)."""
    async with await _client() as ac:
        token, email = await _signup(ac)
        async with test_db_pool.acquire() as conn:
            u = await conn.fetchrow("SELECT id FROM users WHERE email=$1", email)
            # category=transfer 이지만 사용자가 coffee(비필수)로 재분류
            await conn.execute(
                "INSERT INTO transactions (user_id, source_type, txn_date, amount, "
                "merchant_raw, category, user_category_override, dedup_hash, raw_row) "
                "VALUES ($1,'test','2026-05-10',8000,'M','transfer','coffee',$2,'{}'::jsonb)",
                u["id"], str(uuid4()))

        r = await ac.get("/dashboard/by-essential?month=2026-05",
                         headers={"Authorization": f"Bearer {token}"})
        buckets = {b["essential"]: b for b in r.json()}
        # effective=coffee(비필수) → 포함
        assert float(buckets[False]["amount"]) == 8000
        assert True not in buckets


async def test_by_essential_invalid_month_400(test_db_pool):
    async with await _client() as ac:
        token, _ = await _signup(ac)
        r = await ac.get("/dashboard/by-essential?month=bad",
                         headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 400
