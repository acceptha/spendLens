"""Anthropic 월간 비용 가드레일.

키: llm_budget:{YYYY-MM} (UTC) — 누적 비용 USD.
매월 키 이름 자체가 바뀌므로 별도 reset cron 불필요.
"""
from datetime import UTC, datetime

from app.db import acquire
from app.redis_client import acquire_redis
from app.settings import settings

# Anthropic Claude Haiku 4.5 가격 (per 1M tokens, USD)
HAIKU_INPUT_PRICE_PER_MTOK = 1.0
HAIKU_OUTPUT_PRICE_PER_MTOK = 5.0
HAIKU_MODEL_ID = "claude-haiku-4-5-20251001"


def _bucket_key() -> str:
    return f"llm_budget:{datetime.now(UTC).strftime('%Y-%m')}"


async def current_usage_usd() -> float:
    async with acquire_redis() as r:
        raw = await r.get(_bucket_key())
    return float(raw) if raw else 0.0


async def has_room() -> bool:
    return await current_usage_usd() < settings.anthropic_monthly_budget_usd


def _cost(input_tokens: int, output_tokens: int) -> float:
    return (
        input_tokens * HAIKU_INPUT_PRICE_PER_MTOK / 1_000_000
        + output_tokens * HAIKU_OUTPUT_PRICE_PER_MTOK / 1_000_000
    )


async def record_usage(
    *,
    input_tokens: int,
    output_tokens: int,
    merchant: str,
    model: str = HAIKU_MODEL_ID,
) -> None:
    cost = _cost(input_tokens, output_tokens)
    async with acquire_redis() as r:
        await r.incrbyfloat(_bucket_key(), cost)

    async with acquire() as conn:
        await conn.execute(
            """
            INSERT INTO llm_usage_log
              (model, input_tokens, output_tokens, cost_usd, purpose, merchant_normalized)
            VALUES ($1, $2, $3, $4, 'categorize', $5)
            """,
            model, input_tokens, output_tokens, cost, merchant,
        )
