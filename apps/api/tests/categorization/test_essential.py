from app.categorization.essential import (
    ESSENTIAL_CATEGORIES,
    ESSENTIAL_DEFAULTS,
    is_essential,
)
from app.categorization.rulebook import CATEGORIES


def test_essential_defaults_cover_all_categories():
    assert set(ESSENTIAL_DEFAULTS.keys()) == set(CATEGORIES)


def test_is_essential_true_for_housing():
    assert is_essential("housing") is True


def test_is_essential_false_for_coffee():
    assert is_essential("coffee") is False


def test_is_essential_unknown_category_defaults_false():
    assert is_essential("nonexistent") is False


def test_essential_categories_is_subset_of_true_defaults():
    assert set(ESSENTIAL_CATEGORIES) == {c for c, v in ESSENTIAL_DEFAULTS.items() if v}
