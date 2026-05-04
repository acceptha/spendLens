from pathlib import Path
import pytest

from app.parsers import ParseError
from app.parsers.samsung_card import parse_workbook


FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "samsung-card-fixture.xlsx"


def test_parse_workbook_returns_all_data_rows():
    with FIXTURE.open("rb") as f:
        result = parse_workbook(f.read())
    assert result.rows_total == 7
    assert len(result.transactions) >= 6  # at least 6 valid rows
    assert result.parse_errors == [] or all(
        isinstance(e, dict) for e in result.parse_errors
    )


def test_parse_workbook_canceled_row_present():
    with FIXTURE.open("rb") as f:
        result = parse_workbook(f.read())
    canceled = [t for t in result.transactions if t.is_canceled]
    assert len(canceled) == 1
    assert canceled[0].merchant_raw.startswith("교보문고")


def test_parse_workbook_missing_approval_no_present():
    with FIXTURE.open("rb") as f:
        result = parse_workbook(f.read())
    no_approval = [t for t in result.transactions if t.approval_no is None]
    assert len(no_approval) == 1
    assert no_approval[0].merchant_raw == "정산수수료"


def test_parse_workbook_corrupt_bytes_raises():
    with pytest.raises(ParseError) as ei:
        parse_workbook(b"\x00not-an-xlsx")
    assert ei.value.code == "WORKBOOK_LOAD_FAILED"
