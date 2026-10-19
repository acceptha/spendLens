"""거래가 바뀌면 그 달의 캐시된 인사이트는 무효화돼야 한다 (DB 트리거, migration 0006)."""
import datetime
from uuid import uuid4

import pytest


@pytest.fixture
async def user_id(test_db_pool):
    async with test_db_pool.acquire() as conn:
        return await conn.fetchval(
            "INSERT INTO users (email, password_hash) VALUES ($1, 'x') RETURNING id",
            f"_inv-{uuid4()}@example.com",
        )


async def _insert_txn(conn, user_id, d="2026-05-03", amount=1000):
    return await conn.fetchval(
        "INSERT INTO transactions (user_id, source_type, txn_date, amount, merchant_raw, "
        "category, dedup_hash, raw_row) VALUES ($1,'test',$2,$3,'M','etc',$4,'{}'::jsonb) "
        "RETURNING id",
        user_id, datetime.date.fromisoformat(d), amount, str(uuid4()),
    )


async def _cache(conn, user_id, month):
    await conn.execute(
        "INSERT INTO monthly_insights (user_id, month, payload) VALUES ($1, $2, '{}'::jsonb)",
        user_id, month,
    )


async def _cached_months(conn, user_id):
    rows = await conn.fetch(
        "SELECT month FROM monthly_insights WHERE user_id = $1 ORDER BY month", user_id
    )
    return [r["month"] for r in rows]


async def test_insert_invalidates_only_that_month(test_db_pool, user_id):
    async with test_db_pool.acquire() as conn:
        await _cache(conn, user_id, "2026-04")
        await _cache(conn, user_id, "2026-05")
        await _insert_txn(conn, user_id, d="2026-05-10")
        assert await _cached_months(conn, user_id) == ["2026-04"]


async def test_delete_invalidates(test_db_pool, user_id):
    async with test_db_pool.acquire() as conn:
        txn = await _insert_txn(conn, user_id)
        await _cache(conn, user_id, "2026-05")
        await conn.execute("DELETE FROM transactions WHERE id = $1", txn)
        assert await _cached_months(conn, user_id) == []


async def test_category_override_invalidates(test_db_pool, user_id):
    async with test_db_pool.acquire() as conn:
        txn = await _insert_txn(conn, user_id)
        await _cache(conn, user_id, "2026-05")
        await conn.execute(
            "UPDATE transactions SET user_category_override = 'coffee' WHERE id = $1", txn
        )
        assert await _cached_months(conn, user_id) == []


async def test_essential_override_invalidates(test_db_pool, user_id):
    async with test_db_pool.acquire() as conn:
        txn = await _insert_txn(conn, user_id)
        await _cache(conn, user_id, "2026-05")
        await conn.execute(
            "UPDATE transactions SET essential_override = true WHERE id = $1", txn
        )
        assert await _cached_months(conn, user_id) == []


async def test_other_users_cache_untouched(test_db_pool, user_id):
    async with test_db_pool.acquire() as conn:
        other = await conn.fetchval(
            "INSERT INTO users (email, password_hash) VALUES ($1, 'x') RETURNING id",
            f"_inv-{uuid4()}@example.com",
        )
        await _cache(conn, other, "2026-05")
        await _insert_txn(conn, user_id)
        assert await _cached_months(conn, other) == ["2026-05"]
