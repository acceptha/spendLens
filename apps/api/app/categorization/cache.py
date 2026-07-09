"""전역 카테고리 캐시 (Redis).

키: `category:v1:{normalized_merchant_name}` — 모든 사용자 공유.
값: 카테고리 enum 문자열. TTL 없음 (영구). LLM 호출 결과 보존이 목적.

정규화는 `categorization.merchant.normalize_merchant`(별칭 테이블 + 휴리스틱)에
위임한다 — 같은 브랜드의 다른 지점이 하나의 캐시 키를 공유해 hit rate가 오른다.
"""
from app.categorization.merchant import normalize_merchant
from app.redis_client import acquire_redis

_KEY_PREFIX = "category:v1:"

__all__ = ["normalize_merchant", "get", "set"]


async def get(merchant_raw: str) -> str | None:
    key = _KEY_PREFIX + normalize_merchant(merchant_raw)
    async with acquire_redis() as r:
        return await r.get(key)


async def set(merchant_raw: str, category: str) -> None:  # noqa: A001
    key = _KEY_PREFIX + normalize_merchant(merchant_raw)
    async with acquire_redis() as r:
        await r.set(key, category)
