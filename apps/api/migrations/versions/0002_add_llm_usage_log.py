"""add llm_usage_log

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-13
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE llm_usage_log (
          id                  BIGSERIAL PRIMARY KEY,
          called_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
          model               TEXT NOT NULL,
          input_tokens        INTEGER NOT NULL,
          output_tokens       INTEGER NOT NULL,
          cost_usd            NUMERIC(10, 6) NOT NULL,
          purpose             TEXT NOT NULL,
          merchant_normalized TEXT
        );
    """)
    op.execute("CREATE INDEX llm_usage_log_called_at_idx ON llm_usage_log (called_at);")


def downgrade() -> None:
    op.execute("DROP TABLE llm_usage_log;")
