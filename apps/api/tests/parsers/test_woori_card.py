from pathlib import Path

import openpyxl

from app.parsers.woori_card import detect as detect_woori
from app.parsers.woori_card import parse_workbook

FIXTURE = Path(__file__).parent.parent / "fixtures" / "woori-card-fixture.xlsx"


def _load_wb():
    return openpyxl.load_workbook(FIXTURE, read_only=True, data_only=True)


def test_detect_woori_workbook():
    wb = _load_wb()
    try:
        assert detect_woori(wb) is True
    finally:
        wb.close()


def test_parse_returns_at_least_10_transactions():
    result = parse_workbook(FIXTURE.read_bytes())
    assert result.rows_total >= 10
    # Summary rows (카드소계, 통합청구합계) MUST be skipped
    merchants = [t.merchant_raw for t in result.transactions]
    assert not any("소계" in m for m in merchants)
    assert not any("통합청구합계" in m for m in merchants)


def test_parse_extracts_specific_starbucks_row():
    result = parse_workbook(FIXTURE.read_bytes())
    starbucks = [t for t in result.transactions if "스타벅스" in t.merchant_raw]
    assert len(starbucks) == 1
    assert starbucks[0].amount == 5400  # Decimal("5400") OK


def test_parse_marks_cancellation_correctly():
    result = parse_workbook(FIXTURE.read_bytes())
    canceled = [t for t in result.transactions if t.is_canceled]
    assert len(canceled) >= 1
    # amount는 절대값으로 저장됨
    assert all(t.amount >= 0 for t in canceled)


def test_parse_installment_months():
    result = parse_workbook(FIXTURE.read_bytes())
    installments = [
        t for t in result.transactions
        if t.installment_months and t.installment_months > 0
    ]
    assert any(t.installment_months == 3 for t in installments)


def test_parse_card_last4_extracted():
    result = parse_workbook(FIXTURE.read_bytes())
    last4_values = {t.card_last4 for t in result.transactions}
    assert "6247" in last4_values
    assert "5102" in last4_values


def test_parse_no_approval_no():
    """우리카드 명세서에 승인번호 컬럼이 없으므로 모든 거래의 approval_no는 None."""
    result = parse_workbook(FIXTURE.read_bytes())
    assert all(t.approval_no is None for t in result.transactions)


def test_year_inferred_from_max_date():
    """fixture의 일자는 04.14, 05.01 등. 가장 큰 일자가 오늘 이후가 아니면 올해."""
    result = parse_workbook(FIXTURE.read_bytes())
    from datetime import datetime
    today = datetime.now().date()
    for t in result.transactions:
        # 모든 일자는 today 또는 이전 (또는 작년 12월)
        assert t.txn_date.year in (today.year - 1, today.year)
