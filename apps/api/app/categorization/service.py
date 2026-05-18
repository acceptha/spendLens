"""카테고리 분류 오케스트레이터.

흐름: rulebook → redis cache → (Phase 5에서 LLM 추가) → unknown
"""
from app.categorization import budget, cache, rulebook


async def classify(merchant_raw: str) -> str:
    # 1. 룰북
    cat = rulebook.match(merchant_raw)
    if cat is not None:
        return cat

    # 2. Redis 캐시
    cached = await cache.get(merchant_raw)
    if cached is not None:
        return cached

    # 3. 예산 체크 (Phase 5에서 LLM 호출 게이트로 사용)
    if not await budget.has_room():
        return "unknown"

    # 4. LLM 호출 — Phase 5에서 추가. 현 시점에는 unknown.
    return "unknown"
