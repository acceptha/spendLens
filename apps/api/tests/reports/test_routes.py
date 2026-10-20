import datetime
from uuid import uuid4

import httpx
import pytest
from httpx import ASGITransport

from app.budgets import service as budgets
from app.insights import service as insights
from app.main import app


@pytest.fixture(autouse=True)
def today(monkeypatch):
    monkeypatch.setattr(budgets, "today_kst", lambda: datetime.date(2026, 10, 20))


async def _client():
    return httpx.AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    )


async def _signup(ac):
    email = f"_rep-{uuid4()}@example.com"
    r = await ac.post("/auth/signup", json={"email": email, "password": "abcd1234"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}, email


async def _txn(pool, email, d, amount, category="etc"):
    async with pool.acquire() as conn:
        uid = await conn.fetchval("SELECT id FROM users WHERE email=$1", email)
        await conn.execute(
            "INSERT INTO transactions (user_id, source_type, txn_date, amount, merchant_raw, "
            "category, dedup_hash, raw_row) VALUES ($1,'test',$2,$3,'M',$4,$5,'{}'::jsonb)",
            uid, datetime.date.fromisoformat(d), amount, category, str(uuid4()))


async def _seed(pool, email):
    await _txn(pool, email, "2026-08-05", 30000, "coffee")
    await _txn(pool, email, "2026-08-06", 55000, "shopping")
    await _txn(pool, email, "2026-09-05", 62000, "coffee")
    await _txn(pool, email, "2026-09-06", 10000, "shopping")
    await _txn(pool, email, "2026-09-07", 500000, "transfer")   # 지출 제외
    await _txn(pool, email, "2026-09-25", -3000000, "income")
    await _txn(pool, email, "2026-10-02", 4500, "coffee")


async def test_empty_user_returns_null_month(test_db_pool):
    async with await _client() as ac:
        h, _ = await _signup(ac)
        r = await ac.get("/reports/monthly", headers=h)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["month"] is None and body["available_months"] == []
        assert body["summary"] is None and body["insight"] is None


async def test_default_month_is_last_closed_month_and_matches_dashboard(test_db_pool):
    async with await _client() as ac:
        h, email = await _signup(ac)
        await _seed(test_db_pool, email)
        body = (await ac.get("/reports/monthly", headers=h)).json()
        assert body["month"] == "2026-09"
        assert body["available_months"] == ["2026-10", "2026-09", "2026-08"]

        dash = (await ac.get("/dashboard/summary?month=2026-09", headers=h)).json()
        s = body["summary"]
        assert float(s["spent"]) == float(dash["total_amount"]) == 72000
        assert float(s["income"]) == 3000000
        assert s["prev_month"] == "2026-08" and float(s["prev_spent"]) == 85000

        assert [c["category"] for c in body["top_categories"]] == ["coffee", "shopping"]
        changes = body["category_changes"]
        assert [(c["category"], float(c["diff"])) for c in changes["increased"]] == [
            ("coffee", 32000)]
        assert [(c["category"], float(c["diff"])) for c in changes["decreased"]] == [
            ("shopping", -45000)]


async def test_budget_scorecard(test_db_pool):
    async with await _client() as ac:
        h, email = await _signup(ac)
        await _seed(test_db_pool, email)
        assert (await ac.get("/reports/monthly?month=2026-09", headers=h)).json()["budget"] is None

        # 첫 예산은 가장 오래된 거래 월부터 소급 → 9월 결산에 반영
        await ac.put("/budgets", headers=h, json={"category": "_total", "amount": 100000})
        await ac.put("/budgets", headers=h, json={"category": "coffee", "amount": 50000})
        budget = (await ac.get("/reports/monthly?month=2026-09", headers=h)).json()["budget"]
        assert (budget["total"], budget["kept"], budget["over"]) == (2, 1, 1)
        assert {i["category"]: i["level"] for i in budget["items"]}["coffee"] == "over"


async def test_insight_is_generated_once_and_reused(test_db_pool):
    async with await _client() as ac:
        h, email = await _signup(ac)
        await _seed(test_db_pool, email)
        first = (await ac.get("/reports/monthly?month=2026-09", headers=h)).json()["insight"]
        assert first and first["summary"]
        second = (await ac.get("/reports/monthly?month=2026-09", headers=h)).json()["insight"]
        assert second["generated_at"] == first["generated_at"]


async def test_insight_failure_still_returns_report(test_db_pool, monkeypatch):
    async def boom(*args, **kwargs):
        raise insights.BudgetExceededError()

    monkeypatch.setattr(insights, "generate", boom)
    async with await _client() as ac:
        h, email = await _signup(ac)
        await _seed(test_db_pool, email)
        r = await ac.get("/reports/monthly?month=2026-09", headers=h)
        assert r.status_code == 200
        assert r.json()["insight"] is None
        assert float(r.json()["summary"]["spent"]) == 72000


async def test_isolation_and_errors(test_db_pool):
    async with await _client() as ac:
        _, e1 = await _signup(ac)
        h2, _ = await _signup(ac)
        await _seed(test_db_pool, e1)
        assert (await ac.get("/reports/monthly", headers=h2)).json()["month"] is None
        r = await ac.get("/reports/monthly?month=2026-9", headers=h2)
        assert r.status_code == 400 and r.json()["detail"] == "INVALID_MONTH_FORMAT"
        assert (await ac.get("/reports/monthly")).status_code == 401
