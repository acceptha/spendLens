import asyncio
import os
from pathlib import Path

import asyncpg
import pytest


def _load_test_env() -> None:
    env_file = Path(__file__).parent / ".env.test"
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


_load_test_env()


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_db_pool():
    """세션 단위 DB 풀. 로컬 docker-compose의 postgres-test 컨테이너 또는 CI services 사용."""
    pool = await asyncpg.create_pool(os.environ["DATABASE_URL"], min_size=1, max_size=5)
    yield pool
    await pool.close()


@pytest.fixture(scope="session", autouse=True)
async def _init_app_pool(test_db_pool):
    """Make app.db._pool point at test_db_pool so route handlers can use acquire()."""
    import app.db
    app.db._pool = test_db_pool
    yield
    app.db._pool = None


@pytest.fixture(autouse=True)
async def reset_tables(test_db_pool):
    """각 테스트 전 모든 테이블을 비움. CASCADE로 의존성 해결."""
    async with test_db_pool.acquire() as conn:
        await conn.execute("""
            TRUNCATE monthly_insights, llm_usage_log, transactions,
                     source_files, refresh_tokens, users
            RESTART IDENTITY CASCADE;
        """)
    yield


@pytest.fixture(scope="session", autouse=True)
async def _init_app_redis():
    """Initialize redis pool for all tests."""
    from app.redis_client import close_redis, init_redis
    await init_redis()
    yield
    await close_redis()


@pytest.fixture(autouse=True)
async def reset_redis():
    """각 테스트 전 test DB(index 15)를 비움."""
    from app.redis_client import acquire_redis, init_redis
    await init_redis()  # idempotent; re-initializes if a lifecycle test closed the pool
    async with acquire_redis() as r:
        await r.flushdb()
    yield
