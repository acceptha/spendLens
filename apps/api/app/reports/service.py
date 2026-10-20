"""월 결산 — dashboard·budgets·insights 서비스를 조합한 닫힌 달 돌아보기.

지출 수치는 dashboard 서비스를 그대로 써서 대시보드·예산 탭과 항상 같다.
"""
from datetime import date
from decimal import Decimal
from uuid import UUID

import asyncpg

from app.budgets import service as budgets
from app.dashboard import service as dash
from app.insights import service as insights
from app.insights.llm import InsightError


async def available_months(conn: asyncpg.Connection, user_id: UUID) -> list[str]:
    rows = await conn.fetch(
        "SELECT DISTINCT to_char(txn_date, 'YYYY-MM') AS m FROM transactions "
        "WHERE user_id = $1 ORDER BY m DESC",
        user_id,
    )
    return [r["m"] for r in rows]


def default_month(months: list[str], current: str) -> str | None:
    """이번 달 이전 중 최근 달(명세서는 월이 지난 뒤 올라온다). 없으면 최근 달."""
    closed = [m for m in months if m < current]
    if closed:
        return closed[0]
    return months[0] if months else None


def top_categories(rows: list[dict], n: int = 5) -> list[dict]:
    total = sum((r["amount"] for r in rows), Decimal(0))
    return [
        {
            "category": r["category"],
            "amount": r["amount"],
            "share": round(float(r["amount"] / total), 4) if total > 0 else 0.0,
        }
        for r in rows[:n]
    ]


def category_changes(cur: list[dict], prev: list[dict], n: int = 3) -> dict:
    cur_map = {r["category"]: r["amount"] for r in cur}
    prev_map = {r["category"]: r["amount"] for r in prev}
    changes = []
    for cat in cur_map.keys() | prev_map.keys():
        amount = cur_map.get(cat, Decimal(0))
        prev_amount = prev_map.get(cat, Decimal(0))
        changes.append({
            "category": cat,
            "amount": amount,
            "prev_amount": prev_amount,
            "diff": amount - prev_amount,
        })
    increased = sorted((c for c in changes if c["diff"] > 0), key=lambda c: -c["diff"])
    decreased = sorted((c for c in changes if c["diff"] < 0), key=lambda c: c["diff"])
    return {"increased": increased[:n], "decreased": decreased[:n]}


async def monthly_report(
    conn: asyncpg.Connection, user_id: UUID, month: str | None, today: date
) -> dict:
    if month is not None:
        dash.validate_month(month)
    months = await available_months(conn, user_id)
    month = month or default_month(months, today.strftime("%Y-%m"))
    if month is None:
        return {
            "month": None,
            "available_months": [],
            "summary": None,
            "top_categories": [],
            "category_changes": {"increased": [], "decreased": []},
            "budget": None,
            "insight": None,
        }

    s = await dash.summary(conn, user_id, month)
    cur = await dash.by_category(conn, user_id, month)
    prev = await dash.by_category(conn, user_id, s["prev_month"])

    items = (await budgets.status(conn, user_id, month, today))["items"]
    budget = None
    if items:
        over = sum(1 for i in items if i["level"] == "over")
        budget = {"total": len(items), "kept": len(items) - over, "over": over, "items": items}

    # 결산을 열면 인사이트가 없을 때 자동 생성(캐시 재사용). 실패해도 결산은 보여준다.
    try:
        ins = await insights.generate(conn, user_id, month, force=False)
        insight = {
            "summary": ins["summary"],
            "highlights": ins["highlights"],
            "generated_at": ins["generated_at"],
        }
    except (insights.BudgetExceededError, InsightError):
        insight = None

    return {
        "month": month,
        "available_months": months,
        "summary": {
            "spent": s["total_amount"],
            "income": s["income_total"],
            "net_savings": s["net_savings"],
            "savings_rate": s["savings_rate"],
            "transaction_count": s["transaction_count"],
            "prev_month": s["prev_month"],
            "prev_spent": s["prev_month_total"],
            "spent_diff_pct": s["prev_month_diff_pct"],
        },
        "top_categories": top_categories(cur),
        "category_changes": category_changes(cur, prev),
        "budget": budget,
        "insight": insight,
    }
