from datetime import date, time
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, field_validator


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
    source_type: str  # 카드사/은행 파서 키 또는 "manual"(직접 입력)
    # W3 추가
    auto_category: str
    user_category_override: str | None
    effective_category: str
    # W4 — 필수/비필수 (파생)
    essential_override: bool | None
    effective_essential: bool


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


class TransactionPatchResponse(BaseModel):
    # 같은 가맹점에서 이 카테고리로 일괄 변경할 수 있는 거래 수 (웹이 "모두 변경" 제안에 사용)
    same_merchant_pending: int
    merchant: str | None


class ApplyToMerchantResponse(BaseModel):
    updated: int


class EssentialPatchRequest(BaseModel):
    essential_override: bool | None


class ManualTransactionRequest(BaseModel):
    """현금 지출·수입 등 명세서에 없는 거래 직접 입력."""
    kind: Literal["expense", "income"]
    txn_date: date
    amount: int = Field(..., ge=1, lt=100_000_000)
    merchant: str
    # 생략 시: 지출은 업로드와 같은 자동 분류(수정 학습 → 룰북 → LLM), 수입은 income
    category: CategoryLiteral | None = None

    @field_validator("merchant")
    @classmethod
    def _merchant_trimmed(cls, v: str) -> str:
        v = v.strip()
        if not 1 <= len(v) <= 100:
            raise ValueError("merchant must be 1-100 characters")
        return v
