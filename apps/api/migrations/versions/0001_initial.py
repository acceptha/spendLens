"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-30
"""
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.execute("""
        CREATE TABLE users (
          id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          email         CITEXT UNIQUE NOT NULL,
          password_hash TEXT NOT NULL,
          created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    op.execute("""
        CREATE TABLE refresh_tokens (
          jti        UUID PRIMARY KEY,
          user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          expires_at TIMESTAMPTZ NOT NULL,
          revoked_at TIMESTAMPTZ
        );
    """)
    op.execute("CREATE INDEX idx_refresh_user ON refresh_tokens(user_id);")

    op.execute("""
        CREATE TABLE source_files (
          id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          user_id        UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          source_type    TEXT NOT NULL,
          filename       TEXT NOT NULL,
          rows_total     INTEGER NOT NULL,
          rows_inserted  INTEGER NOT NULL,
          rows_skipped   INTEGER NOT NULL,
          uploaded_at    TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    op.execute("""
        CREATE TABLE transactions (
          id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          source_file_id      UUID REFERENCES source_files(id) ON DELETE SET NULL,
          source_type         TEXT NOT NULL,
          txn_date            DATE NOT NULL,
          txn_time            TIME,
          amount              NUMERIC(12,2) NOT NULL,
          merchant_raw        TEXT NOT NULL,
          merchant_normalized TEXT,
          approval_no         TEXT,
          card_last4          TEXT,
          installment_months  INTEGER,
          is_canceled         BOOLEAN NOT NULL DEFAULT false,
          category            TEXT NOT NULL DEFAULT 'unknown',
          essential           BOOLEAN,
          essential_reason    TEXT,
          dedup_hash          TEXT NOT NULL,
          raw_row             JSONB NOT NULL,
          created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
          UNIQUE (user_id, dedup_hash)
        );
    """)
    op.execute("CREATE INDEX idx_transactions_user_date ON transactions(user_id, txn_date DESC);")
    op.execute(
        "CREATE INDEX idx_transactions_approval ON transactions(user_id, approval_no) "
        "WHERE approval_no IS NOT NULL;"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS transactions;")
    op.execute("DROP TABLE IF EXISTS source_files;")
    op.execute("DROP TABLE IF EXISTS refresh_tokens;")
    op.execute("DROP TABLE IF EXISTS users;")
