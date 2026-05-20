from datetime import date, time
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class TransactionIn(BaseModel):
    """One parsed row, before DB insert."""
    txn_date: date
    txn_time: time | None = None
    amount: Decimal
    merchant_raw: str
    approval_no: str | None = None
    card_last4: str | None = None
    installment_months: int | None = None
    is_canceled: bool = False
    category: str = "unknown"
    raw_row: dict[str, Any]


class TransactionOut(BaseModel):
    id: str
    txn_date: date
    txn_time: time | None
    amount: Decimal
    merchant_raw: str
    merchant_normalized: str | None
    approval_no: str | None
    card_last4: str | None
    installment_months: int | None
    is_canceled: bool
    category: str
    # W3 추가
    auto_category: str
    user_category_override: str | None
    effective_category: str
    essential: bool | None
    essential_reason: str | None


class UploadResponse(BaseModel):
    uploaded: int
    skipped: int
    parse_errors: list[dict[str, Any]] = Field(default_factory=list)


from typing import Literal  # noqa: E402

# 19 categories — keep in sync with app.categorization.rulebook.CATEGORIES
CategoryLiteral = Literal[
    "coffee", "lunch", "dinner", "snack_late",
    "groceries", "transport", "telecom",
    "subscription", "entertainment", "health",
    "shopping", "utilities", "etc", "unknown",
    "savings", "insurance", "income", "transfer", "housing",
]


class TransactionPatchRequest(BaseModel):
    category: CategoryLiteral
