"""IP-based fixed-window rate limit via Redis.

Key format: ratelimit:{endpoint}:{ip}:{YYYYMMDDHH}
TTL: window_seconds (e.g. 3600 for hourly).
"""
from datetime import UTC, datetime

from fastapi import HTTPException

from app.redis_client import acquire_redis


async def check(
    endpoint: str,
    ip: str,
    *,
    max_attempts: int,
    window_seconds: int,
) -> None:
    """Increment counter; raise 429 if over limit.

    카운터는 진입 시점에 증가 (성공/실패 무관) — brute-force 시도 자체 차단.
    """
    bucket = datetime.now(UTC).strftime("%Y%m%d%H")
    key = f"ratelimit:{endpoint}:{ip}:{bucket}"

    async with acquire_redis() as r:
        count = await r.incr(key)
        if count == 1:
            await r.expire(key, window_seconds)
        if count > max_attempts:
            ttl = await r.ttl(key)
            raise HTTPException(
                status_code=429,
                detail="TOO_MANY_REQUESTS",
                headers={"Retry-After": str(max(ttl, 1))},
            )
