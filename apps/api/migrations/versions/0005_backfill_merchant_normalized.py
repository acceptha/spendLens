"""backfill merchant_normalized for pre-W6 transactions

W6 이전에 업로드된 거래는 merchant_normalized가 NULL이라 Top 가맹점 그룹핑이
브랜드 단위로 묶이지 않는다. 배포 시 자동 실행되도록 데이터 마이그레이션으로 둔다
(scripts/backfill_merchant_normalized.py와 같은 로직, 멱등 — NULL만 대상).

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-19
"""
import sqlalchemy as sa
from alembic import op

from app.categorization.merchant import normalize_merchant

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "SELECT DISTINCT merchant_raw FROM transactions "
            "WHERE merchant_normalized IS NULL"
        )
    ).fetchall()
    for (raw,) in rows:
        conn.execute(
            sa.text(
                "UPDATE transactions SET merchant_normalized = :norm "
                "WHERE merchant_normalized IS NULL AND merchant_raw = :raw"
            ),
            {"norm": normalize_merchant(raw or ""), "raw": raw},
        )


def downgrade() -> None:
    # 데이터 백필은 되돌리지 않는다 (merchant_normalized는 파생값).
    pass
