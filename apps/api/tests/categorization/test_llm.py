from unittest.mock import AsyncMock, MagicMock

import pytest

from app.categorization.llm import LLMClassifyError, classify_one


def _make_fake_client(category: str = "coffee", input_tokens: int = 120, output_tokens: int = 8):
    fake_msg = MagicMock()
    fake_msg.content = [MagicMock(text=f'{{"category": "{category}"}}')]
    fake_msg.usage = MagicMock(input_tokens=input_tokens, output_tokens=output_tokens)
    fake_client = MagicMock()
    fake_client.messages = MagicMock()
    fake_client.messages.create = AsyncMock(return_value=fake_msg)
    return fake_client


async def test_classify_one_returns_enum_value(monkeypatch):
    fake = _make_fake_client(category="coffee")
    monkeypatch.setattr("app.categorization.llm._client", lambda: fake)

    cat, usage = await classify_one("듣보잡 카페")
    assert cat == "coffee"
    assert usage.input_tokens == 120
    assert usage.output_tokens == 8


async def test_classify_one_enum_violation_returns_unknown(monkeypatch):
    fake = _make_fake_client(category="totally_invalid")
    monkeypatch.setattr("app.categorization.llm._client", lambda: fake)

    cat, _ = await classify_one("뭔가")
    assert cat == "unknown"


async def test_classify_one_non_dict_json_raises(monkeypatch):
    """JSON parse OK이지만 dict가 아닌 경우(e.g. list) — LLMClassifyError로 변환."""
    fake_msg = MagicMock()
    fake_msg.content = [MagicMock(text='["coffee"]')]
    fake_msg.usage = MagicMock(input_tokens=50, output_tokens=10)
    fake_client = MagicMock()
    fake_client.messages = MagicMock()
    fake_client.messages.create = AsyncMock(return_value=fake_msg)
    monkeypatch.setattr("app.categorization.llm._client", lambda: fake_client)

    with pytest.raises(LLMClassifyError, match="expected JSON object"):
        await classify_one("뭔가")


async def test_classify_one_malformed_json_raises(monkeypatch):
    fake_msg = MagicMock()
    fake_msg.content = [MagicMock(text="not json at all")]
    fake_msg.usage = MagicMock(input_tokens=50, output_tokens=10)
    fake_client = MagicMock()
    fake_client.messages = MagicMock()
    fake_client.messages.create = AsyncMock(return_value=fake_msg)
    monkeypatch.setattr("app.categorization.llm._client", lambda: fake_client)

    with pytest.raises(LLMClassifyError):
        await classify_one("뭔가")
