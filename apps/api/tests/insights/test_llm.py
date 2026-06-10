from unittest.mock import AsyncMock, MagicMock

import pytest

from app.insights.llm import InsightError, generate_insight


def _fake_client(text: str, input_tokens=300, output_tokens=120):
    msg = MagicMock()
    msg.content = [MagicMock(text=text)]
    msg.usage = MagicMock(input_tokens=input_tokens, output_tokens=output_tokens)
    client = MagicMock()
    client.messages = MagicMock()
    client.messages.create = AsyncMock(return_value=msg)
    return client


_VALID = (
    '{"summary": "이번 달 지출은 전월 대비 늘었습니다.",'
    ' "highlights": [{"type": "top_growth", "title": "커피 급증",'
    ' "detail": "전월 대비 2배"}]}'
)


async def test_generate_insight_parses_structured(monkeypatch):
    monkeypatch.setattr("app.insights.llm._client", lambda: _fake_client(_VALID))
    result, usage = await generate_insight({"month": "2026-05"})
    assert result["summary"].startswith("이번 달")
    assert result["highlights"][0]["type"] == "top_growth"
    assert usage.input_tokens == 300


async def test_generate_insight_malformed_json_raises(monkeypatch):
    monkeypatch.setattr("app.insights.llm._client", lambda: _fake_client("not json"))
    with pytest.raises(InsightError):
        await generate_insight({"month": "2026-05"})


async def test_generate_insight_missing_keys_raises(monkeypatch):
    monkeypatch.setattr("app.insights.llm._client", lambda: _fake_client('{"summary": "x"}'))
    with pytest.raises(InsightError):
        await generate_insight({"month": "2026-05"})
