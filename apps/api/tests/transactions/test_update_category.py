from uuid import uuid4

from app.transactions.service import update_category


async def _insert_user(conn):
    row = await conn.fetchrow(
        "INSERT INTO users (email, password_hash) VALUES ($1, $2) RETURNING id",
        f"u-{uuid4()}@e.com",
        "$argon2id$v=19$m=65536,t=3,p=4$placeholder",
    )
    return row["id"]


async def _insert_txn(conn, user_id, category="unknown"):
    row = await conn.fetchrow(
        """
        INSERT INTO transactions (
          user_id, source_type, txn_date, amount, merchant_raw,
          category, dedup_hash, raw_row
        ) VALUES (
          $1, 'test', CURRENT_DATE, 1000, 'TEST MERCHANT',
          $2, $3, '{}'::jsonb
        ) RETURNING id
        """,
        user_id, category, str(uuid4()),
    )
    return row["id"]


async def test_update_category_sets_override(test_db_pool):
    async with test_db_pool.acquire() as conn:
        user_id = await _insert_user(conn)
        txn_id = await _insert_txn(conn, user_id)

        updated = await update_category(conn, user_id, txn_id, "groceries")
    assert updated is True

    async with test_db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT category, user_category_override FROM transactions WHERE id = $1",
            txn_id,
        )
    assert row["category"] == "unknown"  # auto는 보존
    assert row["user_category_override"] == "groceries"


async def test_update_category_returns_false_for_other_user(test_db_pool):
    async with test_db_pool.acquire() as conn:
        user_a = await _insert_user(conn)
        user_b = await _insert_user(conn)
        txn_id = await _insert_txn(conn, user_a)

        updated = await update_category(conn, user_b, txn_id, "groceries")
    assert updated is False


async def test_update_category_returns_false_for_missing_id(test_db_pool):
    async with test_db_pool.acquire() as conn:
        user_id = await _insert_user(conn)
        updated = await update_category(conn, user_id, uuid4(), "groceries")
    assert updated is False
