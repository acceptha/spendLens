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
    email = f"_w3-top-{uuid4()}@example.com"
    r = await ac.post("/auth/signup", json={"email": email, "password": "abcd1234"})
    return r.json()["access_token"], email


async def _seed(conn, email, *, merchant, amount, txn_date="2026-05-15"):
    user = await conn.fetchrow("SELECT id FROM users WHERE email = $1", email)
    await conn.execute(
        """
        INSERT INTO transactions (
          user_id, source_type, txn_date, amount, merchant_raw,
          category, dedup_hash, raw_row
        ) VALUES ($1, 'test', $2, $3, $4, 'unknown', $5, '{}'::jsonb)
        """,
        user["id"], datetime.date.fromisoformat(txn_date), amount, merchant, str(uuid4()),
    )


async def test_top_merchants_groups_and_sums(test_db_pool):
    async with await _client() as ac:
        token, email = await _signup_and_token(ac)
        async with test_db_pool.acquire() as conn:
            await _seed(conn, email, merchant="홈플러스", amount=50000)
            await _seed(conn, email, merchant="홈플러스", amount=30000)
            await _seed(conn, email, merchant="스타벅스", amount=5000)
            await _seed(conn, email, merchant="이마트", amount=20000)

        r = await ac.get(
            "/dashboard/top-merchants?month=2026-05&limit=5",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body[0]["merchant_raw"] == "홈플러스"
        assert float(body[0]["amount"]) == 80000
        assert body[0]["count"] == 2
        assert [b["merchant_raw"] for b in body] == ["홈플러스", "이마트", "스타벅스"]


async def test_top_merchants_limit_applied(test_db_pool):
    async with await _client() as ac:
        token, email = await _signup_and_token(ac)
        async with test_db_pool.acquire() as conn:
            for i in range(10):
                await _seed(conn, email, merchant=f"M{i}", amount=1000 + i)

        r = await ac.get(
            "/dashboard/top-merchants?month=2026-05&limit=3",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert len(r.json()) == 3


async def test_top_merchants_default_limit_5(test_db_pool):
    async with await _client() as ac:
        token, email = await _signup_and_token(ac)
        async with test_db_pool.acquire() as conn:
            for i in range(10):
                await _seed(conn, email, merchant=f"M{i}", amount=1000 + i)

        r = await ac.get(
            "/dashboard/top-merchants?month=2026-05",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert len(r.json()) == 5
