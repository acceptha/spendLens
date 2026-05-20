"""add user category override

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-20
"""
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE transactions ADD COLUMN user_category_override TEXT NULL;")


def downgrade() -> None:
    op.execute("ALTER TABLE transactions DROP COLUMN user_category_override;")
