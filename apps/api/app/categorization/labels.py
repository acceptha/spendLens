"""카테고리 키 → 한글 표시 라벨. 사용자에게 보이는 문구(룰 인사이트 등)에 사용.

키는 rulebook/essential과 동기화. 프론트 apps/web/src/lib/categories.ts와 같은 값.
"""
CATEGORY_LABELS: dict[str, str] = {
    "housing": "주거",
    "utilities": "공과금",
    "telecom": "통신",
    "groceries": "장보기",
    "health": "의료",
    "insurance": "보험",
    "transport": "교통",
    "lunch": "점심",
    "dinner": "저녁",
    "coffee": "커피",
    "snack_late": "간식·야식",
    "subscription": "구독",
    "entertainment": "여가",
    "shopping": "쇼핑",
    "savings": "저축",
    "income": "수입",
    "transfer": "이체",
    "etc": "기타",
    "unknown": "미분류",
}


def category_label(key: str) -> str:
    return CATEGORY_LABELS.get(key, key)
