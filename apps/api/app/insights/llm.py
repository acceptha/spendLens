"""Claude Haiku 월간 인사이트 생성.

집계 수치를 받아 구조화 JSON(summary + highlights) 반환.
파싱/검증 실패 시 InsightError — 호출자(service)가 502로 변환.
"""
import json
from dataclasses import dataclass

import anthropic

from app.categorization.budget import HAIKU_MODEL_ID
from app.settings import settings


class InsightError(Exception):
    """LLM 호출/파싱/검증 실패."""


@dataclass
class Usage:
    input_tokens: int
    output_tokens: int


_ALLOWED_TYPES = {"top_growth", "anomaly", "saving_tip"}

_SYSTEM = (
    "당신은 한국 가계부의 월간 지출 데이터를 보고 인사이트를 만드는 분석가입니다. "
    "반드시 JSON만 응답하세요. 형식: "
    '{"summary": "<한 문장 요약>", "highlights": [{"type": "top_growth|anomaly|saving_tip", '
    '"title": "<짧은 제목>", "detail": "<구체 설명>"}]}. '
    "highlights는 1~3개. type은 top_growth(가장 늘어난 카테고리), "
    "anomaly(이상 지출), saving_tip(절약 제안) 중 하나. 다른 문자 없이 JSON만."
)


def _client() -> anthropic.AsyncAnthropic:
    """Factory — tests monkeypatch this to inject mock."""
    return anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)


def _validate(parsed: object) -> dict:
    if not isinstance(parsed, dict):
        raise InsightError("expected JSON object")
    if "summary" not in parsed or "highlights" not in parsed:
        raise InsightError("missing summary/highlights")
    if not isinstance(parsed["highlights"], list):
        raise InsightError("highlights must be a list")
    for h in parsed["highlights"]:
        if not isinstance(h, dict) or h.get("type") not in _ALLOWED_TYPES:
            raise InsightError(f"invalid highlight: {h!r}")
        if "title" not in h or "detail" not in h:
            raise InsightError("highlight missing title/detail")
    return parsed


async def generate_insight(aggregates: dict) -> tuple[dict, Usage]:
    client = _client()
    user_content = (
        f"다음은 {aggregates.get('month')} 월 지출 집계입니다(JSON). "
        f"이를 바탕으로 인사이트를 생성하세요.\n{json.dumps(aggregates, ensure_ascii=False, default=str)}"
    )
    msg = await client.messages.create(
        model=HAIKU_MODEL_ID,
        max_tokens=512,
        system=_SYSTEM,
        messages=[{"role": "user", "content": user_content}],
    )
    text = "".join(block.text for block in msg.content if hasattr(block, "text"))
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise InsightError(f"non-JSON response: {text[:200]}") from exc

    validated = _validate(parsed)
    return validated, Usage(
        input_tokens=msg.usage.input_tokens,
        output_tokens=msg.usage.output_tokens,
    )
