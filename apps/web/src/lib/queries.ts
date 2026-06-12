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
