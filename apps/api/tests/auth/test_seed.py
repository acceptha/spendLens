import pytest
from app.auth.seed import ensure_admin_user
from app.settings import settings


@pytest.mark.asyncio
async def test_seed_creates_user_when_missing(test_db_pool):
    async with test_db_pool.acquire() as conn:
        await ensure_admin_user(conn)
        row = await conn.fetchrow("SELECT email FROM users WHERE email = $1", settings.admin_email)
    assert row is not None
    assert row["email"] == settings.admin_email


@pytest.mark.asyncio
async def test_seed_is_idempotent(test_db_pool):
    async with test_db_pool.acquire() as conn:
        await ensure_admin_user(conn)
        await ensure_admin_user(conn)
        count = await conn.fetchval("SELECT COUNT(*) FROM users WHERE email = $1", settings.admin_email)
    assert count == 1
