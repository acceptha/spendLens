from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.auth.deps import current_user_id
from app.db import acquire
from app.parsers import ParseError, get_parser, SOURCE_TYPE_SAMSUNG_XLSX
from app.transactions.schemas import TransactionOut, UploadResponse
from app.transactions.service import insert_transactions


router = APIRouter(prefix="/transactions", tags=["transactions"])


_MAX_FILE_BYTES = 10 * 1024 * 1024  # 10MB
_ALLOWED_EXT = ".xlsx"
_ALLOWED_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.post("/upload", response_model=UploadResponse)
async def upload(
    file: UploadFile = File(...),
    user_id: UUID = Depends(current_user_id),
) -> UploadResponse:
    if not file.filename or not file.filename.lower().endswith(_ALLOWED_EXT):
        raise HTTPException(status_code=400, detail={"error": "INVALID_FILE_TYPE", "expected": _ALLOWED_EXT})
    if file.content_type and file.content_type != _ALLOWED_MIME:
        # MIME 미스매치는 경고만 (브라우저별 다름) — 확장자 통과면 진행
        pass

    file_bytes = await file.read()
    if len(file_bytes) > _MAX_FILE_BYTES:
        raise HTTPException(status_code=400, detail={"error": "FILE_TOO_LARGE"})

    source_type = SOURCE_TYPE_SAMSUNG_XLSX
    parser = get_parser(source_type)
    try:
        result = parser(file_bytes)
    except ParseError as e:
        raise HTTPException(status_code=400, detail={"error": e.code, **e.details})

    source_file_id = uuid4()
    async with acquire() as conn:
        await conn.execute(
            """
            INSERT INTO source_files (id, user_id, source_type, filename, rows_total, rows_inserted, rows_skipped)
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


@router.get("", response_model=list[TransactionOut], summary="사용자별 거래 목록")
async def list_transactions(user_id: UUID = Depends(current_user_id)) -> list[TransactionOut]:
    async with acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id::text, txn_date, txn_time, amount, merchant_raw, merchant_normalized,
                   approval_no, card_last4, installment_months, is_canceled,
                   category, essential, essential_reason
            FROM transactions
            WHERE user_id = $1
            ORDER BY txn_date DESC, txn_time DESC NULLS LAST, created_at DESC
            """,
            user_id,
        )
    return [TransactionOut(**dict(r)) for r in rows]
