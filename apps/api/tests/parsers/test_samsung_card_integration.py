from pathlib import Path

from app.parsers import SOURCE_TYPE_SAMSUNG_XLSX, get_parser

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "samsung-card-fixture.xlsx"


def test_full_pipeline_via_registry():
    parser = get_parser(SOURCE_TYPE_SAMSUNG_XLSX)
    with FIXTURE.open("rb") as f:
        result = parser(f.read())

    # 6개의 정상 거래 + 1 정산 행 = 7
    assert result.rows_total == 7
    assert len(result.transactions) == 7

    # 파서는 카테고리를 분류하지 않음 — 모두 기본값 "unknown"
    # (카테고리 분류는 transactions/routes.py 에서 classify_category 호출)
    categories = [t.category for t in result.transactions]
    assert all(c == "unknown" for c in categories)

    # 모든 카드번호 마스킹 확인
    for t in result.transactions:
        assert t.raw_row["카드번호"].startswith("****")
