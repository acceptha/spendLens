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
    email = f"_w3-patch-{uuid4()}@example.com"
    r = await ac.post(
        "/auth/signup",
        json={"email": email, "password": "abcd1234"},
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"], email


async def _create_txn(conn, email):
    user_row = await conn.fetchrow(
        "SELECT id FROM users WHERE email = $1", email
    )
    user_id = user_row["id"]
    txn_row = await conn.fetchrow(
        """
        INSERT INTO transactions (
          user_id, source_type, txn_date, amount, merchant_raw,
          category, dedup_hash, raw_row
        ) VALUES (
          $1, 'test', CURRENT_DATE, 1000, 'TEST',
          'unknown', $2, '{}'::jsonb
        ) RETURNING id
        """,
        user_id, str(uuid4()),
    )
    return txn_row["id"]


async def test_patch_updates_category(test_db_pool):
    async with await _client() as ac:
        token, email = await _signup_and_token(ac)
        async with test_db_pool.acquire() as conn:
            txn_id = await _create_txn(conn, email)

        r = await ac.patch(
            f"/transactions/{txn_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"category": "groceries"},
        )
        assert r.status_code == 204, r.text

        # DB 직접 확인 — override 컬럼만 갱신, category(자동) 그대로
        async with test_db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT category, user_category_override FROM transactions WHERE id = $1",
                txn_id,
            )
        assert row["category"] == "unknown"
        assert row["user_category_override"] == "groceries"

        # HTTP layer 확인 — GET /transactions 응답의 effective_category가 override 값
        get_r = await ac.get(
            "/transactions",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert get_r.status_code == 200
        rows = [t for t in get_r.json() if t["id"] == str(txn_id)]
        assert len(rows) == 1
        assert rows[0]["auto_category"] == "unknown"
        assert rows[0]["user_category_override"] == "groceries"
        assert rows[0]["effective_category"] == "groceries"


async def test_patch_rejects_invalid_category(test_db_pool):
    async with await _client() as ac:
        token, email = await _signup_and_token(ac)
        async with test_db_pool.acquire() as conn:
            txn_id = await _create_txn(conn, email)

        r = await ac.patch(
            f"/transactions/{txn_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"category": "not_a_real_category"},
        )
    assert r.status_code == 422


async def test_patch_404_for_other_user_txn(test_db_pool):
    async with await _client() as ac:
        # user A 가입 + 거래 생성
        token_a, email_a = await _signup_and_token(ac)
        async with test_db_pool.acquire() as conn:
            txn_id = await _create_txn(conn, email_a)

        # user B 가입 (다른 IP가 아니므로 rate limit 주의 — 1시간 내 5회 한도)
        token_b, _ = await _signup_and_token(ac)

        # user B 토큰으로 user A의 거래 PATCH 시도
        r = await ac.patch(
            f"/transactions/{txn_id}",
            headers={"Authorization": f"Bearer {token_b}"},
            json={"category": "coffee"},
        )
    assert r.status_code == 404
    assert r.json()["detail"] == "NOT_FOUND"


async def test_patch_404_for_unknown_id(test_db_pool):
    async with await _client() as ac:
        token, _ = await _signup_and_token(ac)
        r = await ac.patch(
            f"/transactions/{uuid4()}",
            headers={"Authorization": f"Bearer {token}"},
            json={"category": "coffee"},
        )
    assert r.status_code == 404
