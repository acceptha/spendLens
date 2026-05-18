import pytest
from fastapi import HTTPException

from app.common.rate_limit import check


async def test_under_limit_passes():
    for _ in range(5):
        await check("test_ep", "1.2.3.4", max_attempts=5, window_seconds=3600)


async def test_over_limit_raises_429():
    for _ in range(5):
        await check("test_ep", "1.2.3.4", max_attempts=5, window_seconds=3600)
    with pytest.raises(HTTPException) as exc:
        await check("test_ep", "1.2.3.4", max_attempts=5, window_seconds=3600)
    assert exc.value.status_code == 429
    assert exc.value.detail == "TOO_MANY_REQUESTS"
    assert "Retry-After" in exc.value.headers


async def test_different_ips_independent():
    for _ in range(5):
        await check("test_ep", "1.2.3.4", max_attempts=5, window_seconds=3600)
    await check("test_ep", "5.6.7.8", max_attempts=5, window_seconds=3600)


async def test_different_endpoints_independent():
    for _ in range(5):
        await check("ep_a", "1.2.3.4", max_attempts=5, window_seconds=3600)
    await check("ep_b", "1.2.3.4", max_attempts=5, window_seconds=3600)
