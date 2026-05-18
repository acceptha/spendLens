import pytest

from app.categorization.cache import get, normalize_merchant
from app.categorization.cache import set as cache_set


@pytest.mark.parametrize(
    "raw,normalized",
    [
        ("스타벅스 강남점", "스타벅스강남"),
        ("(주)이디야커피", "이디야커피"),
        ("이마트 성수1호점", "이마트성수"),
        ("STARBUCKS COFFEE  ", "starbucks coffee"),
    ],
)
def test_normalize_strips_suffixes_and_whitespace(raw, normalized):
    assert normalize_merchant(raw) == normalized


async def test_cache_miss_returns_none():
    result = await get("never_set_merchant")
    assert result is None


async def test_cache_set_then_get_roundtrip():
    await cache_set("스타벅스 강남점", "coffee")
    result = await get("스타벅스 강남점")
    assert result == "coffee"


async def test_cache_key_normalized_so_different_writes_collapse():
    await cache_set("(주)스타벅스 강남점", "coffee")
    # 다른 표기지만 정규화 후 동일 키
    result = await get("스타벅스 강남점 ")
    assert result == "coffee"
