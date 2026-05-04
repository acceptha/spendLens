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
    essential: bool | None
    essential_reason: str | None


class UploadResponse(BaseModel):
    uploaded: int
    skipped: int
    parse_errors: list[dict[str, Any]] = Field(default_factory=list)
