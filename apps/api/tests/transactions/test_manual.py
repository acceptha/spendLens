"""현금 등 직접 입력 거래 — POST /transactions."""
import datetime
from uuid import uuid4

import httpx
import pytest
from httpx import ASGITransport

from app.main import app


async def _client():
    return httpx.AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    )


async def _signup(ac):
    email = f"_man-{uuid4()}@example.com"
    r = await ac.post("/auth/signup", json={"email": email, "password": "abcd1234"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}, email


def _body(**over):
    base = {"kind": "expense", "txn_date": "2026-10-05", "amount": 4500,
            "merchant": "  동네 분식  ", "category": "lunch"}
    base.update(over)
    return base


async def test_create_expense_returns_row_and_counts_as_spending(test_db_pool):
    async with await _client() as ac:
        h, _ = await _signup(ac)
        r = await ac.post("/transactions", headers=h, json=_body())
        assert r.status_code == 201, r.text
        row = r.json()
        assert (row["merchant_raw"], float(row["amount"]), row["effective_category"]) == (
            "동네 분식", 4500, "lunch")
        assert row["source_type"] == "manual"
        assert row["merchant_normalized"]

        listed = (await ac.get("/transactions?month=2026-10", headers=h)).json()
        assert [t["id"] for t in listed] == [row["id"]]
        summary = (await ac.get("/dashboard/summary?month=2026-10", headers=h)).json()
        assert float(summary["total_amount"]) == 4500


async def test_create_income_is_negative_and_defaults_to_income(test_db_pool):
    async with await _client() as ac:
        h, _ = await _signup(ac)
        r = await ac.post("/transactions", headers=h,
                          json=_body(kind="income", merchant="용돈", amount=50000, category=None))
        assert r.status_code == 201, r.text
        assert float(r.json()["amount"]) == -50000
        assert r.json()["effective_category"] == "income"
        summary = (await ac.get("/dashboard/summary?month=2026-10", headers=h)).json()
        assert float(summary["income_total"]) == 50000


async def test_expense_category_auto_uses_learned_override(test_db_pool):
    async with await _client() as ac:
        h, _ = await _signup(ac)
        first = (await ac.post("/transactions", headers=h,
                               json=_body(merchant="망원시장", category="etc"))).json()
        await ac.patch(f"/transactions/{first['id']}", headers=h, json={"category": "groceries"})
        second = await ac.post("/transactions", headers=h,
                               json=_body(merchant="망원시장", category=None))
        assert second.json()["effective_category"] == "groceries"


async def test_identical_manual_entries_are_both_kept(test_db_pool):
    async with await _client() as ac:
        h, _ = await _signup(ac)
        for _ in range(2):
            assert (await ac.post("/transactions", headers=h, json=_body())).status_code == 201
        assert len((await ac.get("/transactions?month=2026-10", headers=h)).json()) == 2


@pytest.mark.parametrize("over", [
    {"amount": 0}, {"amount": -1}, {"amount": 100_000_000},
    {"merchant": "   "}, {"merchant": "가" * 101}, {"kind": "refund"}, {"category": "nope"},
])
async def test_validation_422(test_db_pool, over):
    async with await _client() as ac:
        h, _ = await _signup(ac)
        assert (await ac.post("/transactions", headers=h, json=_body(**over))).status_code == 422


async def test_future_date_400_and_auth_required(test_db_pool):
    async with await _client() as ac:
        h, _ = await _signup(ac)
        future = (datetime.date.today() + datetime.timedelta(days=3)).isoformat()
        r = await ac.post("/transactions", headers=h, json=_body(txn_date=future))
        assert r.status_code == 400 and r.json()["detail"] == "FUTURE_DATE"
        assert (await ac.post("/transactions", json=_body())).status_code == 401


async def test_users_are_isolated(test_db_pool):
    async with await _client() as ac:
        h1, _ = await _signup(ac)
        h2, _ = await _signup(ac)
        await ac.post("/transactions", headers=h1, json=_body())
        assert (await ac.get("/transactions?month=2026-10", headers=h2)).json() == []
