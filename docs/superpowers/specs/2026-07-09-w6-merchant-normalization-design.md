# W6 — 가맹점 정규화 설계

> 작성일: 2026-07-09 · 트랙: 데이터 품질

## 목표

가맹점명을 정규화해 저장하고, Top 가맹점 그룹핑과 LLM 캐시 키에 활용한다. "씨유(CU) 구로JNK점" vs "씨유(CU) 구로원룸점"처럼 지점명만 다른 거래가 따로 집계되던 **분산 문제**를 해소하고, 같은 브랜드는 한 번 분류하면 모든 지점에서 재사용(분류 정확도↑)한다.

## 현재 상태

- `transactions.merchant_normalized` 컬럼은 **존재하지만 비어 있음(NULL)** — 파서·insert 어디서도 채우지 않음.
- `categorization/cache.py`의 `normalize_merchant()`는 LLM 캐시 키 전용 경량 정규화(㈜/N호점/끝의 "점" 제거)만 하고, 저장·그룹핑엔 안 쓰임.
- `dashboard.top_merchants`는 `merchant_raw`로 GROUP BY → 분산.
- 룰북은 `merchant_raw`에 정규식 매칭(브랜드 substring이라 지점 무관하게 이미 동작).

## 범위 (B: 그룹핑 + 분류 정확도)

- ✅ 정규화명 저장(`merchant_normalized`)
- ✅ `top_merchants` 그룹핑에 활용
- ✅ LLM 캐시 키에 활용(브랜치 통일 → hit↑ → 브랜드 단위 분류 재사용)
- ❌ 거래 리스트 UI 표시(범위 C 제외) · LLM 정규화 · 룰북을 normalized로 이관

## 설계

### 1. 정규화 엔진 — `app/categorization/merchant.py` (신규)

`normalize_merchant(raw: str) -> str`:
1. **별칭 테이블 우선**: 대형 체인 정규식 → 정식 브랜드명(첫 매칭). 편의점(CU/GS25/세븐일레븐/이마트24/미니스톱), 카페(스타벅스/이디야/투썸/메가커피/컴포즈/빽다방/할리스/커피빈), 패스트푸드(맥도날드/롯데리아/버거킹/맘스터치/서브웨이), 리테일(이마트/홈플러스/롯데마트/코스트코/올리브영/다이소), 베이커리(파리바게뜨/뚜레쥬르) 등 ~25개. 지점 분산이 큰 체인 위주.
2. **폴백 휴리스틱**: 끝의 지점 토큰(`…점`/`지점`/`N호점`), 괄호 매장코드, `㈜`/`주식회사` 제거 → 공백 정리 → 한글이면 공백 제거 → 앞부분을 브랜드로.
3. 빈 입력 → `""`.

기존 `cache.normalize_merchant` 로직은 이 모듈로 이관하고, `cache.py`는 `merchant.normalize_merchant`를 호출(중복 제거). 캐시 키 prefix는 `v1` 유지(정규화 변경으로 기존 키는 무해한 orphan, 새 키가 쌓임).

### 2. 저장

`transactions.service.insert_transactions`의 INSERT에 `merchant_normalized = normalize_merchant(t.merchant_raw)` 컬럼 추가. 스키마 변경 없음(컬럼 이미 존재).

### 3. 백필

`scripts/backfill_merchant_normalized.py` — 전 거래를 읽어 `merchant_normalized`를 채우는 일회성 스크립트(`merchant_normalized IS NULL`인 행 대상). 배포 후 1회 실행. asyncpg 직접 사용, `normalize_merchant` 재사용.

### 4. 활용

- `dashboard.top_merchants`: `GROUP BY COALESCE(merchant_normalized, merchant_raw)`(백필 전 안전), 표시명·정렬 동일 키. 응답 필드명은 `merchant_raw` 유지(프론트 무변경, 대표명으로 채움).
- 캐시 키: 개선된 `normalize_merchant` 사용(자동).

## 테스트

- `tests/categorization/test_merchant.py`: 별칭 매칭(CU 변형·이마트24 vs 이마트 우선순위), 지점 토큰 제거, 폴백, CJK 공백, 빈 입력.
- `tests/transactions/`: insert가 `merchant_normalized`를 채우는지.
- `tests/dashboard/test_top_merchants.py`: 지점 다른 동일 브랜드가 하나로 그룹됨.
- (선택) 백필 스크립트 스모크.

## 비목표 / 한계

- 별칭 테이블은 코드 상수(사용자별 아님). 미등록 체인은 휴리스틱에 의존 → 완벽하지 않음(반복 지점명은 대부분 흡수).
- 룰북은 raw 매칭 유지(정규화명 이관은 별도 검토).
- 거래 리스트 UI엔 원본만 표시(정규화명 노출은 범위 C, 추후).
