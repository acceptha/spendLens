from app.categorization.budget import (
    HAIKU_INPUT_PRICE_PER_MTOK,
    HAIKU_OUTPUT_PRICE_PER_MTOK,
    current_usage_usd,
    has_room,
    record_usage,
)


async def test_initial_state_no_usage_room_available():
    assert await current_usage_usd() == 0.0
    assert await has_room() is True


async def test_record_usage_increments_counter():
    await record_usage(input_tokens=1000, output_tokens=500, merchant="test_merchant")
    expected = (
        1000 * HAIKU_INPUT_PRICE_PER_MTOK / 1_000_000
        + 500 * HAIKU_OUTPUT_PRICE_PER_MTOK / 1_000_000
    )
    assert abs(await current_usage_usd() - expected) < 1e-9


async def test_has_room_false_when_budget_exhausted(monkeypatch):
    from app.settings import settings
    monkeypatch.setattr(settings, "anthropic_monthly_budget_usd", 0.000001)

    # large usage that will exceed the tiny budget
    await record_usage(input_tokens=10_000, output_tokens=5_000, merchant="x")
    assert await has_room() is False


async def test_record_usage_writes_to_llm_usage_log(test_db_pool):
    await record_usage(input_tokens=100, output_tokens=50, merchant="test_log_merchant")
    async with test_db_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT model, input_tokens, output_tokens, purpose, merchant_normalized "
            "FROM llm_usage_log WHERE merchant_normalized = $1",
            "test_log_merchant",
        )
    assert len(rows) == 1
    assert rows[0]["input_tokens"] == 100
    assert rows[0]["output_tokens"] == 50
    assert rows[0]["purpose"] == "categorize"


async def test_record_usage_logs_purpose(test_db_pool):
    from app.categorization import budget
    await budget.record_usage(
        input_tokens=100, output_tokens=20, merchant="x", purpose="insight"
    )
    async with test_db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT purpose FROM llm_usage_log ORDER BY id DESC LIMIT 1"
        )
    assert row["purpose"] == "insight"
