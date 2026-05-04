import openpyxl
import re
from typing import Iterable

from openpyxl.worksheet.worksheet import Worksheet

from app.parsers import ParseError


_TARGET_SHEET_KEYWORD = "국내이용내역"

REQUIRED_COLUMNS = ["승인일자", "가맹점명", "승인금액(원)", "승인번호", "카드번호"]
ALL_KNOWN_COLUMNS = [
    "카드번호", "본인가족구분", "승인일자", "승인시각", "가맹점명",
    "승인금액(원)", "일시불할부구분", "할부개월", "승인번호",
    "취소여부", "사용포인트", "결제일",
]


def find_target_sheet(wb: openpyxl.Workbook) -> str:
    """Return first sheet name containing '국내이용내역'."""
    for name in wb.sheetnames:
        if _TARGET_SHEET_KEYWORD in name:
            return name
    raise ParseError("SHEET_NOT_FOUND", looking_for=_TARGET_SHEET_KEYWORD, found=list(wb.sheetnames))


def find_header_row(ws: Worksheet) -> tuple[int, dict[str, int]]:
    """Scan rows top-down; return (row_index, {column_name: column_index_1based}).

    A row qualifies if it contains all REQUIRED_COLUMNS as cell values.
    """
    max_scan = min(ws.max_row or 20, 20)
    for row_idx in range(1, max_scan + 1):
        col_map: dict[str, int] = {}
        for col_idx, cell in enumerate(ws[row_idx], start=1):
            if isinstance(cell.value, str):
                col_map[cell.value.strip()] = col_idx
        if all(req in col_map for req in REQUIRED_COLUMNS):
            return row_idx, col_map

    raise ParseError(
        "HEADER_NOT_FOUND",
        required=REQUIRED_COLUMNS,
        scanned_rows=max_scan,
    )


def mask_pan(pan: str | None) -> tuple[str, str]:
    """Return (masked_string, last4)."""
    if not pan:
        return "****-****-****-****", ""
    digits = re.sub(r"\D", "", pan)
    last4 = digits[-4:] if len(digits) >= 4 else ""
    masked = f"****-****-****-{last4}" if last4 else "****-****-****-****"
    return masked, last4
