import hashlib
import json
from datetime import date
from decimal import Decimal
from uuid import UUID

import asyncpg

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
              txn_date, txn_time, amount, merchant_raw,
              approval_no, card_last4, installment_months,
              is_canceled, category, dedup_hash, raw_row
            ) VALUES (
              $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14::jsonb
            )
            ON CONFLICT (user_id, dedup_hash) DO NOTHING
            RETURNING id
            """,
            user_id, source_file_id, source_type,
            t.txn_date, t.txn_time, t.amount, t.merchant_raw,
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
