"""Very simple keyword → category mapping for W1.

W2 will replace this with a proper rulebook + LLM fallback.
"""

# 순서 의미 있음 (위에서부터 첫 매칭). 모두 lowercase로 비교.
_RULES: list[tuple[tuple[str, ...], str]] = [
    (("스타벅스", "이디야", "투썸", "할리스", "starbucks", "coffee bean"), "coffee"),
    (("김밥천국", "맘스터치", "롯데리아", "맥도날드", "버거킹", "쉐이크쉑"), "lunch"),
    (("BBQ", "교촌", "굽네", "푸라닭", "야식", "치킨"), "snack_late"),
    (("이마트", "EMART", "홈플러스", "롯데마트", "코스트코"), "groceries"),
    (("CGV", "메가박스", "롯데시네마", "예스24", "교보문고", "올리브영"), "entertainment"),
    (("스마일클럽", "넷플릭스", "유튜브", "쿠팡플레이", "왓챠", "디즈니"), "subscription"),
    (("KT", "SKT", "LGU"), "telecom"),
    (("티머니", "T머니", "캐시비", "교통"), "transport"),
]


def classify(merchant_raw: str) -> str:
    if not merchant_raw:
        return "unknown"
    text = merchant_raw.lower()
    for keywords, category in _RULES:
        for kw in keywords:
            if kw.lower() in text:
                return category
    return "unknown"
