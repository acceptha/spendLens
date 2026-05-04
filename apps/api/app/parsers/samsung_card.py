import openpyxl

from app.parsers import ParseError


_TARGET_SHEET_KEYWORD = "국내이용내역"


def find_target_sheet(wb: openpyxl.Workbook) -> str:
    """Return first sheet name containing '국내이용내역'."""
    for name in wb.sheetnames:
        if _TARGET_SHEET_KEYWORD in name:
            return name
    raise ParseError("SHEET_NOT_FOUND", looking_for=_TARGET_SHEET_KEYWORD, found=list(wb.sheetnames))
