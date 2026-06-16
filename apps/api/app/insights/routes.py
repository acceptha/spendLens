from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.auth.deps import current_user_id
from app.db import acquire
from app.insights import service
from app.insights.llm import InsightError
from app.insights.schemas import InsightGenerateRequest, InsightResponse

router = APIRouter(prefix="/insights", tags=["insights"])


@router.get("", response_model=InsightResponse | None)
async def get_insight(
    month: str,
    user_id: UUID = Depends(current_user_id),  # noqa: B008
) -> InsightResponse | None:
    async with acquire() as conn:
        cached = await service.get_cached(conn, user_id, month)
    return InsightResponse(**cached) if cached else None


@router.post("/generate", response_model=InsightResponse)
async def generate_insight_route(
    req: InsightGenerateRequest,
    force: bool = False,
    user_id: UUID = Depends(current_user_id),  # noqa: B008
) -> InsightResponse:
    try:
        async with acquire() as conn:
            data = await service.generate(conn, user_id, req.month, force=force)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="INVALID_MONTH_FORMAT") from exc
    except service.BudgetExceededError as exc:
        raise HTTPException(status_code=503, detail="BUDGET_EXCEEDED") from exc
    except InsightError as exc:
        raise HTTPException(status_code=502, detail="INSIGHT_GENERATION_FAILED") from exc
    return InsightResponse(**data)
