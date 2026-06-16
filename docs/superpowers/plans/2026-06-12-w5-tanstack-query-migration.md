# W5 TanStack Query 전면 전환 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `/app`·`/dashboard`의 수동 `useEffect`+`useState`+axios 패칭을 TanStack Query v5로 전환해, 캐시·자동 재검증·구조화된 낙관적 갱신·search debounce를 도입한다.

**Architecture:** `lib/api.ts`의 fetch 함수는 그대로 두고, 그 위에 중앙 쿼리 레이어 `lib/queries.ts`(쿼리 키 팩토리 + `useQuery`/`useMutation` 커스텀 훅)를 만든다. 라우트/컴포넌트는 이 훅만 호출한다. 키 변경 시 데이터 소실은 `keepPreviousData`로, 비활성 쿼리 무한 로딩은 `isLoading` 판정으로, 연속 토글 경합은 `isMutating` 가드로 막는다.

**Tech Stack:** React 18 / TypeScript / Vite / Tailwind / @tremor/react / zustand / axios / react-router v6 / **@tanstack/react-query v5** / vitest + @testing-library/react.

**Spec:** `docs/superpowers/specs/2026-06-12-w5-tanstack-query-migration-design-v2.md`

**공통 규칙 (CLAUDE.md):** 프론트 패키지 매니저 **pnpm**, snake_case 파일명은 백엔드 한정(프론트는 기존대로 camelCase 컴포넌트/PascalCase), Conventional Commits(스코프 `web`). 테스트: `cd apps/web && pnpm vitest run <path>`. 전체 회귀: `cd apps/web && pnpm tsc --noEmit && pnpm vitest run && pnpm build`.

**파일 구조 (생성/수정 맵):**
- Create `apps/web/src/lib/useDebouncedValue.ts` — 범용 디바운스 훅
- Create `apps/web/src/lib/queries.ts` — 쿼리 키 팩토리 + 모든 useQuery/useMutation 훅
- Create `apps/web/src/test/renderWithClient.tsx` — QueryClientProvider 테스트 헬퍼
- Modify `apps/web/src/main.tsx` — QueryClientProvider + Devtools
- Modify `apps/web/src/routes/app.tsx` — 훅 사용으로 전환
- Modify `apps/web/src/routes/dashboard.tsx` — 훅 사용으로 전환
- Modify `apps/web/src/components/InsightCard.tsx` — 훅 사용으로 전환
- Modify `apps/web/src/components/InsightCard.test.tsx` — QueryClientProvider 래핑
- Modify `apps/web/package.json` — 의존성 추가(pnpm add)

---

## Phase 1 — 인프라 (의존성 + Provider + 유틸 훅)

### Task 1: 의존성 설치 + QueryClientProvider + 테스트 헬퍼

**Files:**
- Modify: `apps/web/package.json` (pnpm add로 자동)
- Modify: `apps/web/src/main.tsx`
- Create: `apps/web/src/test/renderWithClient.tsx`

- [ ] **Step 1: 의존성 설치**

```bash
cd apps/web && pnpm add @tanstack/react-query && pnpm add -D @tanstack/react-query-devtools
```

Expected: `package.json`의 `dependencies`에 `@tanstack/react-query`, `devDependencies`에 `@tanstack/react-query-devtools` 추가. 설치 에러 없음.

- [ ] **Step 2: `main.tsx`에 Provider 추가**

`apps/web/src/main.tsx` 전체 교체:

```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { App } from "./App";
import "./index.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
      {import.meta.env.DEV && <ReactQueryDevtools initialIsOpen={false} />}
    </QueryClientProvider>
  </React.StrictMode>,
);
```

- [ ] **Step 3: 테스트 헬퍼 작성** — `apps/web/src/test/renderWithClient.tsx`

```tsx
import { render, type RenderOptions } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactElement, ReactNode } from "react";

/** retry 끄고 staleTime 0인 테스트 전용 QueryClient. */
export function makeTestClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: 0, gcTime: Infinity },
      mutations: { retry: false },
    },
  });
}

/** UI를 새 QueryClientProvider로 감싸 렌더. client를 함께 반환해 캐시 검사 가능. */
export function renderWithClient(ui: ReactElement, options?: RenderOptions) {
  const client = makeTestClient();
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  return { client, ...render(ui, { wrapper, ...options }) };
}
```

- [ ] **Step 4: 빌드/타입 확인**

Run: `cd apps/web && pnpm tsc --noEmit`
Expected: 0 errors (기존 코드는 그대로, 신규 파일 타입 통과).

- [ ] **Step 5: 기존 테스트 회귀 확인**

Run: `cd apps/web && pnpm vitest run`
Expected: 기존 26 passed (Provider 추가가 기존 테스트를 깨지 않음 — 기존 테스트는 main.tsx를 import하지 않음).

- [ ] **Step 6: Commit**

```bash
git add apps/web/package.json apps/web/pnpm-lock.yaml apps/web/src/main.tsx apps/web/src/test/renderWithClient.tsx
git commit -m "feat(web): add @tanstack/react-query + QueryClientProvider + test helper"
```

---

### Task 2: `useDebouncedValue` 훅

**Files:**
- Create: `apps/web/src/lib/useDebouncedValue.ts`
- Test: `apps/web/src/lib/useDebouncedValue.test.tsx`

- [ ] **Step 1: 실패 테스트 작성** — `apps/web/src/lib/useDebouncedValue.test.tsx`

```tsx
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useDebouncedValue } from "./useDebouncedValue";

describe("useDebouncedValue", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("returns initial value immediately", () => {
    const { result } = renderHook(() => useDebouncedValue("a", 300));
    expect(result.current).toBe("a");
  });

  it("delays updates until after delay", () => {
    const { result, rerender } = renderHook(
      ({ v }) => useDebouncedValue(v, 300),
      { initialProps: { v: "a" } },
    );
    rerender({ v: "ab" });
    rerender({ v: "abc" });
    // 아직 지연 시간 안 지남 → 옛 값 유지
    expect(result.current).toBe("a");
    act(() => vi.advanceTimersByTime(299));
    expect(result.current).toBe("a");
    act(() => vi.advanceTimersByTime(1));
    // 마지막 값만 반영
    expect(result.current).toBe("abc");
  });
});
```

- [ ] **Step 2: 실패 확인**

Run: `cd apps/web && pnpm vitest run src/lib/useDebouncedValue.test.tsx`
Expected: FAIL — `Cannot find module './useDebouncedValue'`.

- [ ] **Step 3: 구현** — `apps/web/src/lib/useDebouncedValue.ts`

```ts
import { useEffect, useState } from "react";

/** value가 delayMs 동안 변하지 않으면 그 값을 반영한다. 빠른 연속 변경은 마지막 값만 통과. */
export function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState<T>(value);

  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(t);
  }, [value, delayMs]);

  return debounced;
}
```

- [ ] **Step 4: 통과 확인**

Run: `cd apps/web && pnpm vitest run src/lib/useDebouncedValue.test.tsx`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/lib/useDebouncedValue.ts apps/web/src/lib/useDebouncedValue.test.tsx
git commit -m "feat(web): useDebouncedValue hook"
```

---

## Phase 2 — 쿼리 레이어 (`lib/queries.ts`)

### Task 3: 쿼리 키 팩토리 + 읽기(Query) 훅

**Files:**
- Create: `apps/web/src/lib/queries.ts`
- Test: `apps/web/src/lib/queries.read.test.tsx`

- [ ] **Step 1: 실패 테스트 작성** — `apps/web/src/lib/queries.read.test.tsx`

```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClientProvider } from "@tanstack/react-query";
import { makeTestClient } from "../test/renderWithClient";
import type { ReactNode } from "react";

const { fetchTransactionsMock, fetchSummaryMock } = vi.hoisted(() => ({
  fetchTransactionsMock: vi.fn(),
  fetchSummaryMock: vi.fn(),
}));
vi.mock("./api", () => ({
  fetchTransactions: fetchTransactionsMock,
  fetchMonths: vi.fn(),
  fetchSummary: fetchSummaryMock,
  fetchByCategory: vi.fn(),
  fetchCashflowByMonth: vi.fn(),
  fetchByEssential: vi.fn(),
  fetchTopMerchants: vi.fn(),
  fetchInsight: vi.fn(),
  generateInsight: vi.fn(),
  patchCategory: vi.fn(),
  patchEssential: vi.fn(),
  api: { post: vi.fn() },
}));

import { useTransactions, useSummary, qk } from "./queries";

function wrapper() {
  const client = makeTestClient();
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
}

describe("read hooks", () => {
  beforeEach(() => { fetchTransactionsMock.mockReset(); fetchSummaryMock.mockReset(); });

  it("qk.transactions includes filters for cache identity", () => {
    expect(qk.transactions({ limit: 200, search: "x" })).toEqual([
      "transactions", { limit: 200, search: "x" },
    ]);
  });

  it("useTransactions calls fetchTransactions with filters", async () => {
    fetchTransactionsMock.mockResolvedValueOnce([{ id: "t1" }]);
    const { result } = renderHook(() => useTransactions({ limit: 200 }), { wrapper: wrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(fetchTransactionsMock).toHaveBeenCalledWith({ limit: 200 });
    expect(result.current.data).toEqual([{ id: "t1" }]);
  });

  it("useSummary is disabled when month is undefined", async () => {
    const { result } = renderHook(() => useSummary(undefined), { wrapper: wrapper() });
    // enabled:false → fetch 안 함, isLoading false (v5: 비활성 쿼리)
    expect(fetchSummaryMock).not.toHaveBeenCalled();
    expect(result.current.isLoading).toBe(false);
  });
});
```

- [ ] **Step 2: 실패 확인**

Run: `cd apps/web && pnpm vitest run src/lib/queries.read.test.tsx`
Expected: FAIL — `Cannot find module './queries'`.

- [ ] **Step 3: 구현 (읽기 부분)** — `apps/web/src/lib/queries.ts`

```ts
import {
  useQuery,
  keepPreviousData,
} from "@tanstack/react-query";
import {
  fetchTransactions,
  fetchMonths,
  fetchSummary,
  fetchByCategory,
  fetchCashflowByMonth,
  fetchByEssential,
  fetchTopMerchants,
  fetchInsight,
} from "./api";

export type TxnFilters = {
  month?: string;
  category?: string[];
  search?: string;
  limit: number;
};

/** 쿼리 키 팩토리 — 무효화 일관성의 단일 출처. */
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

// --- 읽기 훅 ---

export function useTransactions(filters: TxnFilters) {
  return useQuery({
    queryKey: qk.transactions(filters),
    queryFn: () => fetchTransactions(filters),
    placeholderData: keepPreviousData,
  });
}

export function useMonths() {
  return useQuery({ queryKey: qk.months(), queryFn: fetchMonths });
}

export function useSummary(month: string | undefined) {
  return useQuery({
    queryKey: qk.dashboard.summary(month ?? ""),
    queryFn: () => fetchSummary(month!),
    enabled: !!month,
    placeholderData: keepPreviousData,
  });
}

export function useByCategory(month: string | undefined) {
  return useQuery({
    queryKey: qk.dashboard.byCategory(month ?? ""),
    queryFn: () => fetchByCategory(month!),
    enabled: !!month,
    placeholderData: keepPreviousData,
  });
}

export function useCashflow(lastN: number) {
  return useQuery({
    queryKey: qk.dashboard.cashflow(lastN),
    queryFn: () => fetchCashflowByMonth(lastN),
  });
}

export function useTopMerchants(month: string | undefined, limit: number) {
  return useQuery({
    queryKey: qk.dashboard.topMerchants(month ?? "", limit),
    queryFn: () => fetchTopMerchants(month!, limit),
    enabled: !!month,
    placeholderData: keepPreviousData,
  });
}

export function useByEssential(month: string | undefined) {
  return useQuery({
    queryKey: qk.dashboard.byEssential(month ?? ""),
    queryFn: () => fetchByEssential(month!),
    enabled: !!month,
    placeholderData: keepPreviousData,
  });
}

export function useInsight(month: string | undefined) {
  return useQuery({
    queryKey: qk.insight(month ?? ""),
    queryFn: () => fetchInsight(month!),
    enabled: !!month,
  });
}
```

- [ ] **Step 4: 통과 확인**

Run: `cd apps/web && pnpm vitest run src/lib/queries.read.test.tsx`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/lib/queries.ts apps/web/src/lib/queries.read.test.tsx
git commit -m "feat(web): query key factory + read hooks (useQuery)"
```

---

### Task 4: `useCategoryOverride` mutation (낙관적 갱신 + 롤백 + 경합 가드)

**Files:**
- Modify: `apps/web/src/lib/queries.ts`
- Test: `apps/web/src/lib/queries.category.test.tsx`

- [ ] **Step 1: 실패 테스트 작성** — `apps/web/src/lib/queries.category.test.tsx`

```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { QueryClientProvider } from "@tanstack/react-query";
import { makeTestClient } from "../test/renderWithClient";
import type { ReactNode } from "react";
import type { TransactionRow } from "./api";

const { patchCategoryMock } = vi.hoisted(() => ({ patchCategoryMock: vi.fn() }));
vi.mock("./api", () => ({
  fetchTransactions: vi.fn(), fetchMonths: vi.fn(), fetchSummary: vi.fn(),
  fetchByCategory: vi.fn(), fetchCashflowByMonth: vi.fn(), fetchByEssential: vi.fn(),
  fetchTopMerchants: vi.fn(), fetchInsight: vi.fn(), generateInsight: vi.fn(),
  patchCategory: patchCategoryMock, patchEssential: vi.fn(), api: { post: vi.fn() },
}));

import { useCategoryOverride, qk, type TxnFilters } from "./queries";

const FILTERS: TxnFilters = { limit: 200 };
function row(id: string, cat: string): TransactionRow {
  return {
    id, txn_date: "2026-05-01", txn_time: null, amount: "1000", merchant_raw: "M",
    category: cat, auto_category: cat, user_category_override: null, effective_category: cat,
  };
}
function ctx() {
  const client = makeTestClient();
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  return { client, wrapper };
}

describe("useCategoryOverride", () => {
  beforeEach(() => patchCategoryMock.mockReset());

  it("optimistically updates the cache, then rolls back on error", async () => {
    const { client, wrapper } = ctx();
    client.setQueryData(qk.transactions(FILTERS), [row("t1", "coffee")]);

    let reject!: (e: unknown) => void;
    patchCategoryMock.mockReturnValueOnce(new Promise((_res, rej) => { reject = rej; }));

    const { result } = renderHook(() => useCategoryOverride(), { wrapper });
    act(() => result.current.mutate({ id: "t1", category: "groceries" }));

    // 낙관적 반영
    await waitFor(() => {
      const rows = client.getQueryData<TransactionRow[]>(qk.transactions(FILTERS))!;
      expect(rows[0].effective_category).toBe("groceries");
      expect(rows[0].user_category_override).toBe("groceries");
    });

    // 실패 → 롤백
    act(() => reject({ message: "boom" }));
    await waitFor(() => {
      const rows = client.getQueryData<TransactionRow[]>(qk.transactions(FILTERS))!;
      expect(rows[0].effective_category).toBe("coffee");
      expect(rows[0].user_category_override).toBeNull();
    });
  });

  it("invalidates transactions only after the last concurrent mutation settles", async () => {
    const { client, wrapper } = ctx();
    client.setQueryData(qk.transactions(FILTERS), [row("t1", "coffee"), row("t2", "etc")]);
    const invalidateSpy = vi.spyOn(client, "invalidateQueries");

    let res1!: () => void, res2!: () => void;
    patchCategoryMock
      .mockReturnValueOnce(new Promise<void>((r) => { res1 = r; }))
      .mockReturnValueOnce(new Promise<void>((r) => { res2 = r; }));

    const { result } = renderHook(() => useCategoryOverride(), { wrapper });
    act(() => { result.current.mutate({ id: "t1", category: "a" }); });
    act(() => { result.current.mutate({ id: "t2", category: "b" }); });

    const txnInvalidations = () =>
      invalidateSpy.mock.calls.filter(
        ([arg]) => Array.isArray((arg as { queryKey?: unknown[] })?.queryKey) &&
          (arg as { queryKey: unknown[] }).queryKey[0] === "transactions",
      ).length;

    // 첫 mutation settle → 아직 두 번째가 진행 중이라 무효화 없음
    act(() => res1());
    await waitFor(() => expect(patchCategoryMock).toHaveBeenCalledTimes(2));
    expect(txnInvalidations()).toBe(0);

    // 마지막 mutation settle → 무효화 1회
    act(() => res2());
    await waitFor(() => expect(txnInvalidations()).toBe(1));
  });
});
```

- [ ] **Step 2: 실패 확인**

Run: `cd apps/web && pnpm vitest run src/lib/queries.category.test.tsx`
Expected: FAIL — `useCategoryOverride` export 없음.

- [ ] **Step 3: 구현** — `apps/web/src/lib/queries.ts` 상단 import에 mutation 심볼 추가하고 파일 끝에 훅 추가.

import 문을 다음으로 교체(읽기 전용에서 mutation 도구 추가):

```ts
import {
  useQuery,
  useMutation,
  useQueryClient,
  keepPreviousData,
  type QueryKey,
} from "@tanstack/react-query";
import {
  fetchTransactions,
  fetchMonths,
  fetchSummary,
  fetchByCategory,
  fetchCashflowByMonth,
  fetchByEssential,
  fetchTopMerchants,
  fetchInsight,
  generateInsight,
  patchCategory,
  patchEssential,
  api,
  type TransactionRow,
} from "./api";
```

파일 끝에 추가:

```ts
// --- mutation 훅 ---

const CATEGORY_MUTATION_KEY = ["override-category"] as const;

type TxnSnapshot = [QueryKey, TransactionRow[] | undefined][];

/** transactions 캐시의 모든 엔트리에서 한 row를 patch. 스냅샷을 반환. */
function patchTxnCaches(
  qc: ReturnType<typeof useQueryClient>,
  id: string,
  patch: Partial<TransactionRow>,
): TxnSnapshot {
  const snapshots = qc.getQueriesData<TransactionRow[]>({ queryKey: ["transactions"] });
  for (const [key, rows] of snapshots) {
    if (!rows) continue;
    qc.setQueryData<TransactionRow[]>(
      key,
      rows.map((r) => (r.id === id ? { ...r, ...patch } : r)),
    );
  }
  return snapshots;
}

function rollbackTxnCaches(
  qc: ReturnType<typeof useQueryClient>,
  snapshots: TxnSnapshot | undefined,
): void {
  snapshots?.forEach(([key, rows]) => qc.setQueryData(key, rows));
}

export function useCategoryOverride() {
  const qc = useQueryClient();
  return useMutation({
    mutationKey: CATEGORY_MUTATION_KEY,
    mutationFn: ({ id, category }: { id: string; category: string }) =>
      patchCategory(id, category),
    onMutate: async ({ id, category }) => {
      await qc.cancelQueries({ queryKey: ["transactions"] });
      const snapshots = patchTxnCaches(qc, id, {
        user_category_override: category,
        effective_category: category,
      });
      return { snapshots };
    },
    onError: (_err, _vars, context) => {
      rollbackTxnCaches(qc, context?.snapshots);
    },
    onSettled: () => {
      // 경합 가드: 마지막으로 settle되는 mutation만 무효화 (진행 중 낙관적 상태 보존)
      if (qc.isMutating({ mutationKey: CATEGORY_MUTATION_KEY }) === 1) {
        qc.invalidateQueries({ queryKey: ["transactions"] });
        qc.invalidateQueries({ queryKey: ["dashboard"] });
      }
    },
  });
}
```

> `patchTxnCaches`/`rollbackTxnCaches`는 Task 5의 essential 토글에서 재사용한다(DRY).

- [ ] **Step 4: 통과 확인**

Run: `cd apps/web && pnpm vitest run src/lib/queries.category.test.tsx`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/lib/queries.ts apps/web/src/lib/queries.category.test.tsx
git commit -m "feat(web): useCategoryOverride mutation (optimistic + rollback + race guard)"
```

---

### Task 5: `useEssentialOverride` mutation

**Files:**
- Modify: `apps/web/src/lib/queries.ts`
- Test: `apps/web/src/lib/queries.essential.test.tsx`

- [ ] **Step 1: 실패 테스트 작성** — `apps/web/src/lib/queries.essential.test.tsx`

```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { QueryClientProvider } from "@tanstack/react-query";
import { makeTestClient } from "../test/renderWithClient";
import type { ReactNode } from "react";
import type { TransactionRow } from "./api";

const { patchEssentialMock } = vi.hoisted(() => ({ patchEssentialMock: vi.fn() }));
vi.mock("./api", () => ({
  fetchTransactions: vi.fn(), fetchMonths: vi.fn(), fetchSummary: vi.fn(),
  fetchByCategory: vi.fn(), fetchCashflowByMonth: vi.fn(), fetchByEssential: vi.fn(),
  fetchTopMerchants: vi.fn(), fetchInsight: vi.fn(), generateInsight: vi.fn(),
  patchCategory: vi.fn(), patchEssential: patchEssentialMock, api: { post: vi.fn() },
}));

import { useEssentialOverride, qk, type TxnFilters } from "./queries";

const FILTERS: TxnFilters = { limit: 200 };
function row(id: string): TransactionRow {
  return {
    id, txn_date: "2026-05-01", txn_time: null, amount: "1000", merchant_raw: "M",
    category: "coffee", auto_category: "coffee", user_category_override: null,
    effective_category: "coffee", essential_override: null, effective_essential: false,
  };
}

describe("useEssentialOverride", () => {
  beforeEach(() => patchEssentialMock.mockReset());

  it("optimistically sets essential_override, rolls back on error", async () => {
    const client = makeTestClient();
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );
    client.setQueryData(qk.transactions(FILTERS), [row("t1")]);

    let reject!: (e: unknown) => void;
    patchEssentialMock.mockReturnValueOnce(new Promise((_r, rej) => { reject = rej; }));

    const { result } = renderHook(() => useEssentialOverride(), { wrapper });
    act(() => result.current.mutate({ id: "t1", essentialOverride: true }));

    await waitFor(() => {
      const rows = client.getQueryData<TransactionRow[]>(qk.transactions(FILTERS))!;
      expect(rows[0].essential_override).toBe(true);
    });

    act(() => reject({ message: "x" }));
    await waitFor(() => {
      const rows = client.getQueryData<TransactionRow[]>(qk.transactions(FILTERS))!;
      expect(rows[0].essential_override).toBeNull();
    });
  });
});
```

- [ ] **Step 2: 실패 확인**

Run: `cd apps/web && pnpm vitest run src/lib/queries.essential.test.tsx`
Expected: FAIL — `useEssentialOverride` export 없음.

- [ ] **Step 3: 구현** — `apps/web/src/lib/queries.ts` 끝에 추가:

```ts
const ESSENTIAL_MUTATION_KEY = ["override-essential"] as const;

export function useEssentialOverride() {
  const qc = useQueryClient();
  return useMutation({
    mutationKey: ESSENTIAL_MUTATION_KEY,
    mutationFn: ({ id, essentialOverride }: { id: string; essentialOverride: boolean | null }) =>
      patchEssential(id, essentialOverride),
    onMutate: async ({ id, essentialOverride }) => {
      await qc.cancelQueries({ queryKey: ["transactions"] });
      const snapshots = patchTxnCaches(qc, id, { essential_override: essentialOverride });
      return { snapshots };
    },
    onError: (_err, _vars, context) => {
      rollbackTxnCaches(qc, context?.snapshots);
    },
    onSettled: () => {
      if (qc.isMutating({ mutationKey: ESSENTIAL_MUTATION_KEY }) === 1) {
        qc.invalidateQueries({ queryKey: ["transactions"] });
        qc.invalidateQueries({ queryKey: ["dashboard"] });
      }
    },
  });
}
```

- [ ] **Step 4: 통과 확인**

Run: `cd apps/web && pnpm vitest run src/lib/queries.essential.test.tsx`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/lib/queries.ts apps/web/src/lib/queries.essential.test.tsx
git commit -m "feat(web): useEssentialOverride mutation (optimistic + rollback)"
```

---

### Task 6: `useUploadStatement` mutation

**Files:**
- Modify: `apps/web/src/lib/queries.ts`
- Test: `apps/web/src/lib/queries.upload.test.tsx`

- [ ] **Step 1: 실패 테스트 작성** — `apps/web/src/lib/queries.upload.test.tsx`

```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { QueryClientProvider } from "@tanstack/react-query";
import { makeTestClient } from "../test/renderWithClient";
import type { ReactNode } from "react";

const { postMock } = vi.hoisted(() => ({ postMock: vi.fn() }));
vi.mock("./api", () => ({
  fetchTransactions: vi.fn(), fetchMonths: vi.fn(), fetchSummary: vi.fn(),
  fetchByCategory: vi.fn(), fetchCashflowByMonth: vi.fn(), fetchByEssential: vi.fn(),
  fetchTopMerchants: vi.fn(), fetchInsight: vi.fn(), generateInsight: vi.fn(),
  patchCategory: vi.fn(), patchEssential: vi.fn(), api: { post: postMock },
}));

import { useUploadStatement } from "./queries";

describe("useUploadStatement", () => {
  beforeEach(() => postMock.mockReset());

  it("posts the file and invalidates transactions/months/dashboard/insight on success", async () => {
    const client = makeTestClient();
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );
    const invalidateSpy = vi.spyOn(client, "invalidateQueries");
    postMock.mockResolvedValueOnce({ data: { uploaded: 3, skipped: 1 } });

    const { result } = renderHook(() => useUploadStatement(), { wrapper });
    act(() => result.current.mutate(new File(["x"], "a.xlsx")));

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(postMock).toHaveBeenCalledWith("/transactions/upload", expect.any(FormData));
    expect(result.current.data).toEqual({ uploaded: 3, skipped: 1 });

    const invalidatedRoots = invalidateSpy.mock.calls.map(
      ([arg]) => (arg as { queryKey: unknown[] }).queryKey[0],
    );
    expect(invalidatedRoots).toEqual(
      expect.arrayContaining(["transactions", "months", "dashboard", "insight"]),
    );
  });
});
```

- [ ] **Step 2: 실패 확인**

Run: `cd apps/web && pnpm vitest run src/lib/queries.upload.test.tsx`
Expected: FAIL — `useUploadStatement` export 없음.

- [ ] **Step 3: 구현** — `apps/web/src/lib/queries.ts` 끝에 추가:

```ts
export type UploadResult = { uploaded: number; skipped: number };

export function useUploadStatement() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (file: File): Promise<UploadResult> => {
      const fd = new FormData();
      fd.append("file", file);
      const { data } = await api.post<UploadResult>("/transactions/upload", fd);
      return data;
    },
    onSuccess: () => {
      // 업로드는 어느 월/카테고리에 떨어질지 모르므로 관련 캐시 전체 무효화.
      qc.invalidateQueries({ queryKey: ["transactions"] });
      qc.invalidateQueries({ queryKey: ["months"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      qc.invalidateQueries({ queryKey: ["insight"] });
    },
  });
}
```

- [ ] **Step 4: 통과 확인**

Run: `cd apps/web && pnpm vitest run src/lib/queries.upload.test.tsx`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/lib/queries.ts apps/web/src/lib/queries.upload.test.tsx
git commit -m "feat(web): useUploadStatement mutation (invalidate on success)"
```

---

### Task 7: `useGenerateInsight` mutation

**Files:**
- Modify: `apps/web/src/lib/queries.ts`
- Test: `apps/web/src/lib/queries.insight.test.tsx`

- [ ] **Step 1: 실패 테스트 작성** — `apps/web/src/lib/queries.insight.test.tsx`

```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { QueryClientProvider } from "@tanstack/react-query";
import { makeTestClient } from "../test/renderWithClient";
import type { ReactNode } from "react";

const { generateInsightMock } = vi.hoisted(() => ({ generateInsightMock: vi.fn() }));
vi.mock("./api", () => ({
  fetchTransactions: vi.fn(), fetchMonths: vi.fn(), fetchSummary: vi.fn(),
  fetchByCategory: vi.fn(), fetchCashflowByMonth: vi.fn(), fetchByEssential: vi.fn(),
  fetchTopMerchants: vi.fn(), fetchInsight: vi.fn(), generateInsight: generateInsightMock,
  patchCategory: vi.fn(), patchEssential: vi.fn(), api: { post: vi.fn() },
}));

import { useGenerateInsight, qk } from "./queries";

describe("useGenerateInsight", () => {
  beforeEach(() => generateInsightMock.mockReset());

  it("writes the result into the insight cache on success", async () => {
    const client = makeTestClient();
    const wrapper = ({ children }: { children: ReactNode }) => (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );
    const payload = {
      month: "2026-05", summary: "요약",
      highlights: [{ type: "saving_tip", title: "t", detail: "d" }],
      generated_at: "2026-06-12T00:00:00Z",
    };
    generateInsightMock.mockResolvedValueOnce(payload);

    const { result } = renderHook(() => useGenerateInsight(), { wrapper });
    act(() => result.current.mutate({ month: "2026-05", force: true }));

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(generateInsightMock).toHaveBeenCalledWith("2026-05", true);
    expect(client.getQueryData(qk.insight("2026-05"))).toEqual(payload);
  });
});
```

- [ ] **Step 2: 실패 확인**

Run: `cd apps/web && pnpm vitest run src/lib/queries.insight.test.tsx`
Expected: FAIL — `useGenerateInsight` export 없음.

- [ ] **Step 3: 구현** — `apps/web/src/lib/queries.ts` 끝에 추가:

```ts
export function useGenerateInsight() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ month, force }: { month: string; force: boolean }) =>
      generateInsight(month, force),
    onSuccess: async (data, { month }) => {
      // 진행 중이던 useInsight fetch가 늦게 도착해 방금 결과를 덮지 않도록 cancel 후 직접 기록.
      await qc.cancelQueries({ queryKey: qk.insight(month) });
      qc.setQueryData(qk.insight(month), data);
    },
  });
}
```

- [ ] **Step 4: 통과 확인 + 쿼리 레이어 전체 회귀**

Run: `cd apps/web && pnpm vitest run src/lib/`
Expected: Task 2~7 테스트 전부 PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/lib/queries.ts apps/web/src/lib/queries.insight.test.tsx
git commit -m "feat(web): useGenerateInsight mutation (cancel + setQueryData)"
```

---

## Phase 3 — 화면 전환

### Task 8: `/app` 리팩토링 (useTransactions + debounce + mutations)

**Files:**
- Modify: `apps/web/src/routes/app.tsx`
- Test: `apps/web/src/routes/app.test.tsx`

- [ ] **Step 1: 실패 테스트 작성** — `apps/web/src/routes/app.test.tsx`

```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { renderWithClient } from "../test/renderWithClient";
import { useAuth } from "../stores/auth";

const { fetchTransactionsMock } = vi.hoisted(() => ({ fetchTransactionsMock: vi.fn() }));
vi.mock("../lib/api", () => ({
  fetchTransactions: fetchTransactionsMock,
  fetchMonths: vi.fn(), fetchSummary: vi.fn(), fetchByCategory: vi.fn(),
  fetchCashflowByMonth: vi.fn(), fetchByEssential: vi.fn(), fetchTopMerchants: vi.fn(),
  fetchInsight: vi.fn(), generateInsight: vi.fn(),
  patchCategory: vi.fn(), patchEssential: vi.fn(), api: { post: vi.fn() },
}));

import { AppPage } from "./app";

describe("AppPage", () => {
  beforeEach(() => {
    fetchTransactionsMock.mockReset().mockResolvedValue([]);
    useAuth.getState().setAccess("test-token"); // 인증 상태 → /login 리다이렉트 방지
  });

  it("debounces search: only the final value triggers a fetch", async () => {
    renderWithClient(<MemoryRouter><AppPage /></MemoryRouter>);
    // 초기 1회 호출
    await waitFor(() => expect(fetchTransactionsMock).toHaveBeenCalled());

    const box = screen.getByPlaceholderText(/가맹점/);
    fireEvent.change(box, { target: { value: "c" } });
    fireEvent.change(box, { target: { value: "co" } });
    fireEvent.change(box, { target: { value: "cof" } });

    // 디바운스(300ms) 후 최종 값으로 호출됨
    await waitFor(
      () => expect(fetchTransactionsMock).toHaveBeenCalledWith(
        expect.objectContaining({ search: "cof" }),
      ),
      { timeout: 1500 },
    );
    // 중간 단일 글자로는 호출되지 않음
    const calledSearches = fetchTransactionsMock.mock.calls.map(([f]) => f.search);
    expect(calledSearches).not.toContain("c");
    expect(calledSearches).not.toContain("co");
  });
});
```

> `FilterBar`의 검색 입력 placeholder가 `/가맹점/`과 매칭되는지 구현 시 확인하고, 다르면 실제 placeholder 정규식으로 교체.

- [ ] **Step 2: 실패 확인**

Run: `cd apps/web && pnpm vitest run src/routes/app.test.tsx`
Expected: FAIL — 현재 `app.tsx`는 디바운스 없이 매 입력마다 호출하므로 `calledSearches`에 "c"/"co" 포함 → assert 실패(또는 구조 차이로 실패).

- [ ] **Step 3: `app.tsx` 전체 교체**

```tsx
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../stores/auth";
import { UploadDropzone } from "../components/UploadDropzone";
import { TransactionList } from "../components/TransactionList";
import { FilterBar } from "../components/FilterBar";
import { useDebouncedValue } from "../lib/useDebouncedValue";
import {
  useTransactions,
  useUploadStatement,
  useCategoryOverride,
  useEssentialOverride,
} from "../lib/queries";

export function AppPage() {
  const [month, setMonth] = useState<string | null>(null);
  const [categories, setCategories] = useState<string[]>([]);
  const [search, setSearch] = useState("");
  const debouncedSearch = useDebouncedValue(search, 300);
  const isAuthed = useAuth((s) => s.isAuthed());
  const nav = useNavigate();

  useEffect(() => {
    if (!isAuthed) nav("/login");
  }, [isAuthed, nav]);

  const txnsQuery = useTransactions({
    month: month ?? undefined,
    category: categories.length ? categories : undefined,
    search: debouncedSearch || undefined,
    limit: 200,
  });
  const upload = useUploadStatement();
  const categoryOverride = useCategoryOverride();
  const essentialOverride = useEssentialOverride();

  const txns = txnsQuery.data ?? [];

  let msg: string | null = null;
  if (upload.isPending) {
    msg = "업로드 중...";
  } else if (upload.isError) {
    const detail =
      (upload.error as { response?: { data?: { detail?: unknown } } })?.response?.data
        ?.detail ?? (upload.error as Error).message;
    msg = `실패: ${JSON.stringify(detail)}`;
  } else if (upload.isSuccess) {
    msg = `업로드 ${upload.data.uploaded}건, dedup ${upload.data.skipped}건`;
  }

  return (
    <div className="min-h-screen">
      <div className="max-w-3xl mx-auto p-8">
        <h2 className="text-2xl mb-4">My Transactions</h2>
        <UploadDropzone onFile={(file) => upload.mutate(file)} />
        {msg && <p className="my-4 text-sm text-zinc-400">{msg}</p>}
      </div>
      <FilterBar
        month={month}
        setMonth={setMonth}
        categories={categories}
        setCategories={setCategories}
        search={search}
        setSearch={setSearch}
      />
      <div className="max-w-3xl mx-auto p-8">
        {txnsQuery.isPending ? (
          <p className="text-zinc-400 text-sm">로딩…</p>
        ) : (
          <div className={txnsQuery.isPlaceholderData ? "opacity-60 transition-opacity" : "transition-opacity"}>
            <TransactionList
              items={txns}
              onCategoryChange={(id, newCategory) =>
                categoryOverride.mutate({ id, category: newCategory })}
              onEssentialChange={(id, override) =>
                essentialOverride.mutate({ id, essentialOverride: override })}
            />
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: 통과 확인**

Run: `cd apps/web && pnpm vitest run src/routes/app.test.tsx`
Expected: PASS. (placeholder 불일치로 실패하면 Step 1 주석대로 실제 placeholder로 교체 후 재실행.)

- [ ] **Step 5: 타입 + 컴포넌트 테스트 회귀**

Run: `cd apps/web && pnpm tsc --noEmit && pnpm vitest run src/components/`
Expected: 타입 0 errors, `TransactionList`/`CategoryChip`/`EssentialToggle` 테스트 PASS(콜백 시그니처 불변).

- [ ] **Step 6: Commit**

```bash
git add apps/web/src/routes/app.tsx apps/web/src/routes/app.test.tsx
git commit -m "feat(web): /app on TanStack Query — useTransactions + debounce + mutations"
```

---

### Task 9: `InsightCard` 전환 (useInsight + useGenerateInsight)

**Files:**
- Modify: `apps/web/src/components/InsightCard.tsx`
- Modify: `apps/web/src/components/InsightCard.test.tsx`

- [ ] **Step 1: 테스트 갱신** — `apps/web/src/components/InsightCard.test.tsx` 전체 교체 (QueryClientProvider 래핑 + 동일 시나리오)

```tsx
import { describe, expect, it, vi, beforeEach } from "vitest";
import { screen, fireEvent, waitFor } from "@testing-library/react";
import { renderWithClient } from "../test/renderWithClient";

const { fetchMock, genMock } = vi.hoisted(() => ({ fetchMock: vi.fn(), genMock: vi.fn() }));
vi.mock("../lib/api", () => ({
  fetchInsight: fetchMock,
  generateInsight: genMock,
  fetchTransactions: vi.fn(), fetchMonths: vi.fn(), fetchSummary: vi.fn(),
  fetchByCategory: vi.fn(), fetchCashflowByMonth: vi.fn(), fetchByEssential: vi.fn(),
  fetchTopMerchants: vi.fn(), patchCategory: vi.fn(), patchEssential: vi.fn(),
  api: { post: vi.fn() },
}));

import { InsightCard } from "./InsightCard";

describe("InsightCard", () => {
  beforeEach(() => { fetchMock.mockReset(); genMock.mockReset(); });

  it("shows generate button when no cached insight", async () => {
    fetchMock.mockResolvedValue(null);
    renderWithClient(<InsightCard month="2026-05" />);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /인사이트 생성/ })).toBeInTheDocument());
  });

  it("renders highlights after generate", async () => {
    fetchMock.mockResolvedValue(null);
    genMock.mockResolvedValueOnce({
      month: "2026-05", summary: "요약입니다",
      highlights: [{ type: "saving_tip", title: "팁", detail: "내용" }],
      generated_at: "2026-06-12T00:00:00Z",
    });
    renderWithClient(<InsightCard month="2026-05" />);
    await waitFor(() => screen.getByRole("button", { name: /인사이트 생성/ }));
    fireEvent.click(screen.getByRole("button", { name: /인사이트 생성/ }));
    await waitFor(() => expect(screen.getByText("요약입니다")).toBeInTheDocument());
    expect(screen.getByText("팁")).toBeInTheDocument();
  });

  it("shows budget error on 503", async () => {
    fetchMock.mockResolvedValue(null);
    genMock.mockRejectedValueOnce({ response: { status: 503 } });
    renderWithClient(<InsightCard month="2026-05" />);
    await waitFor(() => screen.getByRole("button", { name: /인사이트 생성/ }));
    fireEvent.click(screen.getByRole("button", { name: /인사이트 생성/ }));
    await waitFor(() => expect(screen.getByText(/예산/)).toBeInTheDocument());
  });
});
```

- [ ] **Step 2: 실패 확인**

Run: `cd apps/web && pnpm vitest run src/components/InsightCard.test.tsx`
Expected: FAIL — 현재 `InsightCard`는 자체 useState/useEffect 패칭이라 QueryClientProvider와 무관하나, genMock가 `generateInsight(month, force)`로 호출되는 인자/캐시 동작 차이로 일부 실패(특히 전환 전이라 통과할 수도 있음 — 통과하면 Step 3로 진행해 훅 기반으로 바꾼 뒤 재확인).

- [ ] **Step 3: `InsightCard.tsx` 전체 교체**

```tsx
import { Card, Title, Text } from "@tremor/react";
import { useInsight, useGenerateInsight } from "../lib/queries";

const TYPE_LABEL: Record<string, string> = {
  top_growth: "📈 급증", anomaly: "⚠️ 이상", saving_tip: "💡 절약 팁",
};

export function InsightCard({ month }: { month: string }) {
  const insightQuery = useInsight(month);
  const generate = useGenerateInsight();
  const insight = insightQuery.data ?? null;
  const loading = generate.isPending;

  let error: string | null = null;
  if (generate.isError) {
    const status = (generate.error as { response?: { status?: number } })?.response?.status;
    error =
      status === 503
        ? "이번 달 LLM 예산을 초과했습니다. 나중에 다시 시도하세요."
        : "인사이트 생성에 실패했습니다.";
  }

  function onGenerate() {
    // 이미 인사이트가 있으면 "다시 생성" → force=true로 캐시 무시하고 재생성
    generate.mutate({ month, force: insight != null });
  }

  return (
    <Card>
      <div className="flex items-center justify-between">
        <Title>월간 인사이트</Title>
        <button onClick={onGenerate} disabled={loading}
          className="bg-blue-700 text-white text-xs px-3 py-1 rounded disabled:opacity-50">
          {loading ? "생성 중…" : insight ? "다시 생성" : "인사이트 생성"}
        </button>
      </div>
      {error && <Text className="text-red-400 mt-2">{error}</Text>}
      {insight && (
        <div className="mt-3 space-y-2">
          <Text className="text-zinc-200">{insight.summary}</Text>
          <ul className="space-y-1">
            {insight.highlights.map((h, i) => (
              <li key={i} className="text-sm text-zinc-300">
                <span className="text-zinc-400">{TYPE_LABEL[h.type] ?? h.type}</span>{" "}
                <b>{h.title}</b> — {h.detail}
              </li>
            ))}
          </ul>
        </div>
      )}
      {!insight && !error && (
        <Text className="text-zinc-500 mt-2">버튼을 눌러 이번 달 지출 인사이트를 생성하세요.</Text>
      )}
    </Card>
  );
}
```

- [ ] **Step 4: 통과 확인**

Run: `cd apps/web && pnpm vitest run src/components/InsightCard.test.tsx`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/components/InsightCard.tsx apps/web/src/components/InsightCard.test.tsx
git commit -m "feat(web): InsightCard on TanStack Query (useInsight + useGenerateInsight)"
```

---

### Task 10: `/dashboard` 리팩토링 (개별 useQuery + 월 파생값 + isLoading)

**Files:**
- Modify: `apps/web/src/routes/dashboard.tsx`
- Test: `apps/web/src/routes/dashboard.test.tsx`

- [ ] **Step 1: 실패 테스트 작성** — `apps/web/src/routes/dashboard.test.tsx`

```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { renderWithClient } from "../test/renderWithClient";

const { fetchMonthsMock } = vi.hoisted(() => ({ fetchMonthsMock: vi.fn() }));
vi.mock("../lib/api", () => ({
  fetchMonths: fetchMonthsMock,
  fetchTransactions: vi.fn(), fetchSummary: vi.fn(), fetchByCategory: vi.fn(),
  fetchCashflowByMonth: vi.fn(), fetchByEssential: vi.fn(), fetchTopMerchants: vi.fn(),
  fetchInsight: vi.fn(), generateInsight: vi.fn(),
  patchCategory: vi.fn(), patchEssential: vi.fn(), api: { post: vi.fn() },
}));

import { DashboardPage } from "./dashboard";

describe("DashboardPage", () => {
  beforeEach(() => fetchMonthsMock.mockReset());

  it("renders empty state (not an infinite spinner) when there are no months", async () => {
    fetchMonthsMock.mockResolvedValueOnce([]);
    renderWithClient(<DashboardPage />);
    await waitFor(() =>
      expect(screen.getByText(/아직 거래가 없습니다/)).toBeInTheDocument());
    // isLoading 교정 회귀 방지: 무한 "로딩…"이 남아있지 않음
    expect(screen.queryByText("로딩…")).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: 실패 확인**

Run: `cd apps/web && pnpm vitest run src/routes/dashboard.test.tsx`
Expected: FAIL — 현재 `dashboard.tsx`는 lib/api 직접 호출 구조라 mock 형태/렌더 차이로 실패(또는 무한 로딩).

- [ ] **Step 3: `dashboard.tsx` 전체 교체**

```tsx
import { useState } from "react";
import { Card, DonutChart, Title } from "@tremor/react";
import { InsightCard } from "../components/InsightCard";
import { MetricStrip } from "../components/MetricStrip";
import { CashflowChart } from "../components/CashflowChart";
import { EssentialDonut } from "../components/EssentialDonut";
import {
  useMonths, useSummary, useByCategory, useCashflow, useTopMerchants, useByEssential,
} from "../lib/queries";

export function DashboardPage() {
  const monthsQuery = useMonths();
  const months = monthsQuery.data ?? [];
  // 사용자가 고르기 전엔 null → 항상 최신 months[0]을 따른다(파생값). useEffect 동기화 금지.
  const [selectedMonth, setSelectedMonth] = useState<string | null>(null);
  const month = selectedMonth ?? months[0];

  const summaryQ = useSummary(month);
  const byCategoryQ = useByCategory(month);
  const cashflowQ = useCashflow(6);
  const topMerchantsQ = useTopMerchants(month, 5);
  const byEssentialQ = useByEssential(month);

  if (!monthsQuery.isLoading && months.length === 0) {
    return (
      <div className="p-8 text-zinc-400">
        아직 거래가 없습니다. /app에서 명세서를 업로드하세요.
      </div>
    );
  }

  // 비활성 쿼리(enabled:false)는 v5에서 isPending이 계속 true → isLoading으로 판정해야 무한 스피너 방지.
  const isLoading =
    monthsQuery.isLoading || summaryQ.isLoading || byCategoryQ.isLoading ||
    cashflowQ.isLoading || topMerchantsQ.isLoading || byEssentialQ.isLoading;
  const isError =
    monthsQuery.isError || summaryQ.isError || byCategoryQ.isError ||
    cashflowQ.isError || topMerchantsQ.isError || byEssentialQ.isError;

  const summary = summaryQ.data ?? null;
  const byCategory = byCategoryQ.data ?? [];
  const cashflow = cashflowQ.data ?? [];
  const topMerchants = topMerchantsQ.data ?? [];
  const byEssential = byEssentialQ.data ?? [];

  return (
    <div className="p-6 space-y-4">
      {isError && (
        <div role="alert" className="bg-red-900/30 border border-red-700 text-red-200 text-sm rounded p-3">
          대시보드 데이터를 불러오는 중 오류가 발생했습니다.
        </div>
      )}
      <div className="flex items-center gap-3">
        <select value={month ?? ""} onChange={(e) => setSelectedMonth(e.target.value)}
          className="bg-zinc-900 border border-zinc-700 rounded px-2 py-1 text-sm" aria-label="월 선택">
          {months.map((m) => (<option key={m} value={m}>{m}</option>))}
        </select>
      </div>

      {isLoading ? (
        <p className="text-zinc-400 text-sm">로딩…</p>
      ) : (
        <div className="space-y-4">
          {month && <InsightCard month={month} />}
          {summary && <MetricStrip summary={summary} />}
          <CashflowChart data={cashflow} />
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Card>
              <Title>카테고리별 지출</Title>
              <DonutChart
                data={byCategory.map((c) => ({ name: c.category, value: Number(c.amount) }))}
                category="value" index="name"
                valueFormatter={(v) => `₩${v.toLocaleString()}`}
                colors={["cyan","amber","rose","lime","violet","orange","blue","fuchsia","emerald","indigo","yellow","pink","teal","sky","purple","green","red","slate","gray"]}
              />
            </Card>
            <EssentialDonut data={byEssential} />
          </div>
          <Card>
            <Title>Top 5 가맹점</Title>
            <ul className="text-sm text-zinc-300 space-y-1 mt-2">
              {topMerchants.length === 0 ? (
                <li className="text-zinc-500">데이터 없음</li>
              ) : (
                topMerchants.map((t, i) => (
                  <li key={t.merchant_raw} className="flex justify-between">
                    <span>{i + 1}. {t.merchant_raw}</span>
                    <span>₩{Number(t.amount).toLocaleString()} ({t.count}건)</span>
                  </li>
                ))
              )}
            </ul>
          </Card>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: 통과 확인**

Run: `cd apps/web && pnpm vitest run src/routes/dashboard.test.tsx`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/routes/dashboard.tsx apps/web/src/routes/dashboard.test.tsx
git commit -m "feat(web): /dashboard on TanStack Query (parallel queries + derived month + isLoading)"
```

---

## Phase 4 — 회귀 검증

### Task 11: 전체 회귀 (타입 + 테스트 + 빌드)

**Files:** 없음 (검증 전용)

- [ ] **Step 1: 타입 체크**

Run: `cd apps/web && pnpm tsc --noEmit`
Expected: 0 errors.

- [ ] **Step 2: 전체 테스트**

Run: `cd apps/web && pnpm vitest run`
Expected: 기존 26 + 신규(useDebouncedValue 2, queries.read 3, queries.category 2, queries.essential 1, queries.upload 1, queries.insight 1, app 1, dashboard 1 = 12) → 약 38 passed. InsightCard 테스트는 갱신되어 동일 3건 유지.

- [ ] **Step 3: 프로덕션 빌드**

Run: `cd apps/web && pnpm build`
Expected: `tsc -b && vite build` 성공, 번들 산출.

- [ ] **Step 4: 수동 점검 (선택, 백엔드 가동 시)**

`pnpm dev`로 띄워 `/app`에서 검색 타이핑 시 요청이 디바운스되는지(네트워크 탭), 카테고리/essential 토글이 즉시 반영 후 정합되는지, `/dashboard` 월 전환 시 차트가 사라지지 않는지(keepPreviousData) 확인.

- [ ] **Step 5: 최종 정리 커밋 (변경 있으면)**

```bash
git add -A
git commit -m "chore(web): W5 TanStack Query migration regression pass"
```

---

## 완료 후

- 브랜치 `feat/w5-tanstack-query-migration` → PR. W4가 origin 미푸시(ahead)인 상태이므로, W4 푸시/배포 순서는 사용자 확인 후 결정.
- 배포 노트(`docs/releases/w5.md`)는 별도 작성(선행 W4 노트 형식 참고).
- 메모리 `progress.md`에 W5 진행/완료 반영.
