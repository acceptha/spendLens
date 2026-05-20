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
    email = f"_w3-cat-{uuid4()}@example.com"
    r = await ac.post("/auth/signup", json={"email": email, "password": "abcd1234"})
    return r.json()["access_token"], email


async def _seed(conn, email, *, txn_date, amount, category, override=None):
    user = await conn.fetchrow("SELECT id FROM users WHERE email = $1", email)
    await conn.execute(
        """
        INSERT INTO transactions (
          user_id, source_type, txn_date, amount, merchant_raw,
          category, user_category_override, dedup_hash, raw_row
        ) VALUES ($1, 'test', $2, $3, 'M', $4, $5, $6, '{}'::jsonb)
        """,
        user["id"], datetime.date.fromisoformat(txn_date), amount,
        category, override, str(uuid4()),
    )


async def test_by_category_groups_correctly(test_db_pool):
    async with await _client() as ac:
        token, email = await _signup_and_token(ac)
        async with test_db_pool.acquire() as conn:
            await _seed(conn, email, txn_date="2026-05-01", amount=5000, category="coffee")
            await _seed(conn, email, txn_date="2026-05-02", amount=3000, category="coffee")
            await _seed(conn, email, txn_date="2026-05-03", amount=10000, category="groceries")

        r = await ac.get(
            "/dashboard/by-category?month=2026-05",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body[0]["category"] == "groceries"
        assert float(body[0]["amount"]) == 10000
        assert body[0]["count"] == 1
        assert body[1]["category"] == "coffee"
        assert float(body[1]["amount"]) == 8000
        assert body[1]["count"] == 2


async def test_by_category_uses_effective_override(test_db_pool):
    async with await _client() as ac:
        token, email = await _signup_and_token(ac)
        async with test_db_pool.acquire() as conn:
            # auto=unknown, override=groceries → effective=groceries
            await _seed(conn, email, txn_date="2026-05-01", amount=5000,
                        category="unknown", override="groceries")
            await _seed(conn, email, txn_date="2026-05-02", amount=3000,
                        category="groceries")

        r = await ac.get(
            "/dashboard/by-category?month=2026-05",
            headers={"Authorization": f"Bearer {token}"},
        )
        body = r.json()
        assert len(body) == 1
        assert body[0]["category"] == "groceries"
        assert float(body[0]["amount"]) == 8000
        assert body[0]["count"] == 2


async def test_by_category_empty(test_db_pool):
    async with await _client() as ac:
        token, _ = await _signup_and_token(ac)
        r = await ac.get(
            "/dashboard/by-category?month=2026-05",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.json() == []
