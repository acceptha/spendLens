"""키워드/정규식 기반 카테고리 룰북.

순서 의미 있음 (위에서부터 첫 매칭). 매칭 실패 시 None.
LLM 폴백은 service.py에서 처리.
"""
import re

CATEGORIES: tuple[str, ...] = (
    "coffee", "lunch", "dinner", "snack_late",
    "groceries", "transport", "telecom",
    "subscription", "entertainment", "health",
    "shopping", "utilities", "etc", "unknown",
    # W3 추가
    "savings", "insurance", "income", "transfer", "housing",
)

_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"스타벅스|이디야|투썸|할리스|커피빈|starbucks|coffee\s*bean", re.I), "coffee"),
    (re.compile(r"김밥천국|맘스터치|롯데리아|맥도날드|버거킹|쉐이크쉑|서브웨이", re.I), "lunch"),
    (re.compile(r"BBQ|교촌|굽네|푸라닭|치킨|피자|족발|보쌈", re.I), "snack_late"),
    (re.compile(r"이마트|EMART|홈플러스|롯데마트|코스트코|GS\s*THE\s*FRESH", re.I), "groceries"),
    (re.compile(r"CGV|메가박스|롯데시네마|예스24|교보문고|올리브영|다이소", re.I), "entertainment"),
    (re.compile(r"넷플릭스|유튜브\s*프리미엄|쿠팡플레이|왓챠|디즈니플러스|티빙|스포티파이", re.I), "subscription"),  # noqa: E501
    # KT 뒤에 word boundary(\b)는 한글 앞에선 안 잡히므로 lookahead로 공백/한글/텔레콤/통신/문장끝 명시  # noqa: E501
    (re.compile(r"KT(?=\s|텔레콤|통신|[가-힣]|$)|SKT|SK텔레콤|LGU\+|LG\s*유플러스", re.I), "telecom"),  # noqa: E501
    (re.compile(r"티머니|T머니|캐시비|교통카드|버스|지하철|코레일|SRT", re.I), "transport"),
    (re.compile(r"한전|한국전력|도시가스|상수도|관리비", re.I), "utilities"),
    (re.compile(r"약국|병원|의원|치과|한의원", re.I), "health"),
    (re.compile(r"쿠팡|11번가|G마켓|네이버\s*스마트스토어|마켓컬리|SSG", re.I), "shopping"),
    # W3 통장 룰 추가 (merchant_raw가 '[구분] 적요' 형태로 들어옴)
    (re.compile(r"정기적금|적금|예금", re.I), "savings"),
    (re.compile(r"월세|임대", re.I), "housing"),  # CMS보다 먼저 — [CMS] 월세-임대인 → housing
    (re.compile(r"CMS|보험|손해보험|하나생|화재", re.I), "insurance"),
    (re.compile(r"월급|급여|수익|수당", re.I), "income"),  # 이체보다 먼저 — [타행이체] 수임월급 → income  # noqa: E501
    (re.compile(r"이체|송금|입금", re.I), "transfer"),
]


def match(merchant_raw: str) -> str | None:
    if not merchant_raw:
        return None
    for pattern, category in _RULES:
        if pattern.search(merchant_raw):
            return category
    return None
