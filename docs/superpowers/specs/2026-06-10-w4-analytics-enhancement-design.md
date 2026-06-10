# W4 — 분석 고도화 (Analytics Enhancement) 설계

작성일: 2026-06-10
상태: 설계 승인 완료 → 구현 계획(writing-plans) 대기

## 목표

W3에서 본인 모드 UI(필터/검색/오버라이드 + 대시보드 4위젯)를 완성했다. W4는 **"분석 고도화"** 테마로 대시보드의 분석 가치를 끌어올린다. 세 기능을 한 사이클에 출하한다:

1. **월간 LLM 인사이트 리포트** — Claude Haiku로 그 달의 지출 패턴을 구조화 하이라이트로 요약
2. **입금/소득 분석** — 출금만 보던 대시보드에 수입·순저축·저축률·현금흐름 추세 추가
3. **필수/비필수 토글** — 카테고리 기본 매핑 + 사용자 오버라이드로 필수 지출만 따로 집계

### 해결하는 문제 (W3 회고에서)
- 사용자 데이터가 통장 중심이라 출금만 보는 대시보드의 도넛이 비어 보임 → 입금/소득 분석으로 해소
- master plan의 월간 LLM 리포트 미구현 → 인사이트 리포트
- `essential` 컬럼이 W1부터 존재하나 미사용 → 필수/비필수 토글

## 비목표 (Out of Scope)
- 가맹점 정규화 (데이터 품질 테마 — 별도 사이클)
- 입금 구성 분석(급여 vs 이체 vs 기타 분해) — 수지/추세만 다룸
- 비밀번호 재설정, PWA, TanStack Query 등 다른 carry-over

---

## 기존 패턴 (준수)
- `category`(자동 분류) + `user_category_override`(사용자) → `effective_category = COALESCE(override, category)` — W3에서 검증된 단일 진실 공급원 패턴.
- 대시보드 집계는 `dashboard/service.py`의 asyncpg raw SQL, 출금 기준 `amount > 0`.
- LLM 비용은 `categorization/budget.py`가 월간 버킷(`llm_budget:{YYYY-MM}`)으로 가드, `llm_usage_log` 테이블에 기록(`purpose` 필드).
- 인증만 `Depends(current_user_id)`, DB는 `async with acquire()`.

---

## 1. 모듈/파일 구조 (수직 슬라이스)

```
apps/api/app/
├── insights/                 # ★ 신규 도메인 모듈
│   ├── routes.py             # GET /insights, POST /insights/generate
│   ├── schemas.py            # InsightResponse, InsightHighlight, InsightGenerateRequest
│   ├── service.py            # 집계 수집 → 프롬프트 → 캐시 오케스트레이션
│   └── llm.py                # Haiku 호출 → 구조화 JSON, InsightError
├── categorization/
│   └── essential.py          # ★ ESSENTIAL_DEFAULTS 맵 + helper
├── dashboard/
│   ├── routes.py             # ← 수정
│   └── service.py            # ← 수정
└── transactions/
    ├── routes.py             # ← 수정
    └── schemas.py            # ← 수정
```

---

## 2. DB 마이그레이션 — `0004_add_essential_override_and_insights.py` (raw SQL, --autogenerate 금지)

```sql
-- upgrade
ALTER TABLE transactions ADD COLUMN essential_override BOOLEAN NULL;

CREATE TABLE monthly_insights (
  user_id      UUID NOT NULL REFERENCES users(id),
  month        TEXT NOT NULL,              -- 'YYYY-MM'
  payload      JSONB NOT NULL,             -- {summary: str, highlights: [...]}
  generated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, month)
);

-- downgrade
DROP TABLE monthly_insights;
ALTER TABLE transactions DROP COLUMN essential_override;
```
- 기존 미사용 `essential` / `essential_reason` 컬럼은 그대로 둔다 (제거는 scope 밖).
- 백필 없음 (파생 계산이므로 불필요).

---

## 3. 데이터 모델 결정 — 필수/비필수 (파생 계산)

`essential`을 **저장하지 않고** `effective_category`에서 파생한다. 단일 진실 공급원 = 코드 맵.

`apps/api/app/categorization/essential.py`:
```python
# 19개 카테고리 → 필수 여부 기본값. CATEGORIES와 동기화 유지.
ESSENTIAL_DEFAULTS: dict[str, bool] = {
    "housing": True, "utilities": True, "telecom": True,
    "groceries": True, "health": True, "insurance": True,
    "transport": True, "lunch": True, "dinner": True,
    "savings": True, "income": True, "transfer": True,
    "coffee": False, "snack_late": False, "subscription": False,
    "entertainment": False, "shopping": False, "etc": False,
    "unknown": False,
}
ESSENTIAL_CATEGORIES: tuple[str, ...] = tuple(
    c for c, v in ESSENTIAL_DEFAULTS.items() if v
)

def is_essential(category: str) -> bool:
    return ESSENTIAL_DEFAULTS.get(category, False)
```
> 위 기본 매핑은 초안이며 구현 중 사용자 검토로 조정 가능 (예: lunch/dinner를 필수로 둘지). 로직 구조는 고정.

읽기 시: `effective_essential = essential_override (NOT NULL이면) else is_essential(effective_category)`.

집계 SQL:
```sql
CASE WHEN essential_override IS NOT NULL THEN essential_override
     ELSE (COALESCE(user_category_override, category) = ANY($cats::text[]))
END AS essential
```

---

## 4. API 엔드포인트

| 메서드/경로 | 기능 | 응답 |
|---|---|---|
| `GET /insights?month=YYYY-MM` | 캐시된 리포트 (없으면 null) | `InsightResponse \| null` |
| `POST /insights/generate` (body `{month}`, query `?force=false`) | 예산 체크 → 생성 → 캐시 → 반환. force 아니고 캐시 있으면 캐시 | `InsightResponse` |
| `GET /dashboard/summary?month=` | **확장**: income_total, net_savings, savings_rate 추가 | `SummaryResponse` |
| `GET /dashboard/cashflow-by-month?last_n=6` | **신규**: 월별 지출+수입 | `list[CashflowBucket]` |
| `GET /dashboard/by-essential?month=` | **신규**: 필수/비필수 합계 | `list[EssentialBucket]` |
| `PATCH /transactions/{id}/essential` (body `{essential_override: bool\|null}`) | **신규** 토글. null=자동 리셋 | 204 |

기존 `GET /dashboard/by-month`는 `cashflow-by-month`로 대체 (프론트가 후자 사용). by-month 라우트/서비스는 제거.

### 스키마 (snake_case 응답, 컨벤션 준수)
```python
# insights/schemas.py
class InsightHighlight(BaseModel):
    type: Literal["top_growth", "anomaly", "saving_tip"]
    title: str
    detail: str

class InsightResponse(BaseModel):
    month: str
    summary: str
    highlights: list[InsightHighlight]
    generated_at: datetime

class InsightGenerateRequest(BaseModel):
    month: str

# dashboard/routes.py — SummaryResponse 확장 필드
    income_total: Decimal
    net_savings: Decimal
    savings_rate: float | None   # income_total == 0 이면 null

class CashflowBucket(BaseModel):
    month: str
    expense: Decimal
    income: Decimal

class EssentialBucket(BaseModel):
    essential: bool
    amount: Decimal
    count: int

# transactions/schemas.py
class EssentialPatchRequest(BaseModel):
    essential_override: bool | None   # 항상 존재 (null = 자동 리셋)
# TransactionOut: essential/essential_reason 제거 →
    essential_override: bool | None
    effective_essential: bool
```

---

## 5. 데이터 흐름

### ① LLM 인사이트 (온디맨드 + DB 캐시)
```
POST /insights/generate {month}
 → monthly_insights 조회 — force=false & hit 시 즉시 반환
 → budget.has_room()? False → 503 BUDGET_EXCEEDED
 → dashboard.service로 집계 수집 (summary + by_category(이번달+전월, top_growth용) + top_merchants + by_essential)
 → insights.llm.generate_insight(집계) → JSON {summary, highlights:[{type,title,detail}]}
 → 파싱/검증 실패 → InsightError → 라우터에서 502 INSIGHT_GENERATION_FAILED
 → monthly_insights UPSERT (payload=jsonb) + budget.record_usage(..., purpose='insight')
 → InsightResponse 반환
```
- highlights 타입: `top_growth`(전월 대비 가장 늘어난 카테고리), `anomaly`(이상 지출 1건), `saving_tip`(절약 제안 1건).
- 프롬프트는 집계 수치(카테고리별 금액, top 가맹점, 전월 대비)를 한국어로 전달, 구조화 JSON 강제 (분류 llm.py의 enum 강제 패턴 차용).

### ② 입금/소득 (입금 = `amount < 0`)
- `income_total = SUM(-amount) WHERE amount < 0 AND effective_category <> 'transfer'` — **이체 제외**(타행이체 입금이 수입으로 잡혀 저축률 부풀려지는 것 방지).
- `expense_total` = 기존 `SummaryResponse.total_amount` (= `SUM(amount) WHERE amount > 0`). 신규 필드를 추가하지 않고 기존 필드를 지출 총액으로 그대로 사용.
- `net_savings = income_total - expense_total` (지출 > 수입이면 음수 — 정상).
- `savings_rate = net_savings / income_total * 100` (income_total == 0 이면 null).
- `cashflow-by-month`: 최근 N개월 expense·income 두 시리즈 (income은 이체 제외).

### ③ 필수/비필수 (파생 계산)
- `by-essential`: 위 CASE 식으로 필수/비필수 2버킷 합계.
- `PATCH /transactions/{id}/essential`: `essential_override`를 true/false/null로 업데이트. null은 명시적 자동 리셋.

---

## 6. 비용 가드 / 에러 처리
- `budget.record_usage`에 `purpose: str = 'categorize'` 파라미터 추가 (인사이트는 `'insight'`). 기존 호출부 무변경(기본값).
- 인사이트는 분류와 **동일 월간 예산 버킷** 공유, `has_room()` 재사용. 초과 시 `503 BUDGET_EXCEEDED`.
- 인사이트 LLM 파싱 실패는 **silent fallback 안 함** (사용자가 명시 요청한 액션) → `502 INSIGHT_GENERATION_FAILED`.
- 모든 에러: 라우터에서 직접 `HTTPException`, 코드 `UPPER_SNAKE_CASE`. `validate_month` 재사용 → 잘못된 월은 400 `INVALID_MONTH_FORMAT`.

---

## 7. 프론트엔드 — B+ 레이아웃

`dashboard.tsx` 재구성:
```
┌─────────────────────────────────────────────┐
│ ① InsightCard (full-width, [생성] 버튼)        │
├──────────┬──────────┬──────────┬─────────────┤
│ 지출 총액 │ 수입 총액 │ 순저축    │ 저축률       │  ← MetricStrip (확장 summary)
│ (±전월%) │          │          │             │
├──────────┴──────────┴──────────┴─────────────┤
│ ② 월별 추세 — 지출 ━━ + 수입 ━━ (LineChart)    │  ← CashflowChart
├───────────────────────┬───────────────────────┤
│ 카테고리별 지출 도넛(기존)│ ③ 필수/비필수 도넛      │  ← EssentialDonut
├───────────────────────┴───────────────────────┤
│ Top 5 가맹점 (기존)                             │
└─────────────────────────────────────────────┘
```
비대해지는 dashboard.tsx에서 위젯을 컴포넌트로 추출:
- `components/InsightCard.tsx` — 마운트 시 `GET /insights` (캐시), [생성] 버튼 → `POST /insights/generate`. 로딩/에러/예산초과(503) 상태 분기, highlights 렌더.
- `components/MetricStrip.tsx` — 4-up (지출 총액+전월±%, 수입 총액, 순저축, 저축률).
- `components/CashflowChart.tsx` — Tremor `LineChart`, 지출+수입 2시리즈. `colors`는 W3 tailwind safelist에 등록 확인(없으면 추가).
- `components/EssentialDonut.tsx` — 필수/비필수 `DonutChart`.
- `dashboard.tsx` — 페칭 + 조립만.

`lib/api.ts`: `fetchInsight`, `generateInsight`, `fetchCashflowByMonth`, `fetchByEssential` 추가. `SummaryResponse` 타입에 income_total/net_savings/savings_rate 추가. 신규 응답 타입.

`TransactionList.tsx` — 필수/비필수 3-state 토글 칩 (필수 / 비필수 / 자동):
- 자동 = `essential_override: null`, 필수 = `true`, 비필수 = `false` → `PATCH /transactions/{id}/essential`
- 표시는 `effective_essential`, override 여부는 칩 스타일로 구분 (CategoryChip override 패턴 차용).

---

## 8. 테스트 (`tests/`가 `app/` 미러)

| 디렉토리 | 테스트 |
|---|---|
| `tests/insights/` | 캐시 hit/miss, force 재생성, 예산초과→503, LLM JSON 파싱실패→502 (`_client` monkeypatch mock) |
| `tests/categorization/` | `essential.py` 맵 기본값, unknown→False |
| `tests/dashboard/` | summary 확장(income/net/savings_rate, income=0→null), cashflow-by-month(이체 제외 검증), by-essential(override 우선 + 기본맵 fallback) |
| `tests/transactions/` | PATCH essential(true/false/null 리셋), effective_essential SELECT, 404 |
| web (vitest) | InsightCard(생성/로딩/에러/예산초과), MetricStrip, EssentialDonut, TransactionList 3-state 토글 |

- 컨벤션: session-scoped 풀, `reset_tables` TRUNCATE, `_client` monkeypatch.
- 신규 픽스처: 입금(`amount<0`) + 이체 거래 포함 시드 (이체 제외 로직 검증) → `tests/fixtures/`.

---

## 9. 구현 순서 (Phase 분해 — 의존성 순)
1. 마이그레이션 0004 + `categorization/essential.py` 맵
2. transactions: PATCH `/{id}/essential` + `effective_essential` SELECT + 스키마
3. dashboard: summary 확장 + cashflow-by-month + by-essential (by-month 제거)
4. `budget.py` purpose 파라미터
5. insights 모듈 (llm + service + routes + 캐시)
6. web: lib/api.ts + 컴포넌트 추출 + B+ 조립
7. web: TransactionList 3-state 토글
8. 통합 검수 + 운영 배포 docs

---

## 알려진 한계
- 인사이트가 분류와 예산 버킷 공유 → 인사이트 대량 생성 시 분류 예산 잠식 가능 (MVP 허용, 차후 분리 가능).
- `income`/`savings` 카테고리 입금도 수입에 포함됨 (이체만 제외). 더 정교한 입금 구성 분석은 차후.
- `ESSENTIAL_DEFAULTS` 맵 변경은 코드 배포 필요 (사용자별 설정 아님).
