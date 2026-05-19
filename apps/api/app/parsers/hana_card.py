"""하나카드 파서 — Phase 7에서 본구현 예정.

현재는 detect=False로 항상 미매칭, parse는 NotImplementedError.
이 stub 덕분에 Phase 6 registry import가 깨지지 않음.
"""
import openpyxl

from app.parsers.samsung_card import ParseResult


def detect(wb: openpyxl.Workbook) -> bool:  # noqa: ARG001
    return False


def parse_workbook(file_bytes: bytes) -> ParseResult:  # noqa: ARG001
    raise NotImplementedError("hana_card parser will be implemented in Phase 7")
