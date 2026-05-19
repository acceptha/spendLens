"""Parser registry — auto-detects card issuer from XLSX header signature."""
from collections.abc import Callable
from io import BytesIO

import openpyxl


class ParseError(Exception):
    """Raised when input is unrecoverably malformed."""

    def __init__(self, code: str, **details):
        self.code = code
        self.details = details
        super().__init__(f"{code}: {details}")


SOURCE_TYPE_SAMSUNG_XLSX = "samsung_card_xlsx"
SOURCE_TYPE_WOORI_XLSX = "woori_card_xlsx"
SOURCE_TYPE_HANA_XLSX = "hana_card_xlsx"


# Imports below MUST come after ParseError + SOURCE_TYPE_* so submodules can
# `from app.parsers import ParseError` without cycle.
from app.parsers.hana_card import detect as _detect_hana  # noqa: E402
from app.parsers.hana_card import parse_workbook as _hana_parse  # noqa: E402
from app.parsers.samsung_card import ParseResult  # noqa: E402
from app.parsers.samsung_card import detect as _detect_samsung  # noqa: E402
from app.parsers.samsung_card import parse_workbook as _samsung_parse  # noqa: E402
from app.parsers.woori_card import detect as _detect_woori  # noqa: E402
from app.parsers.woori_card import parse_workbook as _woori_parse  # noqa: E402

ParserFn = Callable[[bytes], ParseResult]

# Order = detection priority. First matching detect wins.
_REGISTRY: list[tuple[str, Callable[[openpyxl.Workbook], bool], ParserFn]] = [
    (SOURCE_TYPE_SAMSUNG_XLSX, _detect_samsung, _samsung_parse),
    (SOURCE_TYPE_WOORI_XLSX, _detect_woori, _woori_parse),
    (SOURCE_TYPE_HANA_XLSX, _detect_hana, _hana_parse),
]


def detect(file_bytes: bytes) -> tuple[str, ParserFn]:
    """Open the workbook once, ask each parser if it recognizes the format.

    Returns (source_type, parser_function) of the first match.
    Raises ParseError('UNKNOWN_CARD_FORMAT', sheets=[...]) if no parser matches.
    """
    try:
        wb = openpyxl.load_workbook(BytesIO(file_bytes), read_only=True, data_only=True)
    except Exception as exc:
        raise ParseError("WORKBOOK_LOAD_FAILED", reason=str(exc)) from exc

    try:
        for source_type, detect_fn, parser in _REGISTRY:
            try:
                if detect_fn(wb):
                    return source_type, parser
            except Exception:  # noqa: BLE001, S110
                # 한 파서의 detect 예외가 전체 dispatch를 막지 않게
                pass
        raise ParseError("UNKNOWN_CARD_FORMAT", sheets=list(wb.sheetnames))
    finally:
        wb.close()


def get_parser(source_type: str) -> ParserFn:
    """Backward-compat helper for tests that still want explicit parser lookup."""
    for st, _, parser in _REGISTRY:
        if st == source_type:
            return parser
    raise ParseError("UNSUPPORTED_SOURCE_TYPE", source_type=source_type)
