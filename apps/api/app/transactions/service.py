import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import asyncpg

from app.categorization.merchant import normalize_merchant
from app.transactions.schemas import TransactionIn


def compute_dedup_hash(
    user_id: UUID,
    source_type: str,
    approval_no: str | None,
    *,
    fallback_date: date,
    fallback_amount: Decimal,
    fallback_merchant: str,
) -> str:
    if approval_no:
        payload = f"{user_id}|{source_type}|approval:{approval_no}"
    else:
        payload = (
            f"{user_id}|{source_type}|fb:"
            f"{fallback_date.isoformat()}|{fallback_amount}|{fallback_merchant}"
        )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


async def insert_transactions(
    conn: asyncpg.Connection,
    user_id: UUID,
    source_file_id: UUID,
    source_type: str,
    txns: list[TransactionIn],
) -> tuple[int, int]:
    """Insert with ON CONFLICT DO NOTHING. Returns (inserted, skipped)."""
    inserted = 0
    skipped = 0
    for t in txns:
        dedup = compute_dedup_hash(
            user_id, source_type, t.approval_no,
            fallback_date=t.txn_date,
            fallback_amount=t.amount,
            fallback_merchant=t.merchant_raw,
        )
        result = await conn.fetchrow(
            """
            INSERT INTO transactions (
              user_id, source_file_id, source_type,
              txn_date, txn_time, amount, merchant_raw, merchant_normalized,
              approval_no, card_last4, installment_months,
              is_canceled, category, dedup_hash, raw_row
            ) VALUES (
              $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15::jsonb
            )
            ON CONFLICT (user_id, dedup_hash) DO NOTHING
            RETURNING id
            """,
            user_id, source_file_id, source_type,
            t.txn_date, t.txn_time, t.amount, t.merchant_raw,
            normalize_merchant(t.merchant_raw),
            t.approval_no, t.card_last4, t.installment_months,
            t.is_canceled, t.category, dedup,
            json.dumps(t.raw_row, default=str, ensure_ascii=False),
        )
        if result is not None:
            inserted += 1
        else:
            skipped += 1
    return inserted, skipped


async def update_category(
    conn: asyncpg.Connection,
    user_id: UUID,
    transaction_id: UUID,
    category: str,
) -> bool:
    """Set user_category_override for one transaction owned by user_id.

    Returns True if updated, False if not found or owned by a different user.
    Caller must validate `category` is in CATEGORIES (TransactionPatchRequest does this).
    """
    row = await conn.fetchrow(
        """
        UPDATE transactions
        SET user_category_override = $3
        WHERE id = $2 AND user_id = $1
        RETURNING id
        """,
        user_id, transaction_id, category,
    )
    return row is not None


async def update_essential(
    conn: asyncpg.Connection,
    user_id: UUID,
    transaction_id: UUID,
    essential_override: bool | None,
) -> bool:
    """Set essential_override (true/false/null) for one transaction owned by user_id.

    null clears the override → effective_essential falls back to the category default.
    Returns True if updated, False if not found / owned by another user.
    """
    row = await conn.fetchrow(
        """
        UPDATE transactions
        SET essential_override = $3
        WHERE id = $2 AND user_id = $1
        RETURNING id
        """,
        user_id, transaction_id, essential_override,
    )
    return row is not None


async def remove_transaction(
    conn: asyncpg.Connection,
    user_id: UUID,
    transaction_id: UUID,
) -> bool:
    """Delete one transaction owned by user_id. False if not found / not owned.

    하드 삭제 — 같은 명세서를 다시 올리면 dedup_hash가 비어 있으므로 다시 들어온다.
    """
    row = await conn.fetchrow(
        "DELETE FROM transactions WHERE id = $2 AND user_id = $1 RETURNING id",
        user_id, transaction_id,
    )
    return row is not None


async def same_merchant_pending(
    conn: asyncpg.Connection, user_id: UUID, transaction_id: UUID
) -> tuple[int, str | None]:
    """이 거래와 같은 정규화 가맹점의 다른 거래 중, 이 거래의 카테고리로 바꿀 수 있는 건수.

    대상: 같은 사용자, 사용자가 직접 고치지 않은 거래(override NULL), 카테고리가 다른 것.
    Returns (건수, 정규화 가맹점명). 가맹점명이 비어 있으면 (0, None).
    """
    row = await conn.fetchrow(
        """
        SELECT t.merchant_normalized AS merchant,
               (SELECT COUNT(*) FROM transactions o
                WHERE o.user_id = $1 AND o.id <> t.id
                  AND o.merchant_normalized = t.merchant_normalized
                  AND o.user_category_override IS NULL
                  AND o.category <> COALESCE(t.user_category_override, t.category)) AS pending
        FROM transactions t
        WHERE t.id = $2 AND t.user_id = $1
        """,
        user_id, transaction_id,
    )
    if row is None or not row["merchant"]:
        return 0, None
    return row["pending"], row["merchant"]


async def apply_category_to_merchant(
    conn: asyncpg.Connection, user_id: UUID, transaction_id: UUID
) -> int | None:
    """이 거래의 카테고리를 같은 가맹점의 대상 거래(same_merchant_pending 기준)에 일괄 적용.

    사용자 수정(override)으로 기록되어 이후 업로드 학습에도 반영된다.
    Returns 갱신 건수, 거래가 없거나 다른 사용자 것이면 None.
    """
    exists = await conn.fetchval(
        "SELECT 1 FROM transactions WHERE id = $2 AND user_id = $1", user_id, transaction_id
    )
    if exists is None:
        return None
    rows = await conn.fetch(
        """
        WITH t AS (
            SELECT merchant_normalized AS m,
                   COALESCE(user_category_override, category) AS c
            FROM transactions WHERE id = $2 AND user_id = $1
        )
        UPDATE transactions o SET user_category_override = t.c
        FROM t
        WHERE o.user_id = $1 AND o.id <> $2
          AND t.m IS NOT NULL AND t.m <> ''
          AND o.merchant_normalized = t.m
          AND o.user_category_override IS NULL
          AND o.category <> t.c
        RETURNING o.id
        """,
        user_id, transaction_id,
    )
    return len(rows)


def today_kst() -> date:
    return datetime.now(ZoneInfo("Asia/Seoul")).date()


async def insert_manual(
    conn: asyncpg.Connection,
    user_id: UUID,
    *,
    txn_date: date,
    amount: Decimal,
    merchant: str,
    category: str,
) -> UUID:
    """직접 입력 거래 1건 저장. source_type='manual'.

    업로드 dedup 대상이 아니다 — 같은 날 같은 금액을 두 번 써도 둘 다 기록돼야 하므로
    dedup_hash는 매번 고유값.
    """
    return await conn.fetchval(
        """
        INSERT INTO transactions (
          user_id, source_type, txn_date, amount, merchant_raw, merchant_normalized,
          category, dedup_hash, raw_row
        ) VALUES ($1, 'manual', $2, $3, $4, $5, $6, $7, '{}'::jsonb)
        RETURNING id
        """,
        user_id, txn_date, amount, merchant, normalize_merchant(merchant), category,
        f"manual:{uuid4()}",
    )
