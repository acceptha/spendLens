"""같은 가맹점 일괄 변경 — PATCH가 대상 건수를 알려주고, apply-to-merchant가 일괄 적용."""
import datetime
from uuid import uuid4

import httpx
from httpx import ASGITransport

from app.categorization.merchant import normalize_merchant
from app.main import app


async def _client():
    return httpx.AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    )


async def _signup(ac):
    email = f"_atm-{uuid4()}@example.com"
    r = await ac.post("/auth/signup", json={"email": email, "password": "abcd1234"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}, email


async def _txn(pool, email, merchant, category="coffee", override=None, d="2026-10-01"):
    async with pool.acquire() as conn:
        uid = await conn.fetchval("SELECT id FROM users WHERE email=$1", email)
        return await conn.fetchval(
            "INSERT INTO transactions (user_id, source_type, txn_date, amount, merchant_raw, "
            "merchant_normalized, category, user_category_override, dedup_hash, raw_row) "
            "VALUES ($1,'test',$2,1000,$3,$4,$5,$6,$7,'{}'::jsonb) RETURNING id",
            uid, datetime.date.fromisoformat(d), merchant, normalize_merchant(merchant),
            category, override, str(uuid4()))


async def _effective(pool, txn_id):
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT COALESCE(user_category_override, category) FROM transactions WHERE id=$1",
            txn_id)


async def test_patch_reports_same_merchant_candidates(test_db_pool):
    async with await _client() as ac:
        h, email = await _signup(ac)
        target = await _txn(test_db_pool, email, "스타벅스 강남점")
        await _txn(test_db_pool, email, "스타벅스 역삼점")                     # 대상
        await _txn(test_db_pool, email, "스타벅스 선릉점", d="2026-09-03")     # 대상(다른 달)
        await _txn(test_db_pool, email, "스타벅스 판교점", override="lunch")   # 직접 고침 → 제외
        # 이미 같은 카테고리 → 제외
        await _txn(test_db_pool, email, "스타벅스 서초점", category="snack_late")
        await _txn(test_db_pool, email, "이디야 강남점")                       # 다른 가맹점

        r = await ac.patch(f"/transactions/{target}", headers=h, json={"category": "snack_late"})
        assert r.status_code == 200, r.text
        assert r.json() == {"same_merchant_pending": 2, "merchant": "스타벅스"}


async def test_apply_to_merchant_updates_only_candidates(test_db_pool):
    async with await _client() as ac:
        h, email = await _signup(ac)
        target = await _txn(test_db_pool, email, "스타벅스 강남점")
        a = await _txn(test_db_pool, email, "스타벅스 역삼점")
        manual = await _txn(test_db_pool, email, "스타벅스 판교점", override="lunch")
        other = await _txn(test_db_pool, email, "이디야 강남점")
        await ac.patch(f"/transactions/{target}", headers=h, json={"category": "snack_late"})

        r = await ac.post(f"/transactions/{target}/apply-to-merchant", headers=h)
        assert r.status_code == 200, r.text
        assert r.json() == {"updated": 1}
        assert await _effective(test_db_pool, a) == "snack_late"
        assert await _effective(test_db_pool, manual) == "lunch"
        assert await _effective(test_db_pool, other) == "coffee"

        # 다시 PATCH하면 남은 대상 0건
        r = await ac.patch(f"/transactions/{target}", headers=h, json={"category": "snack_late"})
        assert r.json()["same_merchant_pending"] == 0


async def test_apply_to_merchant_is_per_user(test_db_pool):
    async with await _client() as ac:
        h1, e1 = await _signup(ac)
        _, e2 = await _signup(ac)
        target = await _txn(test_db_pool, e1, "스타벅스 강남점")
        theirs = await _txn(test_db_pool, e2, "스타벅스 역삼점")
        await ac.patch(f"/transactions/{target}", headers=h1, json={"category": "snack_late"})
        r = await ac.post(f"/transactions/{target}/apply-to-merchant", headers=h1)
        assert r.json() == {"updated": 0}
        assert await _effective(test_db_pool, theirs) == "coffee"


async def test_apply_to_merchant_404_for_other_users_txn(test_db_pool):
    async with await _client() as ac:
        _, e1 = await _signup(ac)
        h2, _ = await _signup(ac)
        target = await _txn(test_db_pool, e1, "스타벅스 강남점")
        r = await ac.post(f"/transactions/{target}/apply-to-merchant", headers=h2)
        assert r.status_code == 404
        assert r.json()["detail"] == "NOT_FOUND"
