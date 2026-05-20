# Design: spendLens W3 — 본인 모드 UI 완성 (필터·검색·오버라이드·대시보드 + enum 확장)

작성일: 2026-05-20
저자: hattuping
상위 설계: `hattuping-main-design-20260428-152458.md` (Week 3)
선행 sub-projects:
- W1: `docs/superpowers/specs/2026-04-29-w1-skeleton-and-samsung-xlsx-parser-design.md`
- W2: `docs/superpowers/specs/2026-05-13-w2-multi-user-llm-categorization-design.md`

범위: spendLens 세 번째 sub-project (Week 3) — 2026-05-20 ~ 2026-06-03 (2주)
상태: DRAFT — 사용자 리뷰 후 writing-plans로 implementation plan 작성 예정

**변경 이력**
- 2026-05-20 v1: 초안. brainstorming 결과 반영 (6개 핵심 결정: scope=본인 모드 UI / single-page+dashboard 분리 / 인라인 드롭다운 오버라이드 / Tremor / Standard 차트 / enum +5).

---

## 1. Goal

W2까지 만든 인프라(다중 사용자 + 카테고리 자동 분류 + Redis + 우리/하나 파서) 위에 **본인 모드 UI를 완성**한다. master plan의 Week 3 항목을 단일 출하 단위로 묶음:

1. **거래 리스트 필터/검색**: 월별 + 카테고리 + 가맹점명 검색 — W2에서 본인 명세서 업로드 후 234건 거래가 한 페이지에 쏟아지던 문제 해결.
2. **인라인 카테고리 오버라이드**: 카테고리 칩 클릭 → 드롭다운 → 1클릭 변경. W2의 unknown 89건을 사용자가 직접 분류 가능.
3. **`/dashboard` 페이지**: 카테고리 도넛 + 월별 추이 + Top 가맹점 + 전월 대비 — Tremor 차트 라이브러리 기반.
4. **Enum 확장 14→19**: `savings`, `insurance`, `income`, `transfer`, `housing` 추가. 통장 거래(W2 Phase 7) 적정 분류 가능.
5. **통장 룰북 보강**: 정기적금/CMS-보험/월급/이체/월세 패턴을 rulebook에 추가. LLM 호출 없이 즉시 매칭.

이 단위가 끝나면 본인 명세서를 업로드한 사용자가:
- 한 화면에서 234건을 월·카테고리로 필터링하며 review할 수 있다
- 잘못 분류된 거래를 1클릭으로 수정할 수 있다
- 별도 `/dashboard` 페이지에서 월 마감 review를 차트로 본다

월간 LLM 인사이트 리포트, 비밀번호 재설정/이메일 인증, 추가 카드사는 W4 이후로 미룬다 (§9 참조).

## 2. Done 체크리스트

> spec 작성 시점(2026-05-20)에는 어느 것도 동작하지 않는 것이 정상.

- [ ] [W3 완료 시] 마이그레이션 `0003_add_user_category_override.py` 적용 — `transactions.user_category_override TEXT NULL` 컬럼 추가
- [ ] [W3 완료 시] `categorization/rulebook.py`의 `CATEGORIES` enum 14 → 19 (`savings`, `insurance`, `income`, `transfer`, `housing` 추가)
- [ ] [W3 완료 시] 통장 룰북 5개 패턴 추가 — 정기적금 → `savings`, CMS/보험 → `insurance`, 월급 → `income`, 이체 → `transfer`, 월세/임대 → `housing`
- [ ] [W3 완료 시] `categorization/llm.py`의 system prompt에 19 enum 반영
- [ ] [W3 완료 시] `PATCH /transactions/{id}` — body `{category}` 받아 `user_category_override` 저장, 19 enum 검증, 404 NOT_FOUND / 400 INVALID_CATEGORY
- [ ] [W3 완료 시] `GET /transactions` 응답에 `effective_category = COALESCE(user_category_override, category)` 포함. 쿼리 파라미터: `?month=YYYY-MM`, `?category=...`, `?search=keyword`, `?limit=N`, `?offset=M`
- [ ] [W3 완료 시] 4개 dashboard aggregate API:
  - `GET /dashboard/summary?month=YYYY-MM` → `{total_amount, transaction_count, prev_month_diff_pct}`
  - `GET /dashboard/by-category?month=YYYY-MM` → `[{category, amount, count}]`
  - `GET /dashboard/by-month?last_n=6` → `[{month, amount}]`
  - `GET /dashboard/top-merchants?month=YYYY-MM&limit=5` → `[{merchant_raw, amount, count}]`
- [ ] [W3 완료 시] `/app` 페이지: 상단 필터바 (월 dropdown / 카테고리 multi-select / 가맹점 검색 input), 거래 리스트 행에 인라인 카테고리 칩 (클릭 → 드롭다운 → 19 enum 선택 → PATCH 호출 → 낙관적 UI 업데이트)
- [ ] [W3 완료 시] `/dashboard` 신규 페이지: 월 선택 dropdown + 4 위젯 (도넛 / 막대 / Top 가맹점 리스트 / 전월 대비 카드) — Tremor 컴포넌트
- [ ] [W3 완료 시] `components/Nav.tsx`: 로그인 사용자 헤더에 `거래내역 / 대시보드 / 로그아웃` 링크
- [ ] [W3 완료 시] W2 unknown 89건을 5개 신규 enum + 룰북 5개 패턴으로 재분류 → unknown 비율 50% 이하로 감소 (사용자 명세서 기준)
- [ ] [W3 완료 시] PR 8건+ main 머지 (Phase 0~7 + 검수 PR)
- [ ] [W3 완료 시] README Status "W3 complete", CHANGELOG W3 entry, `docs/retros/w3.md`

## 3. Decisions

| 영역 | 결정 | 근거 |
|---|---|---|
| Scope | 본인 모드 UI 완성 (filter/search/override/dashboard + enum) | master plan Week 3 + W2 carry-overs 묶음 |
| 페이지 구조 | `/app` (single-page transactions) + 별도 `/dashboard` | 일상 사용은 `/app`, 월 review는 `/dashboard` |
| 카테고리 오버라이드 UX | **인라인 드롭다운** (칩 클릭 → 19 enum dropdown) | 1클릭 변경. 필수/비필수는 W4로 |
| 오버라이드 저장 형태 | `transactions.user_category_override TEXT NULL` 컬럼 (별도 테이블 없음) | LLM/룰북 결과(`category`)는 보존하면서 사용자 수정값 별도. `COALESCE(override, category)`로 표시 |
| Enum 확장 | 14 → **19** (+ `savings`, `insurance`, `income`, `transfer`, `housing`) | 통장 거래 분류 + 월세 분리 |
| 차트 라이브러리 | **Tremor** (`@tremor/react`) | master plan 권장. Tailwind 기반 (이미 의존성 있음). 대시보드 컴포넌트(DonutChart, BarChart, Card) 즉시 사용 |
| 차트 구성 | Standard 4 위젯: 도넛(카테고리) / 막대(월별 추이) / 리스트(Top 5 가맹점) / 카드(전월 대비) | master plan 권장 수준, MVP 적정 |
| `effective_category` 계산 위치 | DB SELECT 시점 (`COALESCE(user_category_override, category)`) | 응답에 한 필드로 노출. dashboard aggregate도 동일 COALESCE |
| 필터/검색 쿼리 위치 | 백엔드 (`/transactions?month=...&category=...&search=...`) | 거래 수 많으면 클라이언트 필터링 부담. 페이지네이션도 백엔드 |
| 페이지네이션 | `?limit=N&offset=M` (offset 기반) | 단순. W3 거래 수 규모(<10K)에선 cursor 불필요 |
| 검색 알고리즘 | `merchant_raw ILIKE '%keyword%'` (Postgres ILIKE) | 단순, 인덱스 없이 OK (사용자 데이터 규모). FTS는 W4+ |
| 카테고리 필터 | `&category=coffee,lunch` (CSV) → `effective_category IN (...)` | multi-select |
| 월 dropdown 옵션 | `MIN(txn_date) ~ MAX(txn_date)` 사이 모든 월 (`GET /transactions/months`) | 사용자 데이터 기반 동적 생성 |
| Dashboard 페이지 데이터 | 4 API 병렬 호출 + 클라이언트 캐시 (월 dropdown 변경 시 refetch) | TanStack Query는 W3+에서. 단순 useEffect + useState로 충분 |
| 전월 대비 계산 | `(this_total - prev_total) / prev_total * 100` (이전 월 없으면 `null`) | summary API에서 계산 |
| Top 가맹점 그룹화 | `GROUP BY merchant_raw, SUM(amount), COUNT(*) ORDER BY SUM DESC LIMIT 5` | 가맹점명 정규화는 W4+ (예: "씨유(CU) 구로JNK점" vs "씨유(CU) 구로원룸점"은 별개) |
| `amount` 처리 (대시보드) | 출금=양수, 입금=음수 그대로. **summary는 출금만(`amount > 0`) 집계**, 입금은 별도 표기 안 함 (W3) | 본인 모드는 "지출 가계부" 관점. 입금/소득 분석은 W4+ |
| 통장 룰북 패턴 | `정기적금` → savings, `CMS|보험|손해보험|하나생` → insurance, `월급|급여` → income, `이체|송금` → transfer, `월세|임대` → housing | merchant_raw에 `[구분] 적요` 형태로 들어옴 — 규칙은 substring 매칭 |
| 신규 카드사 | W3엔 없음 (W4+) | 본인 모드 UI 완성에 집중 |
| 모바일 반응형 | 기본 작동 수준만 (필터바 wrap, 차트 폭 100%) | PWA·세부 최적화는 W4+ |
| W3 기간 | 2026-05-20 ~ 2026-06-03 (2주) | W2(7일)보다 frontend 비중 ↑ (차트, nav, 인라인 UI). 보수적 |

## 4. Architecture

W2 다이어그램에서 **frontend가 두 페이지로 확장 + 4 aggregate API + 1 PATCH**가 추가된다. backend 인프라(Redis, Postgres, Caddy) 변경 없음. 신규 의존성: `@tremor/react` (frontend only).

```
┌─────────────────┐
│   사용자 브라우저  │
└────────┬────────┘
         │ HTTPS
         │
         ├──► spendlens.suim-app.store ──► Vercel (web)
         │      /login  /signup  /guest
         │      /app        ← 거래 리스트 + 필터/검색 + 인라인 드롭다운 (W3 신규)
         │      /dashboard  ← Tremor 4 위젯 (W3 신규)
         │
         │
         ├──► api.spendlens.suim-app.store ──► Lightsail VPS
         │   기존 W2 stack 그대로
         │   ├─ POST /auth/signup, /auth/login (W2)
         │   ├─ POST /transactions/upload (W1+W2: registry auto-detect)
         │   ├─ GET /transactions?month=...&category=...&search=...&limit=...&offset=... (W3 갱신)
         │   ├─ GET /transactions/months  ← month dropdown 옵션 (W3 신규)
         │   ├─ PATCH /transactions/{id} {category}  ← 사용자 오버라이드 (W3 신규)
         │   ├─ GET /dashboard/summary?month=...     (W3 신규)
         │   ├─ GET /dashboard/by-category?month=... (W3 신규)
         │   ├─ GET /dashboard/by-month?last_n=6     (W3 신규)
         │   └─ GET /dashboard/top-merchants?month=...&limit=5 (W3 신규)
         │
         └─ Postgres
            ├─ users, refresh_tokens, source_files, llm_usage_log (W1+W2)
            └─ transactions (W3 추가: user_category_override TEXT NULL)
```

**구성 요소 변경**:
- **Frontend**: `@tremor/react` 추가. 신규 라우트 `/dashboard`. `routes/app.tsx`에 필터바 + CategoryChip. `components/Nav.tsx` 신규.
- **Backend**: 신규 라우트 5개 (transactions/months, transactions/{id} PATCH, 4 dashboard aggregates). 기존 `GET /transactions`에 쿼리 파라미터 추가.
- **DB**: 마이그레이션 0003 — 컬럼 1개 추가. 19 enum은 코드 레벨 (CHECK 제약 없음 — schema-light 유지).
- **Redis**: 변경 없음. categorization 캐시는 그대로 (override는 캐시 외).
- **Categorization**: rulebook 5 신규 패턴, LLM system prompt enum 19개로 갱신.

## 5. Components / 디렉토리 구조

W3가 끝났을 때의 디렉토리 변경 (신규 + 변경 표시):

```
apps/api/app/
├── auth/                    # 무변경
├── categorization/
│   ├── rulebook.py          # 변경: CATEGORIES 14→19, 통장 5 패턴 추가
│   ├── llm.py               # 변경: _SYSTEM 프롬프트 enum 19개
│   ├── cache.py / budget.py / service.py  # 무변경
├── common/                  # 무변경
├── parsers/                 # 무변경
├── transactions/
│   ├── routes.py            # 변경: GET 쿼리 파라미터 + PATCH 신규
│   ├── schemas.py           # 변경: TransactionOut.effective_category, PatchRequest, FilterQuery
│   └── service.py           # 변경: update_category 함수 추가
├── dashboard/               # 신규 모듈 (도메인)
│   ├── __init__.py
│   ├── routes.py            # 4 aggregate endpoints
│   └── service.py           # SQL aggregate 쿼리
├── main.py                  # 변경: dashboard_router 등록
└── settings.py              # 무변경

apps/api/migrations/versions/
├── 0001_initial.py / 0002_add_llm_usage_log.py  # 무변경
└── 0003_add_user_category_override.py  # 신규

apps/api/tests/
├── categorization/test_rulebook.py  # 변경: 통장 5 패턴 케이스 추가, CATEGORIES len 19 검증
├── categorization/test_llm.py / test_service.py  # 변경: enum 19 반영
├── transactions/test_filter_query.py  # 신규
├── transactions/test_patch_override.py  # 신규
├── dashboard/                          # 신규
│   ├── __init__.py
│   ├── test_summary.py
│   ├── test_by_category.py
│   ├── test_by_month.py
│   └── test_top_merchants.py
└── conftest.py              # 무변경

apps/web/src/
├── App.tsx                  # 변경: /dashboard 라우트 등록
├── routes/
│   ├── app.tsx              # 변경: 필터바 + CategoryChip 통합
│   └── dashboard.tsx        # 신규: Tremor 4 위젯
├── components/
│   ├── Nav.tsx              # 신규: 헤더 nav (거래내역 / 대시보드 / 로그아웃)
│   ├── CategoryChip.tsx     # 신규: 인라인 드롭다운
│   ├── FilterBar.tsx        # 신규: 월/카테고리/검색 통합
│   ├── TransactionList.tsx  # 변경: CategoryChip 사용, 필터 props
│   └── (Nav.test.tsx, CategoryChip.test.tsx, FilterBar.test.tsx) 신규
├── lib/api.ts               # 변경: dashboard fetch 함수 추가, transactions PATCH
└── stores/auth.ts           # 무변경
```

## 6. Data Model

### 6-A. `transactions.user_category_override` (마이그레이션 0003)

```sql
ALTER TABLE transactions
  ADD COLUMN user_category_override TEXT NULL;

-- 인덱스는 추가하지 않음 (대부분 NULL, 정렬/필터 기준 아님)
```

- `NULL`이면 categorization.service가 채운 `category` 그대로 사용.
- `NOT NULL`이면 사용자가 명시적으로 수정한 값. `COALESCE(user_category_override, category)`로 응답에 노출.
- LLM/룰북이 다시 분류해도 사용자 수정값 덮어쓰지 않음 (재업로드 시).

### 6-B. CATEGORIES enum 14 → 19

```python
# apps/api/app/categorization/rulebook.py
CATEGORIES: tuple[str, ...] = (
    "coffee", "lunch", "dinner", "snack_late",
    "groceries", "transport", "telecom",
    "subscription", "entertainment", "health",
    "shopping", "utilities", "etc", "unknown",
    # W3 추가
    "savings", "insurance", "income", "transfer", "housing",
)
```

DB CHECK 제약 없음. 검증은:
- 업로드 시 categorization.service가 enum 안에서만 반환 (LLM 응답도 enum 강제).
- `PATCH /transactions/{id}` body에서 `category in CATEGORIES` 검증 — 위반 시 400 INVALID_CATEGORY.

### 6-C. `effective_category` (DB SELECT 표현)

```sql
SELECT
  id::text, txn_date, txn_time, amount, merchant_raw, merchant_normalized,
  approval_no, card_last4, installment_months, is_canceled,
  COALESCE(user_category_override, category) AS effective_category,
  category AS auto_category,            -- 디버그용 (어느 게 자동 분류 결과인지)
  user_category_override,               -- NULL이면 미수정 표시 가능
  essential, essential_reason
FROM transactions
WHERE user_id = $1
ORDER BY txn_date DESC, ...
```

`TransactionOut` 스키마에 `effective_category`, `auto_category`, `user_category_override` 3개 노출 — UI가 "수정됨" 뱃지 표시 가능 (auto vs override).

## 7. Data Flow

### 7-A. 필터/검색 흐름 — `GET /transactions`

```
사용자: /app 페이지에서 필터바 조작
  ├─ 월 dropdown 선택 → month = "2026-05"
  ├─ 카테고리 multi-select → categories = ["coffee", "lunch"]
  └─ 검색 input → search = "스타벅스"

Frontend: api.get(`/transactions?month=2026-05&category=coffee,lunch&search=스타벅스&limit=50&offset=0`)

Backend (transactions/routes.py):
  ├─ Depends(current_user_id) → user_id
  ├─ Query params parse (Pydantic FilterQuery)
  ├─ SQL build:
  │     SELECT ..., COALESCE(user_category_override, category) AS effective_category, ...
  │     FROM transactions
  │     WHERE user_id = $1
  │       AND ($2::text IS NULL OR to_char(txn_date, 'YYYY-MM') = $2)
  │       AND ($3::text[] IS NULL OR COALESCE(user_category_override, category) = ANY($3))
  │       AND ($4::text IS NULL OR merchant_raw ILIKE '%' || $4 || '%')
  │     ORDER BY txn_date DESC, txn_time DESC NULLS LAST, created_at DESC
  │     LIMIT $5 OFFSET $6
  └─ 응답: list[TransactionOut]
```

### 7-B. 인라인 카테고리 변경 흐름 — `PATCH /transactions/{id}`

```
사용자: 거래 행의 카테고리 칩 클릭 → 드롭다운 → "groceries" 선택

Frontend (CategoryChip.tsx):
  ├─ 낙관적 UI 업데이트 (즉시 칩 변경)
  ├─ api.patch(`/transactions/${id}`, { category: "groceries" })
  └─ 실패 시 칩 원복 + 토스트

Backend (transactions/routes.py):
  ├─ Depends(current_user_id) → user_id
  ├─ Pydantic PatchRequest: { category: Literal[19 enum strings] }
  │     enum 검증 실패 → 422
  ├─ DB UPDATE:
  │     UPDATE transactions
  │     SET user_category_override = $3
  │     WHERE id = $2 AND user_id = $1
  │     RETURNING id
  │     → row None → 404 NOT_FOUND
  └─ 응답: 204 No Content (또는 갱신된 TransactionOut)
```

### 7-C. Dashboard aggregate 흐름

`/dashboard` 페이지 로드:

```
Frontend: 4 fetch 병렬
  ├─ api.get(`/dashboard/summary?month=2026-05`)
  ├─ api.get(`/dashboard/by-category?month=2026-05`)
  ├─ api.get(`/dashboard/by-month?last_n=6`)
  └─ api.get(`/dashboard/top-merchants?month=2026-05&limit=5`)

Backend (dashboard/service.py): 각각 단일 aggregate SQL.

요약 SQL (summary 기준 — 출금만 집계: amount > 0):
  SELECT
    COALESCE(SUM(amount), 0) AS total_amount,
    COUNT(*) AS transaction_count
  FROM transactions
  WHERE user_id = $1
    AND to_char(txn_date, 'YYYY-MM') = $2
    AND amount > 0;

  -- 전월:
  SELECT COALESCE(SUM(amount), 0)
  FROM transactions
  WHERE user_id = $1
    AND to_char(txn_date, 'YYYY-MM') = $2_prev
    AND amount > 0;

  -- 응답: { total_amount, transaction_count, prev_month_diff_pct }
  -- prev_month가 0이면 prev_month_diff_pct = null
```

by-category (도넛):
```sql
SELECT COALESCE(user_category_override, category) AS cat,
       SUM(amount) AS amount,
       COUNT(*) AS count
FROM transactions
WHERE user_id = $1
  AND to_char(txn_date, 'YYYY-MM') = $2
  AND amount > 0
GROUP BY cat
ORDER BY amount DESC;
```

by-month (막대):
```sql
SELECT to_char(txn_date, 'YYYY-MM') AS month,
       SUM(amount) AS amount
FROM transactions
WHERE user_id = $1
  AND txn_date >= date_trunc('month', CURRENT_DATE - INTERVAL '5 months')
  AND amount > 0
GROUP BY month
ORDER BY month ASC;
```

top-merchants:
```sql
SELECT merchant_raw, SUM(amount) AS amount, COUNT(*) AS count
FROM transactions
WHERE user_id = $1
  AND to_char(txn_date, 'YYYY-MM') = $2
  AND amount > 0
GROUP BY merchant_raw
ORDER BY amount DESC
LIMIT 5;
```

### 7-D. 월 dropdown — `GET /transactions/months`

```sql
SELECT DISTINCT to_char(txn_date, 'YYYY-MM') AS month
FROM transactions
WHERE user_id = $1
ORDER BY month DESC;
```

응답: `["2026-05", "2026-04", "2026-03", ...]`. Frontend가 dropdown 옵션으로 사용.

## 8. Error Handling

| 코드 | HTTP | 발생 위치 |
|---|---|---|
| `INVALID_CATEGORY` | 422 | PATCH /transactions/{id} — Pydantic Literal 검증 (19 enum 외) |
| `NOT_FOUND` | 404 | PATCH /transactions/{id} — id 존재 안 함 또는 다른 사용자 거래 |
| `INVALID_MONTH_FORMAT` | 400 | 월 파라미터 형식 (YYYY-MM 아님) |
| `INVALID_LIMIT` | 400 | limit > 200 또는 음수 |

기존 W1/W2 패턴 그대로 — `HTTPException` 직접 raise, UPPER_SNAKE_CASE detail.

## 9. Out of Scope (W4+ 명시 이관)

- **월간 LLM 인사이트 리포트** (master plan Week 3 #4) — Anthropic 키 + 비용 모델링 필요. W4.
- **필수/비필수 토글** (master plan P5) — `essential` 컬럼은 이미 있음. UI는 W4.
- **비밀번호 재설정 / 이메일 인증** (W2 carry-over) — SMTP 통합 별도. W4.
- **TanStack Query** — W3는 단순 useEffect + useState. W4 또는 차후 필요시 도입.
- **가맹점 정규화** (씨유 구로JNK점 vs 구로원룸점 묶기) — W4+.
- **Top 가맹점 카테고리 그룹** (Top 가맹점을 카테고리별로) — W4+.
- **금액 범위 필터** / **정렬 토글** — W4+ (W3는 날짜 desc 고정).
- **차트 인터랙션** (도넛 클릭 → 거래 리스트 필터링) — W4+ 폴리시.
- **PWA / 모바일 푸시** — W4+.
- **회원 탈퇴 / GDPR export** — W4+.

## 10. Testing 전략

W2 conftest의 session-scoped DB 풀 + Redis flushdb + TRUNCATE CASCADE 패턴 유지.

신규 테스트 우선순위:
1. **rulebook 갱신** — `test_rulebook.py`에 19 enum 검증 + 통장 5 패턴 케이스 추가 (정기적금→savings, CMS→insurance 등)
2. **transactions PATCH** — `test_patch_override.py` — 정상 변경 / 19 enum 외 422 / 타인 거래 404 / `effective_category` 응답 확인
3. **transactions filter** — `test_filter_query.py` — month/category/search/pagination 조합 테스트
4. **dashboard aggregates** — 4 신규 테스트 파일, 각 endpoint 정상 응답 + 빈 데이터 처리 + 전월 대비 null 케이스
5. **frontend** — `Nav.test.tsx` (로그인 상태별 링크 표시), `CategoryChip.test.tsx` (드롭다운 열기 + 변경 + API 호출 + 낙관적 업데이트), `FilterBar.test.tsx` (URL 쿼리 동기화)
6. **E2E 회귀** — `test_upload_integration.py` 갱신: 업로드 후 effective_category 확인, PATCH 적용 후 dashboard summary가 갱신된 값 반영

## 11. ENV 키 명세

W3에 신규 ENV 없음. 기존:
- `DATABASE_URL`, `JWT_SECRET`, `ADMIN_EMAIL`, `ADMIN_PASSWORD_HASH`, `WEB_ORIGIN` (W1)
- `REDIS_URL`, `ANTHROPIC_API_KEY`, `ANTHROPIC_MONTHLY_BUDGET_USD` (W2)

## 12. CI/CD 워크플로

W2 패턴 그대로 — feature 브랜치 → PR → squash merge → deploy-api 자동 트리거.

신규 의존성:
- Frontend: `@tremor/react` 추가 (`pnpm -C apps/web add @tremor/react`). lockfile 갱신.
- Backend: 신규 의존성 없음.

마이그레이션 0003은 deploy-api의 컨테이너 entrypoint가 `alembic upgrade head`로 자동 적용.

## 13. W3 검수 시나리오 (PR 8건+ 머지 후)

1. `/login` admin 로그인 → 헤더에 `거래내역 / 대시보드 / 로그아웃` 보임
2. `/app` 진입 → 필터바 (월 dropdown / 카테고리 multi-select / 검색) + 거래 리스트
3. 월 dropdown에서 `2026-05` 선택 → 거래 리스트 그 월로 필터링
4. 카테고리 multi-select에서 `coffee` + `lunch` 선택 → 두 카테고리 거래만
5. 검색 input에 `스타벅스` → 매칭 거래만
6. unknown 카테고리 칩 클릭 → 드롭다운 → `groceries` 선택 → 칩 즉시 변경 + DB 반영
7. 새로고침 → 변경값 유지됨
8. 같은 명세서 재업로드 → user_category_override 보존됨 (categorization은 `category` 컬럼만 덮어쓰기)
9. `/dashboard` 진입 → 4 위젯 표시 (도넛 / 막대 / Top 5 / 전월 대비)
10. `/dashboard` 월 dropdown 변경 → 4 위젯 모두 갱신
11. W2 unknown 89건 중 통장 거래 → 룰북 5 패턴으로 자동 분류 (savings/insurance/income/transfer/housing)
12. 19 카테고리 외 값 PATCH 시도 → 422

## 14. Open Items (plan 단계에서 해결)

- [ ] Tremor 컴포넌트가 다크 모드 지원하는지 확인 (현재 /app은 dark 테마)
- [ ] Tremor SSR 호환성 (Vite SPA라 문제 없을 것이나 검증)
- [ ] `transactions.user_category_override` UPDATE의 `updated_at` 자동 갱신 필요한가? (현재 transactions 테이블에 updated_at 없음 — W4 결정)
- [ ] `/transactions/months`가 0건일 때 응답 (현재: `[]`, frontend가 disabled dropdown 표시)
- [ ] 월 dropdown에서 "전체 기간" 옵션 제공? (현재 spec: 단일 월만 선택)
- [ ] `top-merchants`의 `[타행이체] 정혜숙` 같은 이름이 노출되는 PII 문제 — 본인 모드라 OK이지만 명시 필요

## 15. Next Step

1. 본 spec을 사용자가 리뷰 → 수정/승인.
2. `superpowers:writing-plans`로 implementation plan 작성: `docs/superpowers/plans/2026-05-XX-w3-personal-mode-ui.md`. Phase 단위:
   - Phase 0: 마이그레이션 0003 + categorization enum 19 + 통장 룰북 5 + LLM 프롬프트 갱신
   - Phase 1: `PATCH /transactions/{id}` 백엔드 + 테스트
   - Phase 2: `GET /transactions` 필터/검색/페이지네이션 백엔드 + 테스트 + `GET /transactions/months`
   - Phase 3: 4 dashboard aggregate API + 테스트
   - Phase 4: Nav 컴포넌트 + Router 등록 + `/dashboard` 라우트 등록
   - Phase 5: `CategoryChip` + `FilterBar` 컴포넌트 + `/app` 통합
   - Phase 6: `routes/dashboard.tsx` Tremor 4 위젯 (`@tremor/react` 의존성 추가)
   - Phase 7: 통장 룰북 회귀 검수 (W2 unknown 89건 재분류율 측정)
   - Phase 8: 운영 배포 + README/CHANGELOG/회고
3. 각 Phase = 1 PR, main으로 squash merge (W2 흐름 동일).
