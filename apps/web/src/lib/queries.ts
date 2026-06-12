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
  patchCategory,
  type TransactionRow,
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

// --- mutation 훅 ---

const CATEGORY_MUTATION_KEY = ["override-category"] as const;

type TxnSnapshot = [QueryKey, TransactionRow[] | undefined][];

/** transactions 캐시의 모든 엔트리에서 한 row를 patch. 스냅샷을 반환. */
export function patchTxnCaches(
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

export function rollbackTxnCaches(
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
