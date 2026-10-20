"""monthly_insights FK ON DELETE CASCADE + remove QA test accounts from production

1) monthly_insights.user_id만 ON DELETE CASCADE가 없어, 인사이트가 있는 사용자는 삭제가
   막혔다. 다른 사용자 테이블(transactions·refresh_tokens·source_files·budgets)과 맞춘다.
2) 운영 QA 중 만든 테스트 계정 2개를 데이터와 함께 정리한다(사용자 요청, 2026-10-20).
   서버 SSH 없이 배포 경로로 실행하기 위한 일회성 정리. 해당 이메일이 없으면 아무 일도 없다.

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-20
"""
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

QA_EMAILS = ("qa-w5-20260617@example.com", "qa-proxy-20261019@example.com")


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE monthly_insights
          DROP CONSTRAINT monthly_insights_user_id_fkey,
          ADD CONSTRAINT monthly_insights_user_id_fkey
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
        """
    )
    # CASCADE로 거래·예산·인사이트·업로드 기록·refresh 토큰까지 함께 삭제된다.
    emails = ", ".join(f"'{e}'" for e in QA_EMAILS)
    op.execute(f"DELETE FROM users WHERE email IN ({emails});")  # noqa: S608 — 고정 상수


def downgrade() -> None:
    # 삭제한 QA 계정은 복구하지 않는다(필요 시 백업에서 복원).
    op.execute(
        """
        ALTER TABLE monthly_insights
          DROP CONSTRAINT monthly_insights_user_id_fkey,
          ADD CONSTRAINT monthly_insights_user_id_fkey
            FOREIGN KEY (user_id) REFERENCES users(id);
        """
    )
