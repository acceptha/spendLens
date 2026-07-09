from app.categorization.cache import get
from app.categorization.cache import set as cache_set

# 가맹점명 정규화 로직 자체의 검증은 tests/categorization/test_merchant.py 로 이동.
# 여기서는 Redis 캐시 동작(get/set/정규화 키 공유)만 검증한다.


async def test_cache_miss_returns_none():
    result = await get("never_set_merchant")
    assert result is None


async def test_cache_set_then_get_roundtrip():
    await cache_set("스타벅스 강남점", "coffee")
    result = await get("스타벅스 강남점")
    assert result == "coffee"


async def test_cache_key_normalized_so_different_writes_collapse():
    await cache_set("(주)스타벅스 강남점", "coffee")
    # 다른 표기지만 정규화 후 동일 키(둘 다 '스타벅스')
    result = await get("스타벅스 강남점 ")
    assert result == "coffee"
