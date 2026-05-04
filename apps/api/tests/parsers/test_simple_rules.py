from app.parsers.simple_rules import classify


def test_classify_starbucks_to_coffee():
    assert classify("스타벅스 강남대로점") == "coffee"


def test_classify_unknown_returns_unknown():
    assert classify("정체불명상점") == "unknown"


def test_classify_case_insensitive_emart():
    assert classify("EMART 잠실점") == "groceries"
