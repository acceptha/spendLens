from app.categorization.labels import CATEGORY_LABELS, category_label
from app.categorization.rulebook import CATEGORIES


def test_labels_cover_all_categories():
    assert set(CATEGORY_LABELS.keys()) == set(CATEGORIES)


def test_category_label_falls_back_to_key():
    assert category_label("coffee") == "커피"
    assert category_label("no_such_key") == "no_such_key"
