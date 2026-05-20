from datetime import date, timedelta
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
    email = f"_w3-bym-{uuid4()}@example.com"
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
        user["id"], txn_date, amount, str(uuid4()),
    )


async def test_by_month_returns_last_n_months(test_db_pool):
    today = date.today()
    # 이번 달 1일과 지난달 1일 — 명시적 월 산술 (timedelta(70)로 인한 월경계 fragility 회피)
    this_month_first = today.replace(day=1)
    last_month_first = (this_month_first - timedelta(days=1)).replace(day=1)

    async with await _client() as ac:
        token, email = await _signup_and_token(ac)
        async with test_db_pool.acquire() as conn:
            await _seed(conn, email, txn_date=this_month_first, amount=10000)
            await _seed(conn, email, txn_date=last_month_first, amount=5000)

        r = await ac.get(
            "/dashboard/by-month?last_n=6",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        body = r.json()
        assert len(body) == 2
        months = [b["month"] for b in body]
        assert months == sorted(months)  # ORDER BY month ASC


async def test_by_month_excludes_deposits(test_db_pool):
    today = date.today()
    async with await _client() as ac:
        token, email = await _signup_and_token(ac)
        async with test_db_pool.acquire() as conn:
            await _seed(conn, email, txn_date=today.replace(day=1), amount=10000)
            await _seed(conn, email, txn_date=today.replace(day=2), amount=-50000)

        r = await ac.get(
            "/dashboard/by-month?last_n=3",
            headers={"Authorization": f"Bearer {token}"},
        )
        body = r.json()
        assert len(body) == 1
        assert float(body[0]["amount"]) == 10000


async def test_by_month_invalid_last_n_400(test_db_pool):
    async with await _client() as ac:
        token, _ = await _signup_and_token(ac)
        r = await ac.get(
            "/dashboard/by-month?last_n=999",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 400
