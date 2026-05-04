from collections.abc import Callable


class ParseError(Exception):
    """Raised when input is unrecoverably malformed."""

    def __init__(self, code: str, **details):
        self.code = code
        self.details = details
        super().__init__(f"{code}: {details}")


SOURCE_TYPE_SAMSUNG_XLSX = "samsung_card_xlsx"


# Imports below MUST come after ParseError + SOURCE_TYPE_SAMSUNG_XLSX so
# samsung_card.py can `from app.parsers import ParseError` without cycle.
from app.parsers.samsung_card import ParseResult  # noqa: E402
from app.parsers.samsung_card import parse_workbook as _samsung_parse  # noqa: E402

_REGISTRY: dict[str, Callable[[bytes], ParseResult]] = {
    SOURCE_TYPE_SAMSUNG_XLSX: _samsung_parse,
}


def get_parser(source_type: str) -> Callable[[bytes], ParseResult]:
    if source_type not in _REGISTRY:
        raise ParseError("UNSUPPORTED_SOURCE_TYPE", source_type=source_type)
    return _REGISTRY[source_type]
