"""가맹점명 정규화 — 지점 분산을 흡수해 브랜드 단위로 묶는다.

용도: transactions.merchant_normalized 저장, Top 가맹점 그룹핑,
LLM 캐시 키(브랜치 통일 → hit rate↑). 룰북 매칭은 raw를 그대로 쓴다.

전략: 대형 체인 별칭 테이블 우선 매칭 → 미매칭 시 휴리스틱(지점 토큰 제거).
"""
import re

# (정규식, 정식 브랜드명) — 위에서부터 첫 매칭. 지점 분산이 큰 체인 위주.
# 순서 주의: 더 구체적인 항목(이마트24)을 상위(이마트)보다 먼저 둔다.
_ALIASES: list[tuple[re.Pattern[str], str]] = [
    # 편의점
    (re.compile(r"씨유|\bCU\b|CU\s*\(", re.I), "CU"),
    (re.compile(r"GS\s*25|지에스25", re.I), "GS25"),
    (re.compile(r"세븐\s*일레븐|7[\s-]*eleven", re.I), "세븐일레븐"),
    (re.compile(r"이마트\s*24|emart\s*24", re.I), "이마트24"),
    (re.compile(r"미니스톱|ministop", re.I), "미니스톱"),
    # 카페
    (re.compile(r"스타벅스|starbucks", re.I), "스타벅스"),
    (re.compile(r"이디야|ediya", re.I), "이디야"),
    (re.compile(r"투썸|twosome", re.I), "투썸플레이스"),
    (re.compile(r"메가\s*(MGC)?\s*커피|mega\s*coffee", re.I), "메가커피"),
    (re.compile(r"컴포즈\s*커피|compose\s*coffee", re.I), "컴포즈커피"),
    (re.compile(r"빽다방", re.I), "빽다방"),
    (re.compile(r"할리스|hollys", re.I), "할리스"),
    (re.compile(r"커피빈|coffee\s*bean", re.I), "커피빈"),
    # 패스트푸드
    (re.compile(r"맥도날드|mcdonald", re.I), "맥도날드"),
    (re.compile(r"롯데리아", re.I), "롯데리아"),
    (re.compile(r"버거킹|burger\s*king", re.I), "버거킹"),
    (re.compile(r"맘스터치", re.I), "맘스터치"),
    (re.compile(r"서브웨이|subway", re.I), "서브웨이"),
    # 리테일
    (re.compile(r"이마트|\bemart\b", re.I), "이마트"),
    (re.compile(r"홈플러스|homeplus", re.I), "홈플러스"),
    (re.compile(r"롯데마트", re.I), "롯데마트"),
    (re.compile(r"코스트코|costco", re.I), "코스트코"),
    (re.compile(r"올리브영|oliveyoung", re.I), "올리브영"),
    (re.compile(r"다이소|daiso", re.I), "다이소"),
    # 베이커리
    (re.compile(r"파리바게(뜨|트)|paris\s*baguette", re.I), "파리바게뜨"),
    (re.compile(r"뚜레쥬르|tous\s*les\s*jours", re.I), "뚜레쥬르"),
]

_SUFFIX_PATTERNS = [
    re.compile(r"\(주\)|㈜|주식회사"),
    re.compile(r"\d+호점\s*$"),
    re.compile(r"[가-힣A-Za-z0-9]*점\s*$"),  # 끝의 지점 토큰(예: '강남점')
    re.compile(r"지점\s*$"),
]


def _is_cjk(s: str) -> bool:
    return any("가" <= ch <= "힣" for ch in s)


def normalize_merchant(raw: str) -> str:
    """가맹점명을 브랜드 단위 정규화명으로 변환. 매칭 실패 시 휴리스틱 결과."""
    text = (raw or "").strip()
    if not text:
        return ""

    for pat, canonical in _ALIASES:
        if pat.search(text):
            return canonical

    # 폴백 휴리스틱
    if not _is_cjk(text):
        text = text.lower()
    for pat in _SUFFIX_PATTERNS:
        text = pat.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()
    if _is_cjk(text):
        text = text.replace(" ", "")
    return text
