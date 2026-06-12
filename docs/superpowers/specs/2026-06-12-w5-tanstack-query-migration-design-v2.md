# W5 — TanStack Query 전면 전환 설계 (Frontend UX) — v2 (검토 반영)

> 작성일: 2026-06-12 (v1: 2026-06-11) · 트랙: 프론트 UX · 선행: W4 (분석 고도화, 로컬 main 머지 / origin 미푸시)
>
> **v2 변경 요약**: ① 쿼리 키 변경 시 데이터 소실 방지(`keepPreviousData`) ② 대시보드 로딩 판정을 `isPending` → `isLoading`으로 교정(비활성 쿼리 무한 로딩 버그) ③ 월 초기 선택을 useState 초기값이 아닌 파생값 패턴으로 교체 ④ 연속 토글 경합 가드(`isMutating`) ⑤ 업로드 무효화에 `["insight"]` 추가 및 인사이트 경합 cancel ⑥ v5 API 확인 완료로 버전 caveat 해소.

## 목표

`/app`·`/dashboard`의 데이터 패칭이 현재 전부 수동(`useEffect` + `useState` + axios)이다. 캐시가 없어 화면 전환·월 변경마다 전체를 다시 요청하고, 쓰기(카테고리 오버라이드·essential 토글·업로드)는 `setTxns`로 수동 낙관적 갱신을 한다. 검색 입력은 한 글자마다 요청한다.

이를 **TanStack Query v5**로 전환해:

- 읽기를 `useQuery`로 — 캐시 + 자동 재검증 + 로딩/에러 상태 일원화
- 쓰기를 `useMutation`으로 — 구조화된 낙관적 갱신(스냅샷 → 패치 → 실패 시 롤백 → 정산 시 무효화)
- search debounce(300ms)를 쿼리 키와 자연스럽게 결합
- **전환 UX 비회귀**: 필터·월 변경 시 이전 데이터를 유지(`keepPreviousData`)해, 현재 수동 패칭 대비 화면이 비었다 다시 그려지는 일이 없도록 한다

수동 `setTxns`/`setLoading`/`setError` 보일러플레이트를 제거하고, 무효화 일관성을 쿼리 키 팩토리로 보장한다.

## 비목표 (W5 범위 밖 — 별도 과제)

- 금액 범위 필터 / 정렬 토글
- 대시보드 차트 클릭 → `/app` 카테고리 필터 prefill
- PWA 매니페스트 / 모바일 푸시
- 웹 번들 코드 스플리팅(~1MB, W3부터의 기존 이슈)
- 백엔드 carry-over: `categorization/essential.py`의 `is_essential()` 미사용 함수, `by-essential` 도넛이 savings/transfer 출금을 필수로 집계하는 판단 건

## 기술 스택 / 컨벤션

- React 18 + Vite + TypeScript + Tailwind + `@tremor/react` + zustand(auth) + axios + react-router v6 (기존)
- **신규**: `@tanstack/react-query` v5 + dev `@tanstack/react-query-devtools`
- 패키지 매니저: **pnpm** (`pnpm add @tanstack/react-query`)
- 테스트: vitest + @testing-library/react
- 커밋: Conventional Commits, 스코프 `web`

> **라이브러리 버전 (확인 완료, v1 caveat 해소)**: 2026-06 기준 TanStack Query의 현행 메이저는 여전히 **v5**(최신 5.101.x)다. 본 설계가 가정한 v5 API — object 단일 시그니처 `useQuery`/`useMutation`, `onMutate`/`onError`/`onSettled` 낙관적 갱신, `QueryClientProvider`, `isPending`/`isLoading` 의미론, `placeholderData: keepPreviousData` — 는 모두 v5 표준 그대로다. v5에서 주의할 시그니처: `queryClient.cancelQueries`/`invalidateQueries`는 배열이 아닌 **`{ queryKey: [...] }` 객체 인자**를 받고, `useQuery`의 `onSuccess`/`onError` 콜백은 제거되었다(본 설계는 사용하지 않음). React 18 필수(충족).

---

## 아키텍처

### 1. 의존성 & Provider 설정

**Files:** `apps/web/package.json`, `apps/web/src/main.tsx`

- `pnpm add @tanstack/react-query` + `pnpm add -D @tanstack/react-query-devtools`
- `main.tsx`에서 `QueryClient` 싱글톤 생성. 기본 옵션:
  - `queries.staleTime`: 30_000 (30s) — 화면 재진입 시 즉시 재요청 방지
  - `queries.retry`: 1
  - `queries.refetchOnWindowFocus`: false (가계부 데이터는 포커스마다 갱신 불필요)
- `<QueryClientProvider client={queryClient}>`로 라우터를 감싼다.
- dev 모드(`import.meta.env.DEV`)에서만 `<ReactQueryDevtools />` 마운트.

### 2. 쿼리 레이어 — 신규 `apps/web/src/lib/queries.ts`

`lib/api.ts`의 fetch 함수(`fetchTransactions`, `fetchSummary`, …)는 **변경 없이 그대로 queryFn으로 재사용**한다. 단일 진실 출처(W3 컨벤션) 유지.

**쿼리 키 팩토리** — 무효화 일관성의 핵심:

```ts
export const qk = {
  transactions: (filters: TxnFilters) => ["transactions", filters] as const,
  months: () => ["months"] as const,
  dashboard: {
    summary: (month: string) => ["dashboard", "summary", month] as const,
    byCategory: (month: string) => ["dashboard", "byCategory", month] as const,
    cashflow: (lastN: number) => ["dashboard", "cashflow", lastN] as const,
    topMerchants: (month: string, limit: number) =>
      ["dashboard", "topMerchants", month, limit] as const,
    byEssential: (month: string) => ["dashboard", "byEssential", month] as const,
  },
  insight: (month: string) => ["insight", month] as const,
};
```

`TxnFilters` 타입은 `{ month?: string; category?: string[]; search?: string; limit: number }` — `useTransactions`의 인자이자 쿼리 키의 일부.

**Query 훅** (각각 `useQuery` 래퍼):

| 훅 | 키 | queryFn | enabled | placeholderData |
|---|---|---|---|---|
| `useTransactions(filters)` | `qk.transactions(filters)` | `fetchTransactions` | — | `keepPreviousData` |
| `useMonths()` | `qk.months()` | `fetchMonths` | — | — |
| `useSummary(month)` | `qk.dashboard.summary(m)` | `fetchSummary` | `!!month` | `keepPreviousData` |
| `useByCategory(month)` | `qk.dashboard.byCategory(m)` | `fetchByCategory` | `!!month` | `keepPreviousData` |
| `useCashflow(lastN)` | `qk.dashboard.cashflow(n)` | `fetchCashflowByMonth` | — | — |
| `useTopMerchants(month, limit)` | `qk.dashboard.topMerchants(m,n)` | `fetchTopMerchants` | `!!month` | `keepPreviousData` |
| `useByEssential(month)` | `qk.dashboard.byEssential(m)` | `fetchByEssential` | `!!month` | `keepPreviousData` |
| `useInsight(month)` | `qk.insight(m)` | `fetchInsight` | `!!month` | — |

> **`keepPreviousData`를 두는 이유 (v1 결함 수정)**: 쿼리 키가 바뀌면 v5의 `data`는 `undefined`로 떨어진다. 검색 한 글자(디바운스 후)·월 변경·카테고리 토글마다 목록/차트가 사라졌다 다시 그려지면 **현재 수동 패칭(이전 데이터 유지)보다 퇴보**다. `placeholderData: keepPreviousData`(`@tanstack/react-query`에서 import)로 이전 키의 데이터를 유지하고, 전환 중 표시는 `isPlaceholderData`로 한다(예: 목록 opacity 약간 낮춤). `useInsight`는 월이 바뀌면 다른 월의 인사이트 텍스트를 보여주는 게 오히려 혼란이라 제외.

**Mutation 훅**:

- **`useUploadStatement()`** — `mutationFn`: 기존 `api.post("/transactions/upload", fd)`.
  `onSuccess`: `invalidateQueries`로 `["transactions"]`, `["months"]`, `["dashboard"]`, **`["insight"]`** prefix 무효화(부분 키 매칭). 업로드는 어느 월/카테고리에 들어갈지 모르므로 낙관적 갱신 없이 무효화만. *(v1 수정: 거래가 추가되면 해당 월 인사이트도 낡은 데이터가 되므로 `["insight"]` 추가.)*

- **`useCategoryOverride()`** — `mutationFn`: `PATCH /transactions/{id}` (기존 api 함수).
  낙관적 갱신:
  - `onMutate({ id, category })`: `cancelQueries({ queryKey: ["transactions"] })` → `getQueriesData({ queryKey: ["transactions"] })`로 매칭되는 모든 캐시 엔트리 스냅샷 저장 → `setQueriesData({ queryKey: ["transactions"] }, updater)`로 해당 row의 `user_category_override`·`effective_category`를 낙관적으로 갱신 → context로 스냅샷 반환
  - `onError(_e, _v, ctx)`: 스냅샷 엔트리들을 `setQueryData`로 각각 롤백
  - `onSettled`: **`isMutating() === 1`(자기 자신뿐)일 때만** `invalidateQueries({ queryKey: ["transactions"] })` + `{ queryKey: ["dashboard"] }`(카테고리 집계 영향). *(v1 수정 — 경합 가드: 같은/다른 row를 빠르게 연속 변경하면 먼저 끝난 mutation의 invalidate가 아직 진행 중인 낙관적 상태를 서버의 옛 값으로 덮어쓴다. 마지막 mutation만 무효화하면 정합이 보장된다.)*

- **`useEssentialOverride()`** — `mutationFn`: `PATCH /transactions/{id}/essential`.
  낙관적 갱신 동일 패턴(스냅샷·패치·롤백·`isMutating` 가드 포함): row의 `essential_override` 갱신. `effective_essential`은 서버 파생값이라 낙관적 단계에서는 `essential_override`만 반영하고(W4 배포노트의 알려진 한계와 동일), `onSettled` 무효화로 정합. `onSettled`: `["transactions"]` + `["dashboard"]`(by-essential 영향).

- **`useGenerateInsight()`** — `mutationFn`: `POST /insights/generate?force=true` (body `{month}`).
  `onSuccess(data, { month })`: `cancelQueries({ queryKey: qk.insight(month) })` 후 `setQueryData(qk.insight(month), data)`로 즉시 갱신(재요청 불필요). *(v1 수정: cancel 없이는 진행 중이던 `useInsight` fetch가 늦게 도착해 방금 생성한 결과를 옛 응답으로 덮을 수 있다.)* 503/502 에러는 호출 컴포넌트에서 표시.

- **카테고리/essential 오버라이드가 `["insight"]`를 무효화하지 않는 이유(명시)**: 인사이트는 온디맨드 LLM 생성물이고 "다시 생성" 버튼이 있다. 오버라이드 한 번마다 인사이트를 무효화하면 비싼 재생성을 유도하거나 빈 상태가 되므로, 의도적으로 stale을 허용한다.

### 3. `useDebouncedValue` 훅 — 신규 `apps/web/src/lib/useDebouncedValue.ts`

```ts
export function useDebouncedValue<T>(value: T, delayMs: number): T
```

`useEffect` + `setTimeout`/`clearTimeout`로 `delayMs` 후 값을 반영하는 범용 훅. `/app` 검색에 사용.

### 4. `/app` 리팩토링 — `apps/web/src/routes/app.tsx`

- `txns`/`loading` useState 제거. `search`/`month`/`categories` 로컬 입력 상태는 유지.
- `const debouncedSearch = useDebouncedValue(search, 300)` 추가.
- 필터 객체: `{ month, category: categories, search: debouncedSearch, limit: 200 }` → `useTransactions(filters)`.
  - 월/카테고리 변경은 즉시 쿼리 키 변경(재요청), 검색만 디바운스. `keepPreviousData`로 전환 중에도 이전 목록 유지.
- 업로드: `const upload = useUploadStatement()` → `upload.mutate(file)`. 성공/실패 메시지는 `upload.isPending`/`upload.data`/`upload.error`로 표시(기존 `msg` 텍스트 UX 유지).
- 카테고리/essential 변경: `useCategoryOverride()`·`useEssentialOverride()`의 `mutate` 호출. 기존 수동 `onCategoryChange`/`onEssentialChange` + `setTxns` 제거. `TransactionList`/`CategoryChip`/`EssentialToggle`의 콜백 prop 시그니처는 유지하고, `app.tsx`에서 콜백 본문을 mutation 호출로 교체(컴포넌트 변경 최소화).
- 로딩 표시 *(v1 교정)*: **최초 로드**는 `useTransactions().isPending`(캐시가 전혀 없는 상태), **필터 전환 중**은 `isPlaceholderData`(이전 목록 유지 + 시각적 dim). 둘을 구분해야 검색 타이핑마다 스피너가 뜨는 회귀를 막는다.

> **컴포넌트 콜백 연결 방식**: `TransactionList`는 현재 `onCategoryChange(id, cat)`·`onEssentialChange(id, override)` 콜백을 받는다. 이 prop 인터페이스는 그대로 두고, `app.tsx`에서 콜백 본문을 `categoryOverride.mutate(...)`로 교체한다. 컴포넌트 자체와 그 테스트는 변경 불필요.

### 5. `/dashboard` 리팩토링 — `apps/web/src/routes/dashboard.tsx`

- **월 선택 (v1 결함 수정)**: v1의 "`month`는 useState로 유지하되 초기값은 `useMonths` 데이터에서 파생"은 구현 불가 — useState 초기값은 데이터가 나중에 도착해도 갱신되지 않는다. useEffect로 동기화하는 패턴도 깜빡임·이중 렌더를 만든다. 대신 **파생값 패턴**을 쓴다:

  ```ts
  const { data: months } = useMonths();
  const [selectedMonth, setSelectedMonth] = useState<string | null>(null); // 사용자가 고르기 전엔 null
  const month = selectedMonth ?? months?.[0]; // 실제 사용 값은 파생
  ```

  사용자가 셀렉트를 조작하면 `setSelectedMonth`, 그 전까지는 항상 최신 `months[0]`을 따른다. useEffect 동기화 금지.
- 5개 집계: `Promise.all` 제거 → `useSummary(month)`·`useByCategory(month)`·`useCashflow(6)`·`useTopMerchants(month,5)`·`useByEssential(month)` 개별 호출(자동 병렬, 각자 캐시). 월 키 쿼리는 `keepPreviousData`로 월 전환 시 차트가 통째로 사라지지 않는다.
- **판정 순서와 플래그 (v1 버그 수정)**:
  1. **빈 상태 먼저**: `useMonths().data?.length === 0` → "아직 거래가 없습니다".
  2. **로딩은 `isLoading` 조합**(`isPending` 아님): `enabled: !!month`로 비활성화된 쿼리는 v5에서 `isPending`이 계속 `true`다. v1대로 `isPending` 조합을 쓰면 months 로드 전·거래 0건 상태에서 **스피너가 영원히 돈다**. v5의 `isLoading`(= `isPending && isFetching`)은 비활성 쿼리에서 `false`이므로 이 문제가 없다.
  3. 에러: `isError` 조합으로 기존 통합 에러 배너 유지.
- `InsightCard`: 내부에서 `useInsight(month)` + `useGenerateInsight()` 사용하도록 전환("다시 생성" 버튼이 `useGenerateInsight().mutate({month})`).

### 6. 데이터 흐름 요약

```
사용자 입력(검색/월/카테고리)
  → (검색은 useDebouncedValue 300ms)
  → 쿼리 키 변경
  → useQuery 자동 재요청 / 캐시 히트
  → 전환 중에는 keepPreviousData로 이전 데이터 유지(isPlaceholderData)
  → 컴포넌트 렌더

쓰기(카테고리/essential 토글)
  → useMutation.mutate
  → onMutate: cancelQueries → 스냅샷 → 캐시 낙관적 패치(즉시 UI 반영)
  → 성공: onSettled, 마지막 mutation이면 invalidate → 서버 정합
  → 실패: onError 스냅샷 롤백
```

### 7. 에러 핸들링

- 쿼리 에러: 각 `useQuery`의 `isError`. dashboard는 조합해 단일 배너, `/app`은 빈 목록 + (선택) 메시지.
- mutation 에러: `onError` 롤백 + 컴포넌트에서 `mutation.error` 표시. 인사이트 503/502는 `InsightCard`에서 사용자 메시지로 변환(기존 동작 유지).
- axios 401(만료 토큰)은 기존 인터셉터/`ProtectedRoute` 흐름 유지 — 본 작업 범위 밖.

---

## 테스트 전략

- **기존 26개 web 테스트**: 대부분 props 기반 컴포넌트 테스트라 유지. `QueryClientProvider`가 필요한 라우트/훅 테스트를 위해 `apps/web/src/test/` 에 `renderWithClient(ui)` 헬퍼 추가 — 각 테스트마다 새 QueryClient, `defaultOptions: { queries: { retry: false }, mutations: { retry: false } }`.
- **신규 훅 테스트** (`lib/queries.test.tsx`):
  - `useCategoryOverride` 낙관적 갱신: mutate 직후 캐시 즉시 반영, mutationFn reject 시 **롤백** 확인
  - `useEssentialOverride` 동일
  - **연속 mutation 경합 가드**: 두 mutate를 연달아 발사 → 첫 번째 settle 시점엔 invalidate가 호출되지 않고 마지막 settle에서만 호출됨을 확인
  - `useUploadStatement` onSuccess 시 transactions/months/dashboard/**insight** 무효화 호출 확인
- **`useDebouncedValue` 테스트** (`lib/useDebouncedValue.test.tsx`): fake timers로 delay 후에만 값 반영 확인
- **라우트 통합**:
  - `/app` 검색 입력 → 디바운스 후 1회만 요청(요청 카운트 assert), 월/카테고리 변경은 즉시 요청. 전환 중 이전 목록이 DOM에 유지됨(`keepPreviousData`) assert
  - `/dashboard` months가 빈 배열일 때 무한 스피너가 아니라 빈 상태 문구가 렌더됨을 확인(isLoading 교정 회귀 방지)
- 실행: `cd apps/web && pnpm vitest run <path>`. 전체 회귀: `pnpm tsc --noEmit && pnpm vitest run && pnpm build`.

## 마이그레이션 / 호환성

- DB 마이그레이션 없음(순수 프론트).
- API 변경 없음 — 기존 엔드포인트·`lib/api.ts` 함수 그대로 사용.
- 빌드 산출물: 기존처럼 `tsc -b && vite build`. 번들에 TanStack Query 추가(경량, ~13KB gzip)되나 코드 스플리팅은 비목표.

## 알려진 한계 / 리스크

- essential 토글 낙관적 갱신 시 `effective_essential`(서버 파생)이 `onSettled` 무효화 전까지 살짝 어긋날 수 있음 — W4와 동일한 기존 한계, 무효화로 곧 정합.
- 카테고리/essential 오버라이드 후 해당 월 인사이트 텍스트는 의도적으로 무효화하지 않음(§2 참조) — 사용자가 "다시 생성"으로 갱신.
- `keepPreviousData`로 전환 중 화면이 이전 필터 결과를 잠시 보여줌 — `isPlaceholderData` dim 처리로 표시하되, 체감상 혼란스러우면 목록 헤더에 로딩 인디케이터 추가 검토.
- 검색 디바운스 300ms는 W3 retro의 carry-over 권고값. 체감 후 조정 가능.
