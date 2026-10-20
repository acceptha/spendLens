from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.auth.deps import current_user_id
from app.budgets import service as budgets
from app.db import acquire
from app.reports import service
from app.reports.schemas import MonthlyReportResponse

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/monthly", response_model=MonthlyReportResponse)
async def monthly_report(
    month: str | None = None,
    user_id: UUID = Depends(current_user_id),  # noqa: B008
) -> MonthlyReportResponse:
    try:
        async with acquire() as conn:
            data = await service.monthly_report(conn, user_id, month, budgets.today_kst())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="INVALID_MONTH_FORMAT") from exc
    return MonthlyReportResponse(**data)
