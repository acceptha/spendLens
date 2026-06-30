from app.insights.rules import build_insight


def _aggs(**over):
    base = {
        "month": "2026-04",
        "summary": {
            "total_amount": 128500,
            "transaction_count": 7,
            "prev_month_total": 100000,
            "prev_month_diff_pct": 28.5,
            "income_total": 0,
            "net_savings": -128500,
            "savings_rate": None,
        },
        "by_category": [
            {"category": "groceries", "amount": 59800, "count": 1},      # 필수
            {"category": "entertainment", "amount": 24000, "count": 1},  # 비필수
            {"category": "coffee", "amount": 15000, "count": 2},         # 비필수
        ],
        "top_merchants": [
            {"merchant_raw": "이마트 잠실점", "amount": 59800, "count": 1},
        ],
        "by_essential": [
            {"essential": True, "amount": 70800, "count": 2},
            {"essential": False, "amount": 57700, "count": 5},
        ],
    }
    base.update(over)
    return base


def test_build_insight_shape_and_allowed_types():
    out = build_insight(_aggs())
    assert isinstance(out["summary"], str) and out["summary"]
    assert 1 <= len(out["highlights"]) <= 3
    for h in out["highlights"]:
        assert h["type"] in {"top_growth", "anomaly", "saving_tip"}
        assert h["title"] and h["detail"]


def test_top_growth_is_largest_category():
    out = build_insight(_aggs())
    tg = next(h for h in out["highlights"] if h["type"] == "top_growth")
    assert "groceries" in tg["title"]


def test_saving_tip_is_largest_non_essential_category():
    # groceries(최대)는 필수 → saving_tip은 비필수 중 최대인 entertainment여야 함
    out = build_insight(_aggs())
    st = next(h for h in out["highlights"] if h["type"] == "saving_tip")
    assert "entertainment" in st["title"]


def test_anomaly_is_top_merchant():
    out = build_insight(_aggs())
    an = next(h for h in out["highlights"] if h["type"] == "anomaly")
    assert "이마트 잠실점" in an["title"]


def test_summary_includes_total_and_diff():
    out = build_insight(_aggs())
    assert "128,500" in out["summary"]
    assert "28" in out["summary"]  # 전월 대비 %


def test_empty_month_yields_no_highlights():
    out = build_insight(
        _aggs(summary={"total_amount": 0}, by_category=[], top_merchants=[], by_essential=[])
    )
    assert out["highlights"] == []
    assert "없습니다" in out["summary"]
