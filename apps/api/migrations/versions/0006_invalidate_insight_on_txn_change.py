"""invalidate cached monthly insight when that month's transactions change

monthly_insights는 생성 시점의 집계로 고정된 캐시라, 이후 업로드·삭제·카테고리/필수
수정이 있으면 대시보드 수치와 어긋난 인사이트가 계속 보였다. 거래가 바뀌는 모든
경로를 한곳에서 잡도록 트리거로 해당 (user, 월) 캐시를 지운다 → 다음 조회 시
"생성" 상태가 되고 새로 만들면 최신 집계를 쓴다.

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-19
"""
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION invalidate_monthly_insight() RETURNS trigger AS $$
        BEGIN
          IF TG_OP IN ('UPDATE', 'DELETE') THEN
            DELETE FROM monthly_insights
            WHERE user_id = OLD.user_id AND month = to_char(OLD.txn_date, 'YYYY-MM');
          END IF;
          IF TG_OP IN ('INSERT', 'UPDATE') THEN
            DELETE FROM monthly_insights
            WHERE user_id = NEW.user_id AND month = to_char(NEW.txn_date, 'YYYY-MM');
          END IF;
          RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER transactions_invalidate_insight
        AFTER INSERT OR DELETE OR UPDATE OF
          txn_date, amount, category, user_category_override, essential_override, user_id
        ON transactions
        FOR EACH ROW EXECUTE FUNCTION invalidate_monthly_insight();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS transactions_invalidate_insight ON transactions;")
    op.execute("DROP FUNCTION IF EXISTS invalidate_monthly_insight();")
