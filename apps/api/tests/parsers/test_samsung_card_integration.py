from pathlib import Path

from app.parsers import get_parser, SOURCE_TYPE_SAMSUNG_XLSX


FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "samsung-card-fixture.xlsx"


def test_full_pipeline_via_registry():
    parser = get_parser(SOURCE_TYPE_SAMSUNG_XLSX)
    with FIXTURE.open("rb") as f:
        result = parser(f.read())

    # 6개의 정상 거래 + 1 정산 행 = 7
    assert result.rows_total == 7
    assert len(result.transactions) == 7

    # 카테고리 분포 검증
    categories = [t.category for t in result.transactions]
    assert "coffee" in categories  # 스타벅스, 이디야
    assert "groceries" in categories  # 이마트
    assert "lunch" in categories  # 김밥천국

    # 모든 카드번호 마스킹 확인
    for t in result.transactions:
        assert t.raw_row["카드번호"].startswith("****")
