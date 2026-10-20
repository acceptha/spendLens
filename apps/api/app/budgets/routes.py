from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.auth.deps import current_user_id
from app.budgets import service
from app.budgets.schemas import BudgetSetRequest, BudgetStatusResponse
from app.db import acquire

router = APIRouter(prefix="/budgets", tags=["budgets"])


@router.get("/status", response_model=BudgetStatusResponse)
async def budget_status(
    month: str,
    user_id: UUID = Depends(current_user_id),  # noqa: B008
) -> BudgetStatusResponse:
    try:
        async with acquire() as conn:
            data = await service.status(conn, user_id, month, service.today_kst())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="INVALID_MONTH_FORMAT") from exc
    return BudgetStatusResponse(**data)


@router.put("", status_code=204)
async def set_budget(
    req: BudgetSetRequest,
    user_id: UUID = Depends(current_user_id),  # noqa: B008
) -> None:
    if req.category not in service.ALLOWED_CATEGORIES:
        raise HTTPException(status_code=400, detail="INVALID_CATEGORY")
    async with acquire() as conn:
        await service.set_budget(
            conn, user_id, req.category, req.amount, service.current_month()
        )
