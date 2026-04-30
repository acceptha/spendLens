import os
import asyncio
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


@pytest.fixture(autouse=True)
async def reset_tables(test_db_pool):
    """각 테스트 전 모든 테이블을 비움. CASCADE로 의존성 해결."""
    async with test_db_pool.acquire() as conn:
        await conn.execute("""
            TRUNCATE transactions, source_files, refresh_tokens, users
            RESTART IDENTITY CASCADE;
        """)
    yield
