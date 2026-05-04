from pathlib import Path
import pytest

from app.parsers import ParseError
from app.parsers.samsung_card import find_target_sheet
import openpyxl


FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "samsung-card-fixture.xlsx"


def test_find_target_sheet_partial_match():
    wb = openpyxl.load_workbook(FIXTURE, read_only=True, data_only=True)
    name = find_target_sheet(wb)
    assert "국내이용내역" in name


def test_find_target_sheet_raises_when_missing():
    wb = openpyxl.Workbook()
    wb.active.title = "Other"
    with pytest.raises(ParseError) as ei:
        find_target_sheet(wb)
    assert ei.value.code == "SHEET_NOT_FOUND"
