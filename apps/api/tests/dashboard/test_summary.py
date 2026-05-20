import datetime
from uuid import uuid4

import httpx
from httpx import ASGITransport

from app.main import app


async def _client():
    return httpx.AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    )


async def _signup_and_token(ac):
    email = f"_w3-dash-{uuid4()}@example.com"
    r = await ac.post("/auth/signup", json={"email": email, "password": "abcd1234"})
    return r.json()["access_token"], email


async def _seed(conn, email, *, txn_date, amount):
    user = await conn.fetchrow("SELECT id FROM users WHERE email = $1", email)
    await conn.execute(
        """
        INSERT INTO transactions (
          user_id, source_type, txn_date, amount, merchant_raw,
          category, dedup_hash, raw_row
        ) VALUES ($1, 'test', $2, $3, 'M', 'unknown', $4, '{}'::jsonb)
        """,
        user["id"], datetime.date.fromisoformat(txn_date), amount, str(uuid4()),
    )


async def test_summary_basic(test_db_pool):
    async with await _client() as ac:
        token, email = await _signup_and_token(ac)
        async with test_db_pool.acquire() as conn:
            await _seed(conn, email, txn_date="2026-05-01", amount=10000)
            await _seed(conn, email, txn_date="2026-05-15", amount=20000)
            await _seed(conn, email, txn_date="2026-04-20", amount=15000)

        r = await ac.get(
            "/dashboard/summary?month=2026-05",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["month"] == "2026-05"
        assert float(body["total_amount"]) == 30000
        assert body["transaction_count"] == 2
        assert body["prev_month"] == "2026-04"
        assert float(body["prev_month_total"]) == 15000
        assert body["prev_month_diff_pct"] == 100.0


async def test_summary_no_prev_month_returns_null_diff(test_db_pool):
    async with await _client() as ac:
        token, email = await _signup_and_token(ac)
        async with test_db_pool.acquire() as conn:
            await _seed(conn, email, txn_date="2026-05-01", amount=10000)

        r = await ac.get(
            "/dashboard/summary?month=2026-05",
            headers={"Authorization": f"Bearer {token}"},
        )
        body = r.json()
        assert body["prev_month_diff_pct"] is None


async def test_summary_excludes_negative_amount(test_db_pool):
    """입금(amount < 0)은 출금 집계에서 제외."""
    async with await _client() as ac:
        token, email = await _signup_and_token(ac)
        async with test_db_pool.acquire() as conn:
            await _seed(conn, email, txn_date="2026-05-01", amount=10000)
            await _seed(conn, email, txn_date="2026-05-02", amount=-50000)

        r = await ac.get(
            "/dashboard/summary?month=2026-05",
            headers={"Authorization": f"Bearer {token}"},
        )
        body = r.json()
        assert float(body["total_amount"]) == 10000
        assert body["transaction_count"] == 1


async def test_summary_invalid_month_400(test_db_pool):
    async with await _client() as ac:
        token, _ = await _signup_and_token(ac)
        r = await ac.get(
            "/dashboard/summary?month=05-2026",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 400
