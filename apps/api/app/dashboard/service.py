"""Dashboard aggregate queries — raw SQL on transactions.

모든 집계는 amount > 0 (출금) 기준. 입금/소득은 W4 이후 분석.
effective_category = COALESCE(user_category_override, category).
"""
import re
from decimal import Decimal
from uuid import UUID

import asyncpg

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

    row = await conn.fetchrow(
        """
        SELECT COALESCE(SUM(amount), 0)::numeric AS total,
               COUNT(*) AS cnt
        FROM transactions
        WHERE user_id = $1 AND to_char(txn_date, 'YYYY-MM') = $2 AND amount > 0
        """,
        user_id, month,
    )
    prev_row = await conn.fetchrow(
        """
        SELECT COALESCE(SUM(amount), 0)::numeric AS total
        FROM transactions
        WHERE user_id = $1 AND to_char(txn_date, 'YYYY-MM') = $2 AND amount > 0
        """,
        user_id, prev,
    )

    cur_total = Decimal(row["total"])
    prev_total = Decimal(prev_row["total"])
    diff_pct: float | None = None
    if prev_total > 0:
        diff_pct = float((cur_total - prev_total) / prev_total * 100)

    return {
        "month": month,
        "total_amount": cur_total,
        "transaction_count": row["cnt"],
        "prev_month": prev,
        "prev_month_total": prev_total,
        "prev_month_diff_pct": diff_pct,
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
        GROUP BY COALESCE(user_category_override, category)
        ORDER BY amount DESC
        """,
        user_id, month,
    )
    return [{"category": r["category"], "amount": r["amount"], "count": r["count"]} for r in rows]


async def by_month(conn: asyncpg.Connection, user_id: UUID, last_n: int) -> list[dict]:
    if not (1 <= last_n <= 24):
        raise ValueError(f"last_n out of range: {last_n}")
    rows = await conn.fetch(
        """
        SELECT to_char(txn_date, 'YYYY-MM') AS month,
               COALESCE(SUM(amount), 0)::numeric AS amount
        FROM transactions
        WHERE user_id = $1
          AND txn_date >= date_trunc('month', CURRENT_DATE - ($2 - 1) * INTERVAL '1 month')
          AND amount > 0
        GROUP BY to_char(txn_date, 'YYYY-MM')
        ORDER BY to_char(txn_date, 'YYYY-MM') ASC
        """,
        user_id, last_n,
    )
    return [{"month": r["month"], "amount": r["amount"]} for r in rows]


async def top_merchants(
    conn: asyncpg.Connection, user_id: UUID, month: str, limit: int,
) -> list[dict]:
    validate_month(month)
    if not (1 <= limit <= 20):
        raise ValueError(f"limit out of range: {limit}")
    rows = await conn.fetch(
        """
        SELECT merchant_raw,
               COALESCE(SUM(amount), 0)::numeric AS amount,
               COUNT(*) AS count
        FROM transactions
        WHERE user_id = $1 AND to_char(txn_date, 'YYYY-MM') = $2 AND amount > 0
        GROUP BY merchant_raw
        ORDER BY amount DESC
        LIMIT $3
        """,
        user_id, month, limit,
    )
    return [
        {"merchant_raw": r["merchant_raw"], "amount": r["amount"], "count": r["count"]}
        for r in rows
    ]
