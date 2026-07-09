"""Dashboard aggregate queries — raw SQL on transactions.

모든 집계는 amount > 0 (출금) 기준. 입금/소득은 W4 이후 분석.
effective_category = COALESCE(user_category_override, category).
"""
import re
from decimal import Decimal
from uuid import UUID

import asyncpg

from app.categorization.essential import ESSENTIAL_CATEGORIES, NON_SPENDING_CATEGORIES

_MONTH_RE = re.compile(r"^\d{4}-\d{2}$")


def validate_month(s: str) -> None:
    if not _MONTH_RE.match(s):
        raise ValueError(f"invalid month format: {s!r}")


def _prev_month(month: str) -> str:
    """2026-05 → 2026-04, 2026-01 → 2025-12."""
    y, m = int(month[:4]), int(month[5:7])
    if m == 1:
        return f"{y - 1:04d}-12"
    return f"{y:04d}-{m - 1:02d}"


async def summary(conn: asyncpg.Connection, user_id: UUID, month: str) -> dict:
    validate_month(month)
    prev = _prev_month(month)

    # "지출"은 소비 기준 — 이체/저축(비소비, 성격 불명)은 제외한다(effective 카테고리).
    non_spending = list(NON_SPENDING_CATEGORIES)
    row = await conn.fetchrow(
        """
        SELECT COALESCE(SUM(amount), 0)::numeric AS total,
               COUNT(*) AS cnt
        FROM transactions
        WHERE user_id = $1 AND to_char(txn_date, 'YYYY-MM') = $2 AND amount > 0
          AND NOT (COALESCE(user_category_override, category) = ANY($3::text[]))
        """,
        user_id, month, non_spending,
    )
    prev_row = await conn.fetchrow(
        """
        SELECT COALESCE(SUM(amount), 0)::numeric AS total
        FROM transactions
        WHERE user_id = $1 AND to_char(txn_date, 'YYYY-MM') = $2 AND amount > 0
          AND NOT (COALESCE(user_category_override, category) = ANY($3::text[]))
        """,
        user_id, prev, non_spending,
    )
    income_row = await conn.fetchrow(
        """
        SELECT COALESCE(SUM(-amount), 0)::numeric AS income
        FROM transactions
        WHERE user_id = $1 AND to_char(txn_date, 'YYYY-MM') = $2
          AND amount < 0
          AND COALESCE(user_category_override, category) <> 'transfer'
        """,
        user_id, month,
    )

    cur_total = Decimal(row["total"])
    prev_total = Decimal(prev_row["total"])
    income_total = Decimal(income_row["income"])
    net_savings = income_total - cur_total

    diff_pct: float | None = None
    if prev_total > 0:
        diff_pct = float((cur_total - prev_total) / prev_total * 100)

    savings_rate: float | None = None
    if income_total > 0:
        savings_rate = float(net_savings / income_total * 100)

    return {
        "month": month,
        "total_amount": cur_total,
        "transaction_count": row["cnt"],
        "prev_month": prev,
        "prev_month_total": prev_total,
        "prev_month_diff_pct": diff_pct,
        "income_total": income_total,
        "net_savings": net_savings,
        "savings_rate": savings_rate,
    }


async def by_category(conn: asyncpg.Connection, user_id: UUID, month: str) -> list[dict]:
    validate_month(month)
    rows = await conn.fetch(
        """
        SELECT COALESCE(user_category_override, category) AS category,
               COALESCE(SUM(amount), 0)::numeric AS amount,
               COUNT(*) AS count
        FROM transactions
        WHERE user_id = $1 AND to_char(txn_date, 'YYYY-MM') = $2 AND amount > 0
          AND NOT (COALESCE(user_category_override, category) = ANY($3::text[]))
        GROUP BY COALESCE(user_category_override, category)
        ORDER BY amount DESC
        """,
        user_id, month, list(NON_SPENDING_CATEGORIES),
    )
    return [{"category": r["category"], "amount": r["amount"], "count": r["count"]} for r in rows]


async def by_essential(conn: asyncpg.Connection, user_id: UUID, month: str) -> list[dict]:
    validate_month(month)
    # 이체/저축(성격 불명·비소비)은 필수/비필수 지출 분석에서 제외(effective 카테고리 기준 —
    # 사용자가 이체를 실제 지출 카테고리로 재분류하면 자동으로 다시 포함됨).
    rows = await conn.fetch(
        """
        SELECT (CASE WHEN essential_override IS NOT NULL THEN essential_override
                     ELSE (COALESCE(user_category_override, category) = ANY($3::text[]))
                END) AS essential,
               COALESCE(SUM(amount), 0)::numeric AS amount,
               COUNT(*) AS count
        FROM transactions
        WHERE user_id = $1 AND to_char(txn_date, 'YYYY-MM') = $2 AND amount > 0
          AND NOT (COALESCE(user_category_override, category) = ANY($4::text[]))
        GROUP BY (CASE WHEN essential_override IS NOT NULL THEN essential_override
                       ELSE (COALESCE(user_category_override, category) = ANY($3::text[]))
                  END)
        ORDER BY (CASE WHEN essential_override IS NOT NULL THEN essential_override
                       ELSE (COALESCE(user_category_override, category) = ANY($3::text[]))
                  END) DESC
        """,
        user_id, month, list(ESSENTIAL_CATEGORIES), list(NON_SPENDING_CATEGORIES),
    )
    return [{"essential": r["essential"], "amount": r["amount"], "count": r["count"]} for r in rows]


async def cashflow_by_month(conn: asyncpg.Connection, user_id: UUID, last_n: int) -> list[dict]:
    if not (1 <= last_n <= 24):
        raise ValueError(f"last_n out of range: {last_n}")
    rows = await conn.fetch(
        """
        SELECT to_char(txn_date, 'YYYY-MM') AS month,
               COALESCE(SUM(amount) FILTER (
                   WHERE amount > 0
                     AND NOT (COALESCE(user_category_override, category) = ANY($3::text[]))
               ), 0)::numeric AS expense,
               COALESCE(SUM(-amount) FILTER (
                   WHERE amount < 0 AND COALESCE(user_category_override, category) <> 'transfer'
               ), 0)::numeric AS income
        FROM transactions
        WHERE user_id = $1
          AND txn_date >= date_trunc('month', CURRENT_DATE - ($2 - 1) * INTERVAL '1 month')
        GROUP BY to_char(txn_date, 'YYYY-MM')
        ORDER BY to_char(txn_date, 'YYYY-MM') ASC
        """,
        user_id, last_n, list(NON_SPENDING_CATEGORIES),
    )
    return [{"month": r["month"], "expense": r["expense"], "income": r["income"]} for r in rows]


async def top_merchants(
    conn: asyncpg.Connection, user_id: UUID, month: str, limit: int,
) -> list[dict]:
    validate_month(month)
    if not (1 <= limit <= 20):
        raise ValueError(f"limit out of range: {limit}")
    rows = await conn.fetch(
        """
        SELECT COALESCE(merchant_normalized, merchant_raw) AS merchant,
               COALESCE(SUM(amount), 0)::numeric AS amount,
               COUNT(*) AS count
        FROM transactions
        WHERE user_id = $1 AND to_char(txn_date, 'YYYY-MM') = $2 AND amount > 0
          AND NOT (COALESCE(user_category_override, category) = ANY($4::text[]))
        GROUP BY COALESCE(merchant_normalized, merchant_raw)
        ORDER BY amount DESC
        LIMIT $3
        """,
        user_id, month, limit, list(NON_SPENDING_CATEGORIES),
    )
    # 응답 필드명은 merchant_raw 유지(프론트 무변경) — 값은 대표(정규화) 가맹점명.
    return [
        {"merchant_raw": r["merchant"], "amount": r["amount"], "count": r["count"]}
        for r in rows
    ]
