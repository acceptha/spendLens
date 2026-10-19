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
    email = f"_del-{uuid4()}@example.com"
    r = await ac.post("/auth/signup", json={"email": email, "password": "abcd1234"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"], email


async def _create_txn(conn, email):
    user_id = await conn.fetchval("SELECT id FROM users WHERE email = $1", email)
    return await conn.fetchval(
        """
        INSERT INTO transactions (
          user_id, source_type, txn_date, amount, merchant_raw,
          category, dedup_hash, raw_row
        ) VALUES ($1, 'test', CURRENT_DATE, 1000, 'TEST', 'unknown', $2, '{}'::jsonb)
        RETURNING id
        """,
        user_id, str(uuid4()),
    )


async def test_delete_transaction_removes_row(test_db_pool):
    async with await _client() as ac:
        token, email = await _signup_and_token(ac)
        async with test_db_pool.acquire() as conn:
            txn_id = await _create_txn(conn, email)

        r = await ac.delete(
            f"/transactions/{txn_id}", headers={"Authorization": f"Bearer {token}"}
        )
        assert r.status_code == 204, r.text

        async with test_db_pool.acquire() as conn:
            assert await conn.fetchval(
                "SELECT count(*) FROM transactions WHERE id = $1", txn_id
            ) == 0


async def test_delete_transaction_of_other_user_404(test_db_pool):
    async with await _client() as ac:
        _, owner_email = await _signup_and_token(ac)
        other_token, _ = await _signup_and_token(ac)
        async with test_db_pool.acquire() as conn:
            txn_id = await _create_txn(conn, owner_email)

        r = await ac.delete(
            f"/transactions/{txn_id}", headers={"Authorization": f"Bearer {other_token}"}
        )
        assert r.status_code == 404
        assert r.json()["detail"] == "NOT_FOUND"

        async with test_db_pool.acquire() as conn:
            assert await conn.fetchval(
                "SELECT count(*) FROM transactions WHERE id = $1", txn_id
            ) == 1


async def test_delete_transaction_requires_auth(test_db_pool):
    async with await _client() as ac:
        r = await ac.delete(f"/transactions/{uuid4()}")
        assert r.status_code == 401
