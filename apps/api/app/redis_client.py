"""Async Redis pool. Same lifecycle pattern as app.db.

Provides:
- init_redis() / close_redis(): called from FastAPI lifespan
- acquire_redis(): async context manager yielding a redis.asyncio.Redis client
"""
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import redis.asyncio as aioredis

from app.settings import settings

_pool: aioredis.Redis | None = None


async def init_redis() -> None:
    global _pool
    if _pool is not None:
        return
    _pool = aioredis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
        max_connections=20,
    )


async def close_redis() -> None:
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None


@asynccontextmanager
async def acquire_redis() -> AsyncIterator[aioredis.Redis]:
    if _pool is None:
        raise RuntimeError("redis pool not initialized")
    yield _pool
