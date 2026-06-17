from app.categorization.essential import (
    ESSENTIAL_CATEGORIES,
    ESSENTIAL_DEFAULTS,
)
from app.categorization.rulebook import CATEGORIES


def test_essential_defaults_cover_all_categories():
    assert set(ESSENTIAL_DEFAULTS.keys()) == set(CATEGORIES)


def test_essential_categories_is_subset_of_true_defaults():
    assert set(ESSENTIAL_CATEGORIES) == {c for c, v in ESSENTIAL_DEFAULTS.items() if v}
