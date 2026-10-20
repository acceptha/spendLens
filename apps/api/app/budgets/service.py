"""월 예산 — 적용 시작 월(effective_from) 행 + 조회 시 지출 집계.

월 M의 예산 = 카테고리별 effective_from <= M 인 가장 최근 행(amount NULL이면 해제).
지출 집계는 dashboard와 같은 규칙: 출금(amount > 0), effective_category 기준,
NON_SPENDING_CATEGORIES 제외. "이번 달/오늘"은 Asia/Seoul.
"""
import calendar
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

import asyncpg

from app.categorization.essential import NON_SPENDING_CATEGORIES
from app.categorization.rulebook import CATEGORIES
from app.dashboard.service import validate_month

TOTAL = "_total"
ALLOWED_CATEGORIES: tuple[str, ...] = (TOTAL,) + tuple(
    c for c in CATEGORIES if c not in NON_SPENDING_CATEGORIES and c != "income"
)
_KST = ZoneInfo("Asia/Seoul")
_WARN_RATIO = Decimal("0.8")


def today_kst() -> date:
    return datetime.now(_KST).date()


def current_month() -> str:
    return today_kst().strftime("%Y-%m")


def month_days(month: str, today: date) -> tuple[int, int, bool]:
    """(경과일, 월 일수, 이번 달 여부). 지난달은 경과일=월 일수, 미래 달은 0."""
    y, m = int(month[:4]), int(month[5:7])
    days_in_month = calendar.monthrange(y, m)[1]
    cur = today.strftime("%Y-%m")
    if month == cur:
        return today.day, days_in_month, True
    if month < cur:
        return days_in_month, days_in_month, False
    return 0, days_in_month, False


def project(
    spent: Decimal, days_elapsed: int, days_in_month: int, is_current: bool
) -> Decimal | None:
    if not is_current or days_elapsed < 1:
        return None
    return (spent / days_elapsed * days_in_month).quantize(Decimal("1"), ROUND_HALF_UP)


def budget_level(spent: Decimal, budget: Decimal, projected: Decimal | None) -> str:
    if spent >= budget:
        return "over"
    if spent >= budget * _WARN_RATIO or (projected is not None and projected > budget):
        return "warn"
    return "ok"


async def _budgets_for_month(
    conn: asyncpg.Connection, user_id: UUID, month: str
) -> dict[str, Decimal]:
    rows = await conn.fetch(
        """
        SELECT DISTINCT ON (category) category, amount
        FROM budgets
        WHERE user_id = $1 AND effective_from <= $2
        ORDER BY category, effective_from DESC
        """,
        user_id, month,
    )
    # NUMERIC(14,0)은 asyncpg가 Decimal('5E+4')처럼 지수형으로 줄 수 있어 정수로 정규화.
    return {r["category"]: Decimal(int(r["amount"])) for r in rows if r["amount"] is not None}


async def _spent_by_category(
    conn: asyncpg.Connection, user_id: UUID, month: str
) -> dict[str, Decimal]:
    rows = await conn.fetch(
        """
        SELECT COALESCE(user_category_override, category) AS cat,
               COALESCE(SUM(amount), 0)::numeric AS spent
        FROM transactions
        WHERE user_id = $1 AND to_char(txn_date, 'YYYY-MM') = $2 AND amount > 0
          AND NOT (COALESCE(user_category_override, category) = ANY($3::text[]))
        GROUP BY 1
        """,
        user_id, month, list(NON_SPENDING_CATEGORIES),
    )
    return {r["cat"]: r["spent"] for r in rows}


async def status(conn: asyncpg.Connection, user_id: UUID, month: str, today: date) -> dict:
    validate_month(month)
    budgets = await _budgets_for_month(conn, user_id, month)
    spent_map = await _spent_by_category(conn, user_id, month)
    days_elapsed, days_in_month, is_current = month_days(month, today)

    items = []
    for category, budget in budgets.items():
        spent = (
            sum(spent_map.values(), Decimal(0)) if category == TOTAL
            else spent_map.get(category, Decimal(0))
        )
        projected = project(spent, days_elapsed, days_in_month, is_current)
        items.append({
            "category": category,
            "budget": budget,
            "spent": spent,
            "ratio": round(float(spent / budget), 4),
            "projected": projected,
            "level": budget_level(spent, budget, projected),
        })
    items.sort(key=lambda i: (i["category"] != TOTAL, -i["ratio"]))
    return {
        "month": month,
        "is_current": is_current,
        "days_elapsed": days_elapsed,
        "days_in_month": days_in_month,
        "items": items,
    }


async def set_budget(
    conn: asyncpg.Connection, user_id: UUID, category: str, amount: int | None, month: str
) -> None:
    """이번 달(month)부터 적용. 같은 달 재저장은 덮어쓰기, amount None = 해제.

    단, 그 카테고리의 **첫 예산**은 사용자의 가장 오래된 거래 월부터 적용한다 —
    명세서는 월이 지난 뒤 올리므로 이미 올라온 과거 달도 바로 예산과 비교할 수 있게.
    """
    if amount is not None:
        has_history = await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM budgets WHERE user_id = $1 AND category = $2)",
            user_id, category,
        )
        if not has_history:
            earliest = await conn.fetchval(
                "SELECT to_char(MIN(txn_date), 'YYYY-MM') FROM transactions WHERE user_id = $1",
                user_id,
            )
            if earliest is not None and earliest < month:
                month = earliest
    await conn.execute(
        """
        INSERT INTO budgets (user_id, category, amount, effective_from)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (user_id, category, effective_from)
        DO UPDATE SET amount = EXCLUDED.amount, updated_at = now()
        """,
        user_id, category, amount, month,
    )
