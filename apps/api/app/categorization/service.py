"""카테고리 분류 오케스트레이터.

흐름: rulebook → redis cache → 예산 체크 → LLM → 캐시 저장 + 사용량 기록
LLM 호출/파싱 실패 시 silent fallback to "unknown" (업로드 흐름 안 끊김).
"""
import logging

from app.categorization import budget, cache, llm, rulebook

logger = logging.getLogger(__name__)


async def classify(merchant_raw: str) -> str:
    # 1. 룰북
    cat = rulebook.match(merchant_raw)
    if cat is not None:
        return cat

    # 2. Redis 캐시
    cached = await cache.get(merchant_raw)
    if cached is not None:
        return cached

    # 3. 예산 체크
    if not await budget.has_room():
        return "unknown"

    # 4. LLM 호출 — 어떤 실패든 silent fallback ("unknown") 으로 업로드 흐름 보호
    try:
        cat, usage = await llm.classify_one(merchant_raw)
    except Exception as exc:  # noqa: BLE001 — intentional broad catch
        logger.warning("LLM classify failed for merchant=%r: %s", merchant_raw, exc)
        return "unknown"

    # 5. 캐시 저장 → 사용량 기록 순서 (cache.set 실패 시 record_usage 안 함; 반대 순서면
    #    LLM 결과 재호출 위험 — 현재 순서가 best-effort MVP에 더 안전)
    await cache.set(merchant_raw, cat)
    await budget.record_usage(
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        merchant=cache.normalize_merchant(merchant_raw),
    )
    return cat
