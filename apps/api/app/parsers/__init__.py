from typing import Protocol


class ParseError(Exception):
    """Raised when input is unrecoverably malformed."""

    def __init__(self, code: str, **details):
        self.code = code
        self.details = details
        super().__init__(f"{code}: {details}")


SOURCE_TYPE_SAMSUNG_XLSX = "samsung_card_xlsx"
