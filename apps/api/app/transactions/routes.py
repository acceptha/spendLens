import re
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.auth.deps import current_user_id
from app.categorization.service import classify as classify_category
from app.db import acquire
from app.parsers import ParseError, detect
from app.transactions.schemas import (
    TransactionOut,
    TransactionPatchRequest,
    UploadResponse,
)
from app.transactions.service import insert_transactions, update_category

router = APIRouter(prefix="/transactions", tags=["transactions"])


_MAX_FILE_BYTES = 10 * 1024 * 1024  # 10MB
_ALLOWED_EXT = ".xlsx"
_ALLOWED_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_MONTH_RE = re.compile(r"^\d{4}-\d{2}$")


@router.post("/upload", response_model=UploadResponse)
async def upload(
    file: UploadFile = File(...),  # noqa: B008
    user_id: UUID = Depends(current_user_id),  # noqa: B008
) -> UploadResponse:
    if not file.filename or not file.filename.lower().endswith(_ALLOWED_EXT):
        raise HTTPException(
            status_code=400, detail={"error": "INVALID_FILE_TYPE", "expected": _ALLOWED_EXT}
        )
    if file.content_type and file.content_type != _ALLOWED_MIME:
        # MIME 미스매치는 경고만 (브라우저별 다름) — 확장자 통과면 진행
        pass

    file_bytes = await file.read()
    if len(file_bytes) > _MAX_FILE_BYTES:
        raise HTTPException(status_code=400, detail={"error": "FILE_TOO_LARGE"})

    try:
        source_type, parser = detect(file_bytes)
        result = parser(file_bytes)
    except ParseError as e:
        raise HTTPException(status_code=400, detail={"error": e.code, **e.details}) from e

    for tx in result.transactions:
        tx.category = await classify_category(tx.merchant_raw)

    source_file_id = uuid4()
    async with acquire() as conn:
        await conn.execute(
            """
            INSERT INTO source_files
              (id, user_id, source_type, filename, rows_total, rows_inserted, rows_skipped)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
            source_file_id, user_id, source_type, file.filename,
            result.rows_total, 0, 0,
        )
        inserted, skipped = await insert_transactions(
            conn, user_id, source_file_id, source_type, result.transactions
        )
        await conn.execute(
            """
            UPDATE source_files SET rows_inserted = $1, rows_skipped = $2 WHERE id = $3
            """,
            inserted, skipped, source_file_id,
        )

    return UploadResponse(uploaded=inserted, skipped=skipped, parse_errors=result.parse_errors)


@router.get("/months", response_model=list[str], summary="사용자별 거래가 있는 월 목록 (DESC)")
async def list_months(
    user_id: UUID = Depends(current_user_id),  # noqa: B008
) -> list[str]:
    async with acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT DISTINCT to_char(txn_date, 'YYYY-MM') AS month
            FROM transactions
            WHERE user_id = $1
            ORDER BY month DESC
            """,
            user_id,
        )
    return [r["month"] for r in rows]


@router.get("", response_model=list[TransactionOut], summary="거래 목록 (필터/검색/페이지네이션)")
async def list_transactions(
    month: str | None = None,
    category: str | None = None,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
    user_id: UUID = Depends(current_user_id),  # noqa: B008
) -> list[TransactionOut]:
    if month is not None and not _MONTH_RE.match(month):
        raise HTTPException(status_code=400, detail="INVALID_MONTH_FORMAT")
    if not (1 <= limit <= 200):
        raise HTTPException(status_code=400, detail="INVALID_LIMIT")
    if offset < 0:
        raise HTTPException(status_code=400, detail="INVALID_LIMIT")

    categories_list = (
        [c.strip() for c in category.split(",") if c.strip()] if category else None
    )
    # 모든 토큰이 빈 문자열(`category=,,,`)이면 []가 되어 ANY('{}')가 0 행을 반환
    # → 의도(필터 없음)와 어긋나므로 None으로 치환
    categories = categories_list if categories_list else None

    async with acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id::text, txn_date, txn_time, amount, merchant_raw, merchant_normalized,
                   approval_no, card_last4, installment_months, is_canceled,
                   category,
                   category AS auto_category,
                   user_category_override,
                   COALESCE(user_category_override, category) AS effective_category,
                   essential, essential_reason
            FROM transactions
            WHERE user_id = $1
              AND ($2::text IS NULL OR to_char(txn_date, 'YYYY-MM') = $2)
              AND ($3::text[] IS NULL OR COALESCE(user_category_override, category) = ANY($3))
              AND ($4::text IS NULL OR merchant_raw ILIKE '%' || $4 || '%')
            ORDER BY txn_date DESC, txn_time DESC NULLS LAST, created_at DESC
            LIMIT $5 OFFSET $6
            """,
            user_id, month, categories, search, limit, offset,
        )
    return [TransactionOut(**dict(r)) for r in rows]


@router.patch("/{transaction_id}", status_code=204)
async def patch_transaction(
    transaction_id: UUID,
    req: TransactionPatchRequest,
    user_id: UUID = Depends(current_user_id),  # noqa: B008
) -> None:
    async with acquire() as conn:
        updated = await update_category(conn, user_id, transaction_id, req.category)
    if not updated:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
