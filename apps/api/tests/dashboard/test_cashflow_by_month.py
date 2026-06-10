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
        "INSERT INTO transactions (user_id, source_type, txn_date, amount, merchant_raw, category, dedup_hash, raw_row) "
        "VALUES ($1,'test',$2,$3,'M',$4,$5,'{}'::jsonb)",
        u["id"], datetime.date.fromisoformat(d), amount, category, str(uuid4()))


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
