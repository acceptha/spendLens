from app.categorization.merchant import normalize_merchant


def test_alias_cu_variants_group_together():
    assert normalize_merchant("씨유(CU) 구로JNK점") == "CU"
    assert normalize_merchant("씨유(CU) 구로원룸점") == "CU"
    assert normalize_merchant("CU 강남점") == "CU"


def test_alias_emart24_takes_priority_over_emart():
    assert normalize_merchant("이마트24 역삼점") == "이마트24"
    assert normalize_merchant("이마트 잠실점") == "이마트"


def test_alias_starbucks_ko_and_en():
    assert normalize_merchant("스타벅스 강남대로점") == "스타벅스"
    assert normalize_merchant("STARBUCKS Gangnam") == "스타벅스"


def test_heuristic_strips_branch_suffix_for_unlisted_chain():
    # 별칭에 없는 체인 → 끝의 지점 토큰 제거
    assert normalize_merchant("본죽 강남점") == "본죽"


def test_heuristic_removes_corp_markers():
    assert normalize_merchant("주식회사 카카오") == "카카오"


def test_cjk_spaces_collapsed():
    assert normalize_merchant("김밥 천국") == "김밥천국"


def test_empty_input():
    assert normalize_merchant("") == ""
    assert normalize_merchant("   ") == ""
