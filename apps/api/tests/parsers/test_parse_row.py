from datetime import date, time
from decimal import Decimal

from app.parsers.samsung_card import ALL_KNOWN_COLUMNS, parse_row


def _make_row(values: dict[str, object]) -> dict[str, object]:
    return {col: values.get(col) for col in ALL_KNOWN_COLUMNS}


def test_parse_row_basic_lump_sum():
    row = _make_row({
        "카드번호": "1234-5678-9012-3456",
        "본인가족구분": "본인",
        "승인일자": "2026-04-28",
        "승인시각": "12:34:00",
        "가맹점명": "스타벅스 강남대로점",
        "승인금액(원)": 9500,
        "일시불할부구분": "일시불",
        "할부개월": 0,
        "승인번호": "A20260428001",
        "취소여부": "N",
    })
    txn = parse_row(row)
    assert txn.txn_date == date(2026, 4, 28)
    assert txn.txn_time == time(12, 34, 0)
    assert txn.amount == Decimal("9500")
    assert txn.merchant_raw == "스타벅스 강남대로점"
    assert txn.approval_no == "A20260428001"
    assert txn.card_last4 == "3456"
    assert txn.installment_months == 0
    assert txn.is_canceled is False
    assert txn.category == "unknown"  # categorization happens in route layer, not parser
    # raw_row의 카드번호는 마스킹된 형태
    assert txn.raw_row["카드번호"] == "****-****-****-3456"


def test_parse_row_installment():
    row = _make_row({
        "카드번호": "1234-5678-9012-3456",
        "승인일자": "2026-04-26",
        "가맹점명": "이마트 잠실점",
        "승인금액(원)": 59800,
        "일시불할부구분": "할부",
        "할부개월": 3,
        "승인번호": "A20260426001",
        "취소여부": "N",
    })
    txn = parse_row(row)
    assert txn.installment_months == 3


def test_parse_row_canceled():
    row = _make_row({
        "카드번호": "1234-5678-9012-3456",
        "승인일자": "2026-04-24",
        "가맹점명": "교보문고 강남점",
        "승인금액(원)": 24000,
        "승인번호": "A20260424001",
        "취소여부": "Y",
    })
    txn = parse_row(row)
    assert txn.is_canceled is True


def test_parse_row_missing_approval_no():
    row = _make_row({
        "카드번호": "1234-5678-9012-3456",
        "승인일자": "2026-04-23",
        "가맹점명": "정산수수료",
        "승인금액(원)": 500,
        "승인번호": "",
        "취소여부": "N",
    })
    txn = parse_row(row)
    assert txn.approval_no is None
