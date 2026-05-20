import pytest

from app.categorization.rulebook import CATEGORIES, match


@pytest.mark.parametrize(
    "merchant,expected",
    [
        ("스타벅스 강남점", "coffee"),
        ("STARBUCKS COFFEE", "coffee"),
        ("이디야커피 역삼", "coffee"),
        ("김밥천국", "lunch"),
        ("맥도날드 잠실점", "lunch"),
        ("BBQ 치킨 잠실", "snack_late"),
        ("이마트 성수점", "groceries"),
        ("코스트코 양재", "groceries"),
        ("CGV 왕십리", "entertainment"),
        ("넷플릭스", "subscription"),
        ("KT 통신요금", "telecom"),
        ("KT통신요금", "telecom"),  # 공백 없는 한글 직결 — \b 회귀 방지
        ("KT텔레콤", "telecom"),
        ("티머니 충전", "transport"),
        ("EMART 잠실점", "groceries"),  # 기존 test_simple_rules 케이스 흡수
        # W3 통장 룰북 추가
        ("[정기적금] 청년도약", "savings"),
        ("[CMS] 하나생02022", "insurance"),
        ("[타행이체] 수임월급", "income"),
        ("[타행이체] 정혜숙", "transfer"),
        ("[CMS] 월세-임대인", "housing"),
    ],
)
def test_rulebook_matches_known_merchants(merchant, expected):
    assert match(merchant) == expected


def test_rulebook_returns_none_for_unknown():
    assert match("아무도 모르는 가맹점 12345") is None


def test_rulebook_returns_none_for_empty_string():
    assert match("") is None


def test_categories_enum_has_unknown_and_19_total():
    assert "unknown" in CATEGORIES
    assert "savings" in CATEGORIES
    assert "insurance" in CATEGORIES
    assert "income" in CATEGORIES
    assert "transfer" in CATEGORIES
    assert "housing" in CATEGORIES
    assert len(CATEGORIES) == 19
