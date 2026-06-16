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
    email = f"_w4-iroute-{uuid4()}@example.com"
    r = await ac.post("/auth/signup", json={"email": email, "password": "abcd1234"})
    return r.json()["access_token"], email


def _patch_llm(monkeypatch):
    from app.insights.llm import Usage

    async def fake(aggregates):
        return (
            {
                "summary": "요약",
                "highlights": [{"type": "saving_tip", "title": "t", "detail": "d"}],
            },
            Usage(input_tokens=10, output_tokens=5),
        )

    async def room():
        return True

    async def noop(**kwargs):
        return None

    monkeypatch.setattr("app.insights.service.llm.generate_insight", fake)
    monkeypatch.setattr("app.insights.service.budget.has_room", room)
    monkeypatch.setattr("app.insights.service.budget.record_usage", noop)


async def test_get_insights_returns_null_when_absent(test_db_pool):
    async with await _client() as ac:
        token, _ = await _signup(ac)
        r = await ac.get("/insights?month=2026-05",
                         headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json() is None


async def test_generate_then_get(test_db_pool, monkeypatch):
    _patch_llm(monkeypatch)
    async with await _client() as ac:
        token, _ = await _signup(ac)
        p = await ac.post("/insights/generate", json={"month": "2026-05"},
                          headers={"Authorization": f"Bearer {token}"})
        assert p.status_code == 200, p.text
        assert p.json()["summary"] == "요약"

        g = await ac.get("/insights?month=2026-05",
                         headers={"Authorization": f"Bearer {token}"})
        assert g.json()["highlights"][0]["type"] == "saving_tip"


async def test_generate_budget_exceeded_503(test_db_pool, monkeypatch):
    async def no_room():
        return False
    monkeypatch.setattr("app.insights.service.budget.has_room", no_room)
    async with await _client() as ac:
        token, _ = await _signup(ac)
        r = await ac.post("/insights/generate", json={"month": "2026-05"},
                          headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 503
        assert r.json()["detail"] == "BUDGET_EXCEEDED"


async def test_generate_llm_failure_502(test_db_pool, monkeypatch):
    from app.insights.llm import InsightError

    async def boom(aggregates):
        raise InsightError("bad")
    async def room():
        return True
    monkeypatch.setattr("app.insights.service.llm.generate_insight", boom)
    monkeypatch.setattr("app.insights.service.budget.has_room", room)
    async with await _client() as ac:
        token, _ = await _signup(ac)
        r = await ac.post("/insights/generate", json={"month": "2026-05"},
                          headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 502
        assert r.json()["detail"] == "INSIGHT_GENERATION_FAILED"
