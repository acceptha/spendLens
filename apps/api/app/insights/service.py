"""월간 인사이트 오케스트레이터.

흐름: 캐시 조회 → (force or miss) 예산 체크 → 집계 수집 → LLM → 캐시 UPSERT.
캐시는 monthly_insights(user_id, month) PK. payload는 jsonb.
"""
import json
from uuid import UUID

import asyncpg

from app.categorization import budget
from app.dashboard import service as dash
from app.insights import llm


class BudgetExceeded(Exception):
    """월간 LLM 예산 초과 — 라우터에서 503."""


async def get_cached(conn: asyncpg.Connection, user_id: UUID, month: str) -> dict | None:
    row = await conn.fetchrow(
        "SELECT payload, generated_at FROM monthly_insights WHERE user_id = $1 AND month = $2",
        user_id, month,
    )
    if row is None:
        return None
    payload = row["payload"]
    if isinstance(payload, str):
        payload = json.loads(payload)
    return {
        "month": month,
        "summary": payload["summary"],
        "highlights": payload["highlights"],
        "generated_at": row["generated_at"],
    }


async def _collect_aggregates(conn: asyncpg.Connection, user_id: UUID, month: str) -> dict:
    summary = await dash.summary(conn, user_id, month)
    by_category = await dash.by_category(conn, user_id, month)
    top_merchants = await dash.top_merchants(conn, user_id, month, limit=5)
    by_essential = await dash.by_essential(conn, user_id, month)
    return {
        "month": month,
        "summary": summary,
        "by_category": by_category,
        "top_merchants": top_merchants,
        "by_essential": by_essential,
    }


async def generate(
    conn: asyncpg.Connection, user_id: UUID, month: str, *, force: bool
) -> dict:
    dash.validate_month(month)  # raises ValueError → 라우터 400
    if not force:
        cached = await get_cached(conn, user_id, month)
        if cached is not None:
            return cached

    if not await budget.has_room():
        raise BudgetExceeded()

    aggregates = await _collect_aggregates(conn, user_id, month)
    result, usage = await llm.generate_insight(aggregates)  # InsightError → 라우터 502

    payload = {"summary": result["summary"], "highlights": result["highlights"]}
    row = await conn.fetchrow(
        """
        INSERT INTO monthly_insights (user_id, month, payload)
        VALUES ($1, $2, $3::jsonb)
        ON CONFLICT (user_id, month)
        DO UPDATE SET payload = EXCLUDED.payload, generated_at = now()
        RETURNING generated_at
        """,
        user_id, month, json.dumps(payload, ensure_ascii=False),
    )
    await budget.record_usage(
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        merchant=f"insight:{month}",
        purpose="insight",
    )
    return {
        "month": month,
        "summary": payload["summary"],
        "highlights": payload["highlights"],
        "generated_at": row["generated_at"],
    }
