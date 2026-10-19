import datetime
from uuid import uuid4

import httpx
from httpx import ASGITransport

from app.main import app


async def _client():
    return httpx.AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    )


async def _signup(ac):
    email = f"_w4-cf-{uuid4()}@example.com"
    r = await ac.post("/auth/signup", json={"email": email, "password": "abcd1234"})
    return r.json()["access_token"], email


async def _ins(conn, email, *, d, amount, category="etc"):
    u = await conn.fetchrow("SELECT id FROM users WHERE email=$1", email)
    await conn.execute(
        "INSERT INTO transactions (user_id, source_type, txn_date, amount, merchant_raw, "
        "category, dedup_hash, raw_row) "
        "VALUES ($1,'test',$2,$3,'M',$4,$5,'{}'::jsonb)",
        u["id"], datetime.date.fromisoformat(d), amount, category, str(uuid4()))


async def test_cashflow_excludes_transfer_savings_from_expense(test_db_pool):
    async with await _client() as ac:
        token, email = await _signup(ac)
        async with test_db_pool.acquire() as conn:
            this_month = datetime.date.today().strftime("%Y-%m")
            d = f"{this_month}-05"
            await _ins(conn, email, d=d, amount=20000, category="etc")       # 지출
            await _ins(conn, email, d=d, amount=50000, category="transfer")  # 제외
            await _ins(conn, email, d=d, amount=30000, category="savings")   # 제외

        r = await ac.get("/dashboard/cashflow-by-month?last_n=6",
                         headers={"Authorization": f"Bearer {token}"})
        cur = {row["month"]: row for row in r.json()}[this_month]
        assert float(cur["expense"]) == 20000


async def test_cashflow_by_month_splits_expense_income(test_db_pool):
    async with await _client() as ac:
        token, email = await _signup(ac)
        async with test_db_pool.acquire() as conn:
            this_month = datetime.date.today().strftime("%Y-%m")
            d = f"{this_month}-05"
            await _ins(conn, email, d=d, amount=20000, category="etc")     # 지출
            await _ins(conn, email, d=d, amount=-80000, category="income") # 수입
            await _ins(conn, email, d=d, amount=-30000, category="transfer") # 이체 제외

        r = await ac.get("/dashboard/cashflow-by-month?last_n=6",
                         headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200, r.text
        rows = {row["month"]: row for row in r.json()}
        cur = rows[this_month]
        assert float(cur["expense"]) == 20000
        assert float(cur["income"]) == 80000   # 이체 제외


async def test_cashflow_invalid_last_n_400(test_db_pool):
    async with await _client() as ac:
        token, _ = await _signup(ac)
        r = await ac.get("/dashboard/cashflow-by-month?last_n=99",
                         headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 400


async def test_cashflow_anchors_to_latest_data_month_and_fills_gaps(test_db_pool):
    # 오래된 명세서만 올린 경우에도(오늘 기준 6개월 밖) 추세가 보여야 하고, 빈 달은 0으로 채운다.
    async with await _client() as ac:
        token, email = await _signup(ac)
        async with test_db_pool.acquire() as conn:
            await _ins(conn, email, d="2024-01-10", amount=10000)
            await _ins(conn, email, d="2024-03-10", amount=30000)

        r = await ac.get("/dashboard/cashflow-by-month?last_n=6",
                         headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200, r.text
        rows = r.json()
        assert [row["month"] for row in rows] == ["2024-01", "2024-02", "2024-03"]
        assert [float(row["expense"]) for row in rows] == [10000, 0, 30000]


async def test_cashflow_window_is_last_n_months_ending_at_latest(test_db_pool):
    async with await _client() as ac:
        token, email = await _signup(ac)
        async with test_db_pool.acquire() as conn:
            for m in range(1, 11):  # 2024-01 ~ 2024-10
                await _ins(conn, email, d=f"2024-{m:02d}-15", amount=1000 * m)

        r = await ac.get("/dashboard/cashflow-by-month?last_n=3",
                         headers={"Authorization": f"Bearer {token}"})
        assert [row["month"] for row in r.json()] == ["2024-08", "2024-09", "2024-10"]


async def test_cashflow_empty_for_user_without_transactions(test_db_pool):
    async with await _client() as ac:
        token, _ = await _signup(ac)
        r = await ac.get("/dashboard/cashflow-by-month?last_n=6",
                         headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json() == []
