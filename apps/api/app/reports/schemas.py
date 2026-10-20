from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.budgets.schemas import BudgetItemOut
from app.insights.schemas import InsightHighlight


class ReportSummaryOut(BaseModel):
    spent: Decimal
    income: Decimal
    net_savings: Decimal
    savings_rate: float | None
    transaction_count: int
    prev_month: str
    prev_spent: Decimal
    spent_diff_pct: float | None


class TopCategoryOut(BaseModel):
    category: str
    amount: Decimal
    share: float


class CategoryChangeOut(BaseModel):
    category: str
    amount: Decimal
    prev_amount: Decimal
    diff: Decimal


class CategoryChangesOut(BaseModel):
    increased: list[CategoryChangeOut]
    decreased: list[CategoryChangeOut]


class ReportBudgetOut(BaseModel):
    total: int
    kept: int
    over: int
    items: list[BudgetItemOut]


class ReportInsightOut(BaseModel):
    summary: str
    highlights: list[InsightHighlight]
    generated_at: datetime


class MonthlyReportResponse(BaseModel):
    month: str | None
    available_months: list[str]
    summary: ReportSummaryOut | None
    top_categories: list[TopCategoryOut]
    category_changes: CategoryChangesOut
    budget: ReportBudgetOut | None
    insight: ReportInsightOut | None
