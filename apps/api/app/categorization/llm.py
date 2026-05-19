"""Claude Haiku 카테고리 분류 호출.

응답을 14개 enum 안으로 강제. enum 밖이면 'unknown'으로 대체.
JSON 응답 실패 시 LLMClassifyError raise — 호출자(service)가 'unknown'으로 폴백.
"""
import json
from dataclasses import dataclass

import anthropic

from app.categorization.budget import HAIKU_MODEL_ID
from app.categorization.rulebook import CATEGORIES
from app.settings import settings


class LLMClassifyError(Exception):
    """LLM 호출/파싱 실패. 호출자가 unknown으로 폴백."""


@dataclass
class Usage:
    input_tokens: int
    output_tokens: int


_SYSTEM = (
    "당신은 한국 카드 거래의 가맹점명을 보고 카테고리를 정해주는 분류기입니다. "
    "다음 14개 중 정확히 하나를 JSON으로 답하세요: "
    f"{', '.join(CATEGORIES)}. "
    '응답 형식: {"category": "<enum>"}. 다른 문자 없이 JSON만.'
)


def _client() -> anthropic.AsyncAnthropic:
    """Factory — tests monkeypatch this to inject mock."""
    return anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)


async def classify_one(merchant_raw: str) -> tuple[str, Usage]:
    client = _client()
    msg = await client.messages.create(
        model=HAIKU_MODEL_ID,
        max_tokens=64,
        system=_SYSTEM,
        messages=[{"role": "user", "content": f"가맹점명: {merchant_raw}"}],
    )

    text = "".join(block.text for block in msg.content if hasattr(block, "text"))

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LLMClassifyError(f"non-JSON response: {text[:200]}") from exc

    if not isinstance(parsed, dict):
        raise LLMClassifyError(f"expected JSON object, got: {type(parsed).__name__}")

    cat = parsed.get("category", "unknown")
    if cat not in CATEGORIES:
        cat = "unknown"

    return cat, Usage(
        input_tokens=msg.usage.input_tokens,
        output_tokens=msg.usage.output_tokens,
    )
