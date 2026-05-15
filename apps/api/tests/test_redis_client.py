import pytest

from app.redis_client import acquire_redis, close_redis, init_redis


async def test_redis_set_get_roundtrip():
    """Pool lifecycle: init → use → close. Standalone, doesn't rely on conftest auto-init."""
    await init_redis()
    try:
        async with acquire_redis() as r:
            await r.set("test:roundtrip", "hello")
            value = await r.get("test:roundtrip")
        assert value == "hello"
    finally:
        await close_redis()


async def test_acquire_redis_raises_when_pool_not_initialized():
    # conftest auto-initializes pool — close it for this test
    await close_redis()
    try:
        with pytest.raises(RuntimeError, match="redis pool not initialized"):
            async with acquire_redis() as _:
                pass
    finally:
        # restore for subsequent tests
        await init_redis()
