# W7 — 월 예산 목표 + 초과 경고 설계

- 작성일: 2026-10-20
- 상태: 확정 (사용자 승인)
- 범위: 백엔드 `app/budgets/` 신규 도메인 모듈 + migration 0007, 웹 `/budget` 탭 + 대시보드 요약 카드

## 1. 목표

사용자가 한 달 총 지출 한도와 카테고리별 한도를 정해 두고, 지출이 한도에 가까워지거나 넘으면 **앱 안에서** 바로 알 수 있게 한다. 월말 예상 지출을 보여줘 "이미 넘었다"뿐 아니라 "이 속도면 넘는다"도 경고한다.

### 결정 사항 (사용자 확정)

| 항목 | 결정 |
|---|---|
| 알림 | 앱 안 표시만 (이메일·웹 푸시 없음) |
| 예산 단위 | 매월 반복되는 기본값. 변경은 **이번 달부터** 적용, 지난달 기록은 유지 |
| 범위 | 총 지출 한도(`_total`) + 원하는 카테고리별 한도 |
| 화면 | 새 `예산` 탭(설정·상세) + 대시보드 요약 카드 |
| 저장 방식 | 적용 시작 월(`effective_from`)을 가진 행 (접근 A) |
| 예상 지출 | 이번 달만, 단순 선형 투영 |

### 비목표

- 이메일·푸시 알림, 월별 개별 조정(특정 달만 다른 값), 미래 달 예약 변경, 예산 이월(rollover), 수입 기반 자동 예산 추천.

## 2. 데이터 모델 — migration 0007

```sql
CREATE TABLE budgets (
  user_id        UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  category       TEXT NOT NULL,           -- 카테고리 키 또는 '_total'
  amount         NUMERIC(14,0) NULL,      -- NULL = 이 달부터 예산 해제
  effective_from TEXT NOT NULL,           -- 'YYYY-MM'
  updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, category, effective_from)
);
```

- **월 M의 예산**: 카테고리별로 `effective_from <= M` 인 행 중 `effective_from`이 가장 큰 행. 그 `amount`가 NULL이거나 행이 없으면 예산 없음.
- **저장(PUT)**: 항상 `effective_from = 이번 달(Asia/Seoul)` 로 upsert(`ON CONFLICT (user_id, category, effective_from) DO UPDATE`). 같은 달 재수정은 덮어쓰기, 과거 달 행은 건드리지 않는다.
- **해제**: `amount = NULL` 행을 이번 달로 upsert. 과거 달 진행률은 당시 예산으로 계속 보인다.
- 허용 카테고리: `_total` + `CATEGORIES` 중 `NON_SPENDING_CATEGORIES`(transfer, savings)와 `income`을 뺀 나머지. 그 외는 400 `INVALID_CATEGORY`.
- `amount` 검증: NULL 또는 1 이상 정수(상한 10^12 미만). 위반 시 422(Pydantic).
- `tests/conftest.py`의 TRUNCATE 목록에 `budgets` 추가.

## 3. API — `app/budgets/` (도메인 모듈: `routes.py`, `schemas.py`, `service.py`)

인증은 `Depends(current_user_id)`, DB는 `async with acquire() as conn`, 에러는 라우터에서 `HTTPException` 직접 raise (CLAUDE.md 규칙).

### `GET /budgets/status?month=YYYY-MM`

- `month` 형식 오류 → 400 `INVALID_MONTH_FORMAT` (dashboard와 동일 검증 재사용).
- 응답 `BudgetStatusResponse`:

```json
{
  "month": "2026-10",
  "is_current": true,
  "days_elapsed": 20,
  "days_in_month": 31,
  "items": [
    {"category": "_total", "budget": "1500000", "spent": "820000",
     "ratio": 0.5467, "projected": "1271000", "level": "ok"},
    {"category": "coffee", "budget": "50000", "spent": "62000",
     "ratio": 1.24, "projected": "96100", "level": "over"}
  ]
}
```

- `items`: 그 달 예산이 있는 항목만. `_total`이 있으면 맨 앞, 나머지는 `ratio` 내림차순.
- `spent`: 그 달 지출 합 — **dashboard와 같은 규칙**: `amount > 0`, `effective_category = COALESCE(user_category_override, category)` 기준, `NON_SPENDING_CATEGORIES` 제외. `_total`은 전체 합, 카테고리는 해당 effective_category 합. 구현은 `dashboard/service.py`의 집계를 재사용하거나 같은 SQL 조건을 쓴다(일치 테스트로 보장).
- `is_current`: `month == 이번 달(Asia/Seoul)`.
- `days_elapsed`: 이번 달이면 오늘 날짜(일), 지난달이면 `days_in_month`, 미래 달이면 0.
- `projected`: `is_current`이고 `days_elapsed >= 1`일 때 `round(spent / days_elapsed * days_in_month)`, 아니면 null.
- `ratio`: `spent / budget` (소수 4자리).
- `level` (순수 함수 `budget_level(spent, budget, projected)`):
  - `over`: `spent >= budget`
  - `warn`: `spent >= 0.8 * budget` 또는 (`projected` 있고 `projected > budget`)
  - `ok`: 그 외

### `PUT /budgets`

- 요청 `BudgetSetRequest {category: str, amount: int | None}` → 204.
- 이번 달 기준 upsert. 응답 본문 없음(클라이언트가 status 재조회).

### 시간대

"이번 달/오늘"은 `zoneinfo.ZoneInfo("Asia/Seoul")` 기준. `service.py`에 `today_kst()` 를 두고 테스트에서 monkeypatch 가능하게 한다.

## 4. 웹

### 네비게이션
`Nav`에 `예산`(`/budget`) 추가, `ProtectedRoute`로 보호, 라우트 lazy 로딩(기존 코드 스플리팅 패턴). 375px에서 한 줄 유지 확인.

### `/budget` 페이지 (`routes/budget.tsx`)
- 월 선택: `useMonths()` 결과 ∪ 이번 달, 기본값 이번 달. `?month=` 쿼리 파라미터 지원.
- **총 지출 카드**: `₩spent / ₩budget`, 퍼센트, 진행 막대, 이번 달이면 "이 속도면 월말 ₩projected 예상".
- **카테고리 목록**: 한글 라벨(`categoryLabel`), 금액/한도, 퍼센트, 상태 배지, 이번 달이면 월말 예상.
- **상태 표현**: `ok` 초록 / `warn` 주황 + "주의" / `over` 빨강 + "초과". 색 + 글자 병기.
- **편집**: 행의 `편집` → 인라인 숫자 입력 → Enter/저장 → `PUT` → status 재조회. 빈 값 저장 = 해제. 실패 시 행에 에러 문구.
- **예산 추가**: 예산 없는 허용 카테고리 드롭다운 + 금액 입력.
- **지난달**: 편집·추가 숨김, "예산 변경은 이번 달부터 적용됩니다" 안내.
- **빈 상태(예산 0개, 이번 달)**: "한 달 총 지출 한도부터 정해보세요" + 총액 입력란 하나.
- 금액 표기는 `formatWon`.

### 대시보드 요약 카드 (`components/BudgetSummaryCard.tsx`)
- 위치: 인사이트 카드 아래. 대시보드 선택 월의 status 사용.
- `_total` 진행 막대 1줄 + `warn`/`over` 카테고리 최대 3개 ("커피 124% 초과", "쇼핑 월말 예상 초과").
- 클릭 → `/budget?month=`.
- 예산 없음 → "예산 설정하기 →" 한 줄.

### 데이터 흐름 (`lib/api.ts`, `lib/queries.ts`)
- `fetchBudgetStatus(month)`, `putBudget(category, amount)`.
- `qk.budget(month) = ["budget", month]`, `useBudgetStatus(month)`, `useSaveBudget()` (성공 시 `["budget"]` 무효화).
- 거래 변경 mutation(업로드·삭제·카테고리·필수 토글)의 무효화 목록에 `["budget"]` 추가.

## 5. 테스트

**API (pytest)**
- `budget_level`·`projected` 단위: 경계 79.9%/80%/100%, projected 초과만으로 warn, 지난달 projected null, 1일차.
- effective_from: 지난달 예산 저장 후 이번 달 변경 → 지난달 status는 옛 값, 이번 달은 새 값. 같은 달 재저장 덮어쓰기. 해제(null) 후 이번 달 항목 없음 + 지난달 유지.
- 집계 일치: 같은 데이터에서 `_total.spent == dashboard summary total_amount`, 카테고리 spent == by-category 값 (transfer/savings 제외, override 반영).
- 사용자 격리, `INVALID_CATEGORY`(income/transfer/savings/임의 문자열), `INVALID_MONTH_FORMAT`, 인증 필요(401).
- 시간 고정: `today_kst` monkeypatch.

**웹 (vitest)**
- 진행 막대: level별 색 클래스와 "주의"/"초과" 텍스트.
- 편집 → 저장 호출 인자, 빈 값 저장 = null, 저장 후 무효화.
- 지난달: 편집/추가 버튼 없음 + 안내 문구.
- 빈 상태 렌더, 대시보드 카드 요약(최대 3개, 빈 상태 링크).

**운영 검증**
- 배포 후 QA 계정으로 예산 설정 → 대시보드/예산 탭 확인(데스크톱·모바일 375px), 거래 삭제 후 spent 갱신 확인.

## 6. 작업 단위 (PR)

1. `feat(api)`: migration 0007 + `app/budgets/` + 테스트
2. `feat(web)`: API 클라이언트·쿼리 훅 + `/budget` 페이지 + Nav
3. `feat(web)`: 대시보드 요약 카드 + 거래 mutation 무효화 연동
4. `docs`: FEATURES.md 갱신
