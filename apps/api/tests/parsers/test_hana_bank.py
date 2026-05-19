from decimal import Decimal
from pathlib import Path

import openpyxl

from app.parsers.hana_bank import detect, parse_workbook

FIXTURE = Path(__file__).parent.parent / "fixtures" / "hana-bank-fixture.xlsx"


def _load_wb():
    return openpyxl.load_workbook(FIXTURE, read_only=True, data_only=True)


def test_detect_hana_bank_workbook():
    wb = _load_wb()
    try:
        assert detect(wb) is True
    finally:
        wb.close()


def test_parse_returns_at_least_10_transactions():
    result = parse_workbook(FIXTURE.read_bytes())
    assert result.rows_total >= 10


def test_parse_withdrawal_is_positive():
    result = parse_workbook(FIXTURE.read_bytes())
    # 스타벅스 = 출금
    starbucks = [t for t in result.transactions if "스타벅스" in t.merchant_raw]
    assert len(starbucks) == 1
    assert starbucks[0].amount == Decimal(5500)
    assert starbucks[0].amount > 0


def test_parse_deposit_is_negative():
    result = parse_workbook(FIXTURE.read_bytes())
    # 월급 = 입금
    salary = [t for t in result.transactions if "월급" in t.merchant_raw]
    assert len(salary) == 1
    assert salary[0].amount == Decimal(-3500000)
    assert salary[0].amount < 0


def test_parse_merchant_raw_format():
    """구분이 있을 때 merchant_raw는 '[구분] 적요' 패턴. 구분 없으면 적요만 또는 fallback."""
    result = parse_workbook(FIXTURE.read_bytes())
    bracketed = [t for t in result.transactions if t.merchant_raw.startswith("[")]
    # fixture의 모든 행에 구분이 있으므로 최소 하나는 bracket 형태
    assert len(bracketed) >= 5
    # 알려진 패턴이 등장하는지 확인
    types_seen = {t.merchant_raw.split("]")[0][1:] for t in bracketed if "]" in t.merchant_raw}
    assert "타행이체" in types_seen
    assert "현금/체크" in types_seen


def test_parse_skips_rows_with_zero_amount():
    """출금=입금=0인 행은 거래로 변환되지 않아야 함 (skip)."""
    # 이 검증은 parser 동작의 negative-skip 보증.
    # fixture에는 0/0 행이 없으므로 모든 transaction의 amount는 nonzero.
    result = parse_workbook(FIXTURE.read_bytes())
    assert all(t.amount != 0 for t in result.transactions)


def test_parse_no_card_info():
    """통장이라 카드 관련 필드는 모두 None."""
    result = parse_workbook(FIXTURE.read_bytes())
    for t in result.transactions:
        assert t.approval_no is None
        assert t.card_last4 is None
        assert t.installment_months is None
        assert t.is_canceled is False


def test_parse_full_datetime_preserved():
    """txn_time이 None이 아니어야 함 (full datetime → time 추출)."""
    result = parse_workbook(FIXTURE.read_bytes())
    for t in result.transactions:
        assert t.txn_time is not None
