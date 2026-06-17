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
