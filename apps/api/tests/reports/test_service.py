from decimal import Decimal

from app.reports.service import category_changes, default_month, top_categories


def test_default_month_prefers_last_closed_month():
    assert default_month(["2026-10", "2026-09", "2026-08"], "2026-10") == "2026-09"
    assert default_month(["2026-10"], "2026-10") == "2026-10"
    assert default_month([], "2026-10") is None


def test_top_categories_share_and_limit():
    rows = [{"category": f"c{i}", "amount": Decimal(100 - i * 10), "count": 1} for i in range(7)]
    out = top_categories(rows)
    assert [r["category"] for r in out] == ["c0", "c1", "c2", "c3", "c4"]
    assert out[0]["share"] == round(100 / 490, 4)
    assert top_categories([]) == []


def test_category_changes_sorted_and_limited():
    cur = [{"category": "coffee", "amount": Decimal(62000)},
           {"category": "shopping", "amount": Decimal(10000)},
           {"category": "lunch", "amount": Decimal(50000)},
           {"category": "health", "amount": Decimal(1000)},
           {"category": "etc", "amount": Decimal(9000)}]
    prev = [{"category": "coffee", "amount": Decimal(30000)},
            {"category": "shopping", "amount": Decimal(55000)},
            {"category": "dinner", "amount": Decimal(40000)},
            {"category": "etc", "amount": Decimal(1000)}]
    out = category_changes(cur, prev)
    assert [(c["category"], c["diff"]) for c in out["increased"]] == [
        ("lunch", Decimal(50000)), ("coffee", Decimal(32000)), ("etc", Decimal(8000))]
    assert [(c["category"], c["diff"]) for c in out["decreased"]] == [
        ("shopping", Decimal(-45000)), ("dinner", Decimal(-40000))]
    assert out["decreased"][1]["amount"] == Decimal(0)  # 이번 달엔 없던 카테고리
