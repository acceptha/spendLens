from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class BudgetSetRequest(BaseModel):
    category: str
    # None = 이번 달부터 예산 해제
    amount: int | None = Field(..., ge=1, lt=10**12)


class BudgetItemOut(BaseModel):
    category: str
    budget: Decimal
    spent: Decimal
    ratio: float
    projected: Decimal | None
    level: Literal["ok", "warn", "over"]


class BudgetStatusResponse(BaseModel):
    month: str
    is_current: bool
    days_elapsed: int
    days_in_month: int
    items: list[BudgetItemOut]
