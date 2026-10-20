import datetime
from uuid import uuid4

import httpx
import pytest
from httpx import ASGITransport

from app.budgets import service
from app.main import app


@pytest.fixture
def today(monkeypatch):
    """오늘을 2026-10-20(KST)로 고정. current_month()도 이 값을 따른다."""
    holder = {"d": datetime.date(2026, 10, 20)}
    monkeypatch.setattr(service, "today_kst", lambda: holder["d"])
    return holder


async def _client():
    return httpx.AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    )


async def _signup(ac):
    email = f"_bud-{uuid4()}@example.com"
    r = await ac.post("/auth/signup", json={"email": email, "password": "abcd1234"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}, email


async def _txn(pool, email, d, amount, category="etc", override=None):
    async with pool.acquire() as conn:
        uid = await conn.fetchval("SELECT id FROM users WHERE email=$1", email)
        await conn.execute(
            "INSERT INTO transactions (user_id, source_type, txn_date, amount, merchant_raw, "
            "category, user_category_override, dedup_hash, raw_row) "
            "VALUES ($1,'test',$2,$3,'M',$4,$5,$6,'{}'::jsonb)",
            uid, datetime.date.fromisoformat(d), amount, category, override, str(uuid4()))


async def test_status_empty_without_budgets(test_db_pool, today):
    async with await _client() as ac:
        h, _ = await _signup(ac)
        r = await ac.get("/budgets/status?month=2026-10", headers=h)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["items"] == []
        assert (body["is_current"], body["days_elapsed"], body["days_in_month"]) == (True, 20, 31)


async def test_set_and_status_with_projection_and_levels(test_db_pool, today):
    async with await _client() as ac:
        h, email = await _signup(ac)
        await _txn(test_db_pool, email, "2026-10-05", 62000, "coffee")
        await _txn(test_db_pool, email, "2026-10-06", 10000, "shopping")
        await _txn(test_db_pool, email, "2026-10-07", 500000, "transfer")  # 지출 제외
        for cat, amt in (("_total", 300000), ("coffee", 50000), ("shopping", 100000)):
            assert (await ac.put("/budgets", headers=h,
                                 json={"category": cat, "amount": amt})).status_code == 204

        items = (await ac.get("/budgets/status?month=2026-10", headers=h)).json()["items"]
        by = {i["category"]: i for i in items}
        assert items[0]["category"] == "_total"
        assert float(by["_total"]["spent"]) == 72000
        assert float(by["_total"]["projected"]) == 111600  # 72000/20*31
        assert by["_total"]["level"] == "ok"
        assert by["coffee"]["level"] == "over"
        assert by["coffee"]["ratio"] == 1.24
        # NUMERIC 값이 지수 표기("5E+4")가 아니라 정수 문자열로 나가야 한다
        assert by["coffee"]["budget"] == "50000"
        assert by["_total"]["budget"] == "300000"
        assert float(by["shopping"]["spent"]) == 10000
        assert [i["category"] for i in items] == ["_total", "coffee", "shopping"]


async def test_spent_matches_dashboard_rules(test_db_pool, today):
    async with await _client() as ac:
        h, email = await _signup(ac)
        await _txn(test_db_pool, email, "2026-10-01", 30000, "etc", override="coffee")
        await _txn(test_db_pool, email, "2026-10-02", 20000, "transfer", override="shopping")
        await _txn(test_db_pool, email, "2026-10-03", 40000, "savings")
        await _txn(test_db_pool, email, "2026-10-04", -100000, "income")
        await ac.put("/budgets", headers=h, json={"category": "_total", "amount": 100000})
        await ac.put("/budgets", headers=h, json={"category": "coffee", "amount": 100000})

        items = {i["category"]: i for i in
                 (await ac.get("/budgets/status?month=2026-10", headers=h)).json()["items"]}
        summary = (await ac.get("/dashboard/summary?month=2026-10", headers=h)).json()
        by_cat = {c["category"]: c for c in
                  (await ac.get("/dashboard/by-category?month=2026-10", headers=h)).json()}
        assert float(items["_total"]["spent"]) == float(summary["total_amount"]) == 50000
        assert float(items["coffee"]["spent"]) == float(by_cat["coffee"]["amount"]) == 30000


async def test_change_applies_from_this_month_and_keeps_past(test_db_pool, today):
    async with await _client() as ac:
        h, _ = await _signup(ac)
        today["d"] = datetime.date(2026, 9, 10)
        await ac.put("/budgets", headers=h, json={"category": "coffee", "amount": 50000})
        today["d"] = datetime.date(2026, 10, 20)
        await ac.put("/budgets", headers=h, json={"category": "coffee", "amount": 80000})
        await ac.put("/budgets", headers=h, json={"category": "coffee", "amount": 70000})

        sep = (await ac.get("/budgets/status?month=2026-09", headers=h)).json()
        octo = (await ac.get("/budgets/status?month=2026-10", headers=h)).json()
        assert float(sep["items"][0]["budget"]) == 50000
        assert sep["items"][0]["projected"] is None
        assert float(octo["items"][0]["budget"]) == 70000  # 같은 달 재저장 = 덮어쓰기


async def test_clear_budget_from_this_month_only(test_db_pool, today):
    async with await _client() as ac:
        h, _ = await _signup(ac)
        today["d"] = datetime.date(2026, 9, 10)
        await ac.put("/budgets", headers=h, json={"category": "coffee", "amount": 50000})
        today["d"] = datetime.date(2026, 10, 20)
        r = await ac.put("/budgets", headers=h, json={"category": "coffee", "amount": None})
        assert r.status_code == 204
        assert (await ac.get("/budgets/status?month=2026-10", headers=h)).json()["items"] == []
        assert len((await ac.get("/budgets/status?month=2026-09", headers=h)).json()["items"]) == 1


async def test_users_are_isolated(test_db_pool, today):
    async with await _client() as ac:
        h1, _ = await _signup(ac)
        h2, _ = await _signup(ac)
        await ac.put("/budgets", headers=h1, json={"category": "_total", "amount": 100000})
        assert (await ac.get("/budgets/status?month=2026-10", headers=h2)).json()["items"] == []


@pytest.mark.parametrize("category", ["income", "transfer", "savings", "nope"])
async def test_invalid_category_400(test_db_pool, today, category):
    async with await _client() as ac:
        h, _ = await _signup(ac)
        r = await ac.put("/budgets", headers=h, json={"category": category, "amount": 1000})
        assert r.status_code == 400
        assert r.json()["detail"] == "INVALID_CATEGORY"


@pytest.mark.parametrize("amount", [0, -5, 10**12])
async def test_invalid_amount_422(test_db_pool, today, amount):
    async with await _client() as ac:
        h, _ = await _signup(ac)
        r = await ac.put("/budgets", headers=h, json={"category": "coffee", "amount": amount})
        assert r.status_code == 422


async def test_invalid_month_400_and_auth_required(test_db_pool, today):
    async with await _client() as ac:
        h, _ = await _signup(ac)
        r = await ac.get("/budgets/status?month=2026-1", headers=h)
        assert r.status_code == 400
        assert r.json()["detail"] == "INVALID_MONTH_FORMAT"
        assert (await ac.get("/budgets/status?month=2026-10")).status_code == 401
        r = await ac.put("/budgets", json={"category": "coffee", "amount": 1})
        assert r.status_code == 401


async def test_first_budget_applies_back_to_earliest_data_month(test_db_pool, today):
    # 명세서는 월이 지난 뒤 올리므로, 처음 정한 예산은 이미 올라온 과거 달에도 보여야 한다.
    async with await _client() as ac:
        h, email = await _signup(ac)
        await _txn(test_db_pool, email, "2026-08-15", 30000, "coffee")
        await ac.put("/budgets", headers=h, json={"category": "coffee", "amount": 50000})

        for m in ("2026-08", "2026-09", "2026-10"):
            items = (await ac.get(f"/budgets/status?month={m}", headers=h)).json()["items"]
            assert [float(i["budget"]) for i in items] == [50000], m
        assert (await ac.get("/budgets/status?month=2026-07", headers=h)).json()["items"] == []

        # 이후 변경은 이번 달부터 — 과거 달은 첫 예산 그대로
        await ac.put("/budgets", headers=h, json={"category": "coffee", "amount": 70000})
        aug = (await ac.get("/budgets/status?month=2026-08", headers=h)).json()["items"]
        octo = (await ac.get("/budgets/status?month=2026-10", headers=h)).json()["items"]
        assert float(aug[0]["budget"]) == 50000
        assert float(octo[0]["budget"]) == 70000


async def test_retroactive_start_is_per_category(test_db_pool, today):
    async with await _client() as ac:
        h, email = await _signup(ac)
        await _txn(test_db_pool, email, "2026-08-15", 30000, "coffee")
        await ac.put("/budgets", headers=h, json={"category": "_total", "amount": 500000})
        # 나중에 처음 추가하는 카테고리도 첫 예산이므로 과거 달까지 적용
        await ac.put("/budgets", headers=h, json={"category": "coffee", "amount": 50000})
        cats = [i["category"] for i in
                (await ac.get("/budgets/status?month=2026-08", headers=h)).json()["items"]]
        assert cats == ["_total", "coffee"]


async def test_reenabling_after_clear_starts_this_month(test_db_pool, today):
    async with await _client() as ac:
        h, email = await _signup(ac)
        await _txn(test_db_pool, email, "2026-08-15", 30000, "coffee")
        await ac.put("/budgets", headers=h, json={"category": "coffee", "amount": 50000})
        await ac.put("/budgets", headers=h, json={"category": "coffee", "amount": None})
        await ac.put("/budgets", headers=h, json={"category": "coffee", "amount": 60000})
        aug = (await ac.get("/budgets/status?month=2026-08", headers=h)).json()["items"]
        octo = (await ac.get("/budgets/status?month=2026-10", headers=h)).json()["items"]
        # 첫 기록은 그대로 — 같은 달 해제·재설정은 이번 달 행만 덮어쓴다
        assert float(aug[0]["budget"]) == 50000
        assert float(octo[0]["budget"]) == 60000
