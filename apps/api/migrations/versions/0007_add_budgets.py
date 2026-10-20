"""add budgets (monthly recurring, effective-dated)

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-20
"""
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE budgets (
          user_id        UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          category       TEXT NOT NULL,
          amount         NUMERIC(14,0) NULL,
          effective_from TEXT NOT NULL,
          updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
          PRIMARY KEY (user_id, category, effective_from)
        );
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS budgets;")
