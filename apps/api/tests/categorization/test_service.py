from unittest.mock import AsyncMock, MagicMock

from app.categorization import cache
from app.categorization.service import classify


async def test_rulebook_hit_returns_without_cache_or_llm():
    result = await classify("스타벅스 강남점")
    assert result == "coffee"


async def test_rulebook_miss_cache_hit_returns_cached():
    await cache.set("이상한가맹점XYZ", "shopping")
    result = await classify("이상한가맹점XYZ")
    assert result == "shopping"


async def test_budget_exhausted_short_circuits_to_unknown(monkeypatch):
    from app.settings import settings
    monkeypatch.setattr(settings, "anthropic_monthly_budget_usd", 0.0)
    result = await classify("새로운가맹점123")
    assert result == "unknown"


def _patch_llm(monkeypatch, category: str = "shopping"):
    """Inject a fake Anthropic client into llm._client."""
    fake_msg = MagicMock()
    fake_msg.content = [MagicMock(text=f'{{"category": "{category}"}}')]
    fake_msg.usage = MagicMock(input_tokens=100, output_tokens=5)
    fake_client = MagicMock()
    fake_client.messages = MagicMock()
    fake_client.messages.create = AsyncMock(return_value=fake_msg)
    monkeypatch.setattr("app.categorization.llm._client", lambda: fake_client)
    return fake_client


async def test_rulebook_miss_calls_llm_and_caches(monkeypatch):
    fake = _patch_llm(monkeypatch, category="shopping")

    result = await classify("미지의가맹점XYZ")
    assert result == "shopping"
    assert fake.messages.create.await_count == 1

    # 두 번째 호출은 캐시 hit → LLM 추가 호출 없음
    result2 = await classify("미지의가맹점XYZ")
    assert result2 == "shopping"
    assert fake.messages.create.await_count == 1


async def test_llm_failure_returns_unknown_silently(monkeypatch):
    fake = _patch_llm(monkeypatch)
    fake.messages.create.side_effect = RuntimeError("api down")

    result = await classify("새로운가맹점123")
    assert result == "unknown"


async def test_llm_records_usage_to_budget(monkeypatch, test_db_pool):
    _patch_llm(monkeypatch, category="shopping")
    await classify("기록되는가맹점")

    async with test_db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT input_tokens, output_tokens, purpose FROM llm_usage_log"
        )
    assert len(rows) == 1
    assert rows[0]["input_tokens"] == 100
    assert rows[0]["output_tokens"] == 5
    assert rows[0]["purpose"] == "categorize"
