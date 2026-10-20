"""remove QA account re-created by a post-deploy verification probe

0008 배포 후 삭제 확인을 위해 같은 이메일로 회원가입을 시도한 것이 빈 계정을 다시 만들었다.
0008과 같은 목록을 한 번 더 정리한다(해당 이메일이 없으면 무동작).

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-20
"""
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

QA_EMAILS = ("qa-w5-20260617@example.com", "qa-proxy-20261019@example.com")


def upgrade() -> None:
    emails = ", ".join(f"'{e}'" for e in QA_EMAILS)
    op.execute(f"DELETE FROM users WHERE email IN ({emails});")  # noqa: S608 — 고정 상수


def downgrade() -> None:
    pass
