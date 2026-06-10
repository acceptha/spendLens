from uuid import uuid4

import pytest

from app.insights import service
from app.insights.llm import InsightError


async def _user(conn):
    row = await conn.fetchrow(
        "INSERT INTO users (email, password_hash) VALUES ($1,'x') RETURNING id",
        f"_w4-isvc-{uuid4()}@example.com",
    )
    return row["id"]


async def test_get_cached_returns_none_when_absent(test_db_pool):
    async with test_db_pool.acquire() as conn:
        uid = await _user(conn)
        result = await service.get_cached(conn, uid, "2026-05")
    assert result is None


async def test_generate_caches_and_get_cached_returns(test_db_pool, monkeypatch):
    monkeypatch.setattr("app.insights.service.budget.has_room", _async_true)
    monkeypatch.setattr("app.insights.service.llm.generate_insight", _fake_generate)
    monkeypatch.setattr("app.insights.service.budget.record_usage", _async_noop)

    async with test_db_pool.acquire() as conn:
        uid = await _user(conn)
        out = await service.generate(conn, uid, "2026-05", force=False)
        assert out["summary"] == "요약"
        cached = await service.get_cached(conn, uid, "2026-05")
        assert cached is not None
        assert cached["month"] == "2026-05"


async def test_generate_budget_exceeded_raises(test_db_pool, monkeypatch):
    monkeypatch.setattr("app.insights.service.budget.has_room", _async_false)
    async with test_db_pool.acquire() as conn:
        uid = await _user(conn)
        with pytest.raises(service.BudgetExceeded):
            await service.generate(conn, uid, "2026-05", force=False)


async def _async_true():
    return True


async def _async_false():
    return False


async def _async_noop(**kwargs):
    return None


async def _fake_generate(aggregates):
    from app.insights.llm import Usage
    return (
        {"summary": "요약", "highlights": [{"type": "saving_tip", "title": "t", "detail": "d"}]},
        Usage(input_tokens=10, output_tokens=5),
    )
