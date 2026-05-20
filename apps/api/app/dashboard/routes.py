from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth.deps import current_user_id
from app.dashboard import service
from app.db import acquire

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class SummaryResponse(BaseModel):
    month: str
    total_amount: Decimal
    transaction_count: int
    prev_month: str
    prev_month_total: Decimal
    prev_month_diff_pct: float | None


class CategoryBucket(BaseModel):
    category: str
    amount: Decimal
    count: int


class MonthBucket(BaseModel):
    month: str
    amount: Decimal


class MerchantBucket(BaseModel):
    merchant_raw: str
    amount: Decimal
    count: int


@router.get("/summary", response_model=SummaryResponse)
async def get_summary(
    month: str,
    user_id: UUID = Depends(current_user_id),  # noqa: B008
) -> SummaryResponse:
    try:
        async with acquire() as conn:
            data = await service.summary(conn, user_id, month)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="INVALID_MONTH_FORMAT") from exc
    return SummaryResponse(**data)


@router.get("/by-category", response_model=list[CategoryBucket])
async def get_by_category(
    month: str,
    user_id: UUID = Depends(current_user_id),  # noqa: B008
) -> list[CategoryBucket]:
    try:
        async with acquire() as conn:
            rows = await service.by_category(conn, user_id, month)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="INVALID_MONTH_FORMAT") from exc
    return [CategoryBucket(**r) for r in rows]


@router.get("/by-month", response_model=list[MonthBucket])
async def get_by_month(
    last_n: int = 6,
    user_id: UUID = Depends(current_user_id),  # noqa: B008
) -> list[MonthBucket]:
    try:
        async with acquire() as conn:
            rows = await service.by_month(conn, user_id, last_n)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="INVALID_LAST_N") from exc
    return [MonthBucket(**r) for r in rows]


@router.get("/top-merchants", response_model=list[MerchantBucket])
async def get_top_merchants(
    month: str,
    limit: int = 5,
    user_id: UUID = Depends(current_user_id),  # noqa: B008
) -> list[MerchantBucket]:
    try:
        async with acquire() as conn:
            rows = await service.top_merchants(conn, user_id, month, limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="INVALID_PARAMETER") from exc
    return [MerchantBucket(**r) for r in rows]
