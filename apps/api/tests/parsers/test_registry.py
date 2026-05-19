from io import BytesIO
from pathlib import Path

import openpyxl
import pytest

from app.parsers import (
    SOURCE_TYPE_SAMSUNG_XLSX,
    SOURCE_TYPE_WOORI_XLSX,
    ParseError,
    detect,
)

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_detect_samsung_xlsx():
    data = (FIXTURES / "samsung-card-fixture.xlsx").read_bytes()
    source_type, parser = detect(data)
    assert source_type == SOURCE_TYPE_SAMSUNG_XLSX
    assert callable(parser)


def test_detect_woori_xlsx():
    data = (FIXTURES / "woori-card-fixture.xlsx").read_bytes()
    source_type, parser = detect(data)
    assert source_type == SOURCE_TYPE_WOORI_XLSX
    assert callable(parser)


def test_detect_unknown_workbook_raises():
    wb = openpyxl.Workbook()
    wb.active["A1"] = "this is not a card statement"
    buf = BytesIO()
    wb.save(buf)
    with pytest.raises(ParseError) as exc_info:
        detect(buf.getvalue())
    assert exc_info.value.code == "UNKNOWN_CARD_FORMAT"


def test_detect_corrupt_workbook_raises_workbook_load_failed():
    with pytest.raises(ParseError) as exc_info:
        detect(b"this is not even an xlsx file")
    assert exc_info.value.code == "WORKBOOK_LOAD_FAILED"
