from datetime import date
from decimal import Decimal

from app.budgets.service import ALLOWED_CATEGORIES, budget_level, month_days, project


def test_level_boundaries():
    b = Decimal("100000")
    assert budget_level(Decimal("79900"), b, None) == "ok"
    assert budget_level(Decimal("80000"), b, None) == "warn"
    assert budget_level(Decimal("100000"), b, None) == "over"


def test_level_warns_when_projection_exceeds_budget():
    assert budget_level(Decimal("30000"), Decimal("100000"), Decimal("120000")) == "warn"
    assert budget_level(Decimal("30000"), Decimal("100000"), Decimal("90000")) == "ok"


def test_month_days_current_past_future():
    today = date(2026, 10, 20)
    assert month_days("2026-10", today) == (20, 31, True)
    assert month_days("2026-09", today) == (30, 30, False)
    assert month_days("2026-11", today) == (0, 30, False)
    assert month_days("2024-02", today) == (29, 29, False)


def test_project_only_for_current_month():
    assert project(Decimal("100000"), 10, 30, True) == Decimal("300000")
    assert project(Decimal("100000"), 30, 30, False) is None
    assert project(Decimal("0"), 0, 30, True) is None


def test_project_rounds_half_up():
    assert project(Decimal("10"), 3, 31, True) == Decimal("103")  # 103.33…


def test_allowed_categories_exclude_non_spending_and_income():
    assert "_total" in ALLOWED_CATEGORIES
    assert "coffee" in ALLOWED_CATEGORIES
    for c in ("income", "transfer", "savings"):
        assert c not in ALLOWED_CATEGORIES
