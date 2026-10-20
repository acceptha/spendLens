"""계정 삭제 시 사용자 데이터가 모두 함께 지워져야 한다.

migration 0008에서 monthly_insights FK에 ON DELETE CASCADE 추가.
"""
import datetime
from uuid import uuid4


async def test_deleting_user_removes_all_their_data(test_db_pool):
    async with test_db_pool.acquire() as conn:
        uid = await conn.fetchval(
            "INSERT INTO users (email, password_hash) VALUES ($1, 'x') RETURNING id",
            f"_del-{uuid4()}@example.com",
        )
        await conn.execute(
            "INSERT INTO transactions (user_id, source_type, txn_date, amount, merchant_raw, "
            "category, dedup_hash, raw_row) VALUES ($1,'test',$2,1000,'M','etc',$3,'{}'::jsonb)",
            uid, datetime.date(2026, 9, 1), str(uuid4()))
        # 트리거가 지우지 않도록 거래 삽입 뒤에 캐시 생성
        await conn.execute(
            "INSERT INTO monthly_insights (user_id, month, payload) VALUES ($1, '2026-09', '{}')",
            uid)
        await conn.execute(
            "INSERT INTO budgets (user_id, category, amount, effective_from) "
            "VALUES ($1, '_total', 1000, '2026-09')", uid)

        await conn.execute("DELETE FROM users WHERE id = $1", uid)

        for table in ("transactions", "monthly_insights", "budgets"):
            left = await conn.fetchval(f"SELECT count(*) FROM {table} WHERE user_id = $1", uid)  # noqa: S608
            assert left == 0, table
