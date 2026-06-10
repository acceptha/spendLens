"""add essential_override and monthly_insights

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-10
"""
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE transactions ADD COLUMN essential_override BOOLEAN NULL;")
    op.execute(
        """
        CREATE TABLE monthly_insights (
          user_id      UUID NOT NULL REFERENCES users(id),
          month        TEXT NOT NULL,
          payload      JSONB NOT NULL,
          generated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          PRIMARY KEY (user_id, month)
        );
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE monthly_insights;")
    op.execute("ALTER TABLE transactions DROP COLUMN essential_override;")
