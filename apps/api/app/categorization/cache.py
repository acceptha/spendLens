"""전역 카테고리 캐시 (Redis).

키: `category:v1:{normalized_merchant_name}` — 모든 사용자 공유.
값: 카테고리 enum 문자열. TTL 없음 (영구). LLM 호출 결과 보존이 목적.
"""
import re

from app.redis_client import acquire_redis

_KEY_PREFIX = "category:v1:"

_SUFFIX_PATTERNS = [
    re.compile(r"\(주\)|㈜|주식회사"),
    re.compile(r"\d+호점"),
    re.compile(r"점\s*$"),
]


def _is_cjk(s: str) -> bool:
    return any("가" <= ch <= "힣" for ch in s)


def normalize_merchant(raw: str) -> str:
    """가맹점명 정규화 — 공통 표기 차이를 흡수해 캐시 hit rate 상승."""
    text = raw.strip()
    if not _is_cjk(text):
        text = text.lower()
    for pat in _SUFFIX_PATTERNS:
        text = pat.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()
    # 한글이 포함된 경우 공백 제거 (영문은 공백 유지)
    if _is_cjk(text):
        text = text.replace(" ", "")
    return text


async def get(merchant_raw: str) -> str | None:
    key = _KEY_PREFIX + normalize_merchant(merchant_raw)
    async with acquire_redis() as r:
        return await r.get(key)


async def set(merchant_raw: str, category: str) -> None:  # noqa: A001
    key = _KEY_PREFIX + normalize_merchant(merchant_raw)
    async with acquire_redis() as r:
        await r.set(key, category)
