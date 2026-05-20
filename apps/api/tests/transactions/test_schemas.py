import typing

import pytest
from pydantic import ValidationError

from app.transactions.schemas import CategoryLiteral, TransactionPatchRequest


def test_patch_request_accepts_valid_category():
    req = TransactionPatchRequest(category="groceries")
    assert req.category == "groceries"


def test_patch_request_accepts_new_w3_categories():
    for cat in ("savings", "insurance", "income", "transfer", "housing"):
        req = TransactionPatchRequest(category=cat)
        assert req.category == cat


def test_patch_request_rejects_invalid_category():
    with pytest.raises(ValidationError):
        TransactionPatchRequest(category="totally_not_a_category")


def test_category_literal_has_19_options():
    args = typing.get_args(CategoryLiteral)
    assert len(args) == 19
    assert "unknown" in args
    assert "savings" in args
