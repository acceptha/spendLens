from app.categorization import cache
from app.categorization.service import classify


async def test_rulebook_hit_returns_without_cache_or_llm():
    result = await classify("스타벅스 강남점")
    assert result == "coffee"


async def test_rulebook_miss_cache_miss_returns_unknown():
    # Phase 4에서는 LLM이 아직 없으므로 unknown (Phase 5에서 LLM 호출로 변경)
    result = await classify("듣도보도 못한 가맹점 ABC")
    assert result == "unknown"


async def test_rulebook_miss_cache_hit_returns_cached():
    await cache.set("이상한가맹점XYZ", "shopping")
    result = await classify("이상한가맹점XYZ")
    assert result == "shopping"


async def test_budget_exhausted_short_circuits_to_unknown(monkeypatch):
    from app.settings import settings
    monkeypatch.setattr(settings, "anthropic_monthly_budget_usd", 0.0)
    result = await classify("새로운가맹점123")
    assert result == "unknown"
