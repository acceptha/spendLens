"""카테고리 → 필수/비필수 기본 매핑.

essential은 저장하지 않고 effective_category에서 파생한다. 단일 진실 공급원.
사용자가 명시 토글하면 transactions.essential_override가 우선한다.
CATEGORIES(rulebook)와 키 동기화 유지.
"""
ESSENTIAL_DEFAULTS: dict[str, bool] = {
    "housing": True,
    "utilities": True,
    "telecom": True,
    "groceries": True,
    "health": True,
    "insurance": True,
    "transport": True,
    "lunch": True,
    "dinner": True,
    "savings": True,
    "income": True,
    "transfer": True,
    "coffee": False,
    "snack_late": False,
    "subscription": False,
    "entertainment": False,
    "shopping": False,
    "etc": False,
    "unknown": False,
}

ESSENTIAL_CATEGORIES: tuple[str, ...] = tuple(
    c for c, v in ESSENTIAL_DEFAULTS.items() if v
)

# 소비(consumption)로 보기 어려운 카테고리 — 필수/비필수 지출 분석에서 제외한다.
# transfer(계좌 이체)는 저축성/지출성이 섞여 있어 라벨 없이는 성격 불명이고,
# savings(저축)는 지출이 아니라 이연된 자금이다. 사용자가 이체를 실제 지출
# 카테고리로 재분류하면 effective_category가 바뀌어 자연히 집계에 포함된다.
NON_SPENDING_CATEGORIES: tuple[str, ...] = ("transfer", "savings")
