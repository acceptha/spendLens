import axios, { AxiosError } from "axios";
import { useAuth } from "../stores/auth";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

export const api = axios.create({
  baseURL: API_BASE,
  withCredentials: true,
});

api.interceptors.request.use((config) => {
  const token = useAuth.getState().accessToken;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

let refreshing: Promise<string | null> | null = null;

/** Refresh the access token using the httpOnly refresh cookie. Deduped across
 *  concurrent callers. Used both by the 401 retry interceptor and the on-boot
 *  rehydration in App. Resolves to the new token, or null if there's no valid session. */
export async function refreshAccessToken(): Promise<string | null> {
  if (!refreshing) {
    refreshing = (async () => {
      try {
        const resp = await axios.post(
          `${API_BASE}/auth/refresh`,
          {},
          { withCredentials: true },
        );
        const newToken = resp.data.access_token as string;
        useAuth.getState().setAccess(newToken);
        return newToken;
      } catch {
        // 토큰을 여기서 null로 만들지 않는다. 부팅 시 익명 refresh가 실패해도
        // (그 사이) 로그인이 세팅한 토큰을 덮어쓰는 레이스를 피하기 위함.
        // 만료 세션 로그아웃은 401 인터셉터가 책임진다(아래).
        return null;
      } finally {
        refreshing = null;
      }
    })();
  }
  return refreshing;
}

api.interceptors.response.use(
  (r) => r,
  async (err: AxiosError) => {
    const original = err.config as any;
    if (err.response?.status === 401 && !original?._retried) {
      original._retried = true;
      const newToken = await refreshAccessToken();
      if (newToken) {
        original.headers.Authorization = `Bearer ${newToken}`;
        return api(original);
      }
      // refresh 실패 = 세션 만료 → 로그아웃 (여기서만 토큰을 비운다)
      useAuth.getState().setAccess(null);
    }
    return Promise.reject(err);
  },
);

export type TransactionRow = {
  id: string;
  txn_date: string;
  txn_time: string | null;
  amount: string;
  merchant_raw: string;
  category: string;
  auto_category: string;
  user_category_override: string | null;
  effective_category: string;
  card_last4?: string | null;
  is_canceled?: boolean;
  essential_override?: boolean | null;
  effective_essential?: boolean;
};

export async function fetchTransactions(params: {
  month?: string;
  category?: string[];
  search?: string;
  limit?: number;
  offset?: number;
}): Promise<TransactionRow[]> {
  const q = new URLSearchParams();
  if (params.month) q.set("month", params.month);
  if (params.category && params.category.length)
    q.set("category", params.category.join(","));
  if (params.search) q.set("search", params.search);
  q.set("limit", String(params.limit ?? 50));
  q.set("offset", String(params.offset ?? 0));
  const { data } = await api.get<TransactionRow[]>(`/transactions?${q}`);
  return data;
}

export async function fetchMonths(): Promise<string[]> {
  const { data } = await api.get<string[]>("/transactions/months");
  return data;
}

export async function patchCategory(id: string, category: string): Promise<void> {
  await api.patch(`/transactions/${id}`, { category });
}

export type SummaryResponse = {
  month: string;
  total_amount: string;
  transaction_count: number;
  prev_month: string;
  prev_month_total: string;
  prev_month_diff_pct: number | null;
  income_total: string;
  net_savings: string;
  savings_rate: number | null;
};
export type CategoryBucket = { category: string; amount: string; count: number };
export type CashflowBucket = { month: string; expense: string; income: string };
export type MerchantBucket = { merchant_raw: string; amount: string; count: number };
export type EssentialBucket = { essential: boolean; amount: string; count: number };

export type InsightHighlight = {
  type: "top_growth" | "anomaly" | "saving_tip";
  title: string;
  detail: string;
};
export type InsightResponse = {
  month: string;
  summary: string;
  highlights: InsightHighlight[];
  generated_at: string;
};

export async function fetchSummary(month: string): Promise<SummaryResponse> {
  const { data } = await api.get<SummaryResponse>(`/dashboard/summary?month=${month}`);
  return data;
}
export async function fetchByCategory(month: string): Promise<CategoryBucket[]> {
  const { data } = await api.get<CategoryBucket[]>(`/dashboard/by-category?month=${month}`);
  return data;
}
export async function fetchCashflowByMonth(lastN: number = 6): Promise<CashflowBucket[]> {
  const { data } = await api.get<CashflowBucket[]>(`/dashboard/cashflow-by-month?last_n=${lastN}`);
  return data;
}
export async function fetchByEssential(month: string): Promise<EssentialBucket[]> {
  const { data } = await api.get<EssentialBucket[]>(`/dashboard/by-essential?month=${month}`);
  return data;
}
export async function fetchInsight(month: string): Promise<InsightResponse | null> {
  const { data } = await api.get<InsightResponse | null>(`/insights?month=${month}`);
  return data;
}
export async function generateInsight(month: string, force = false): Promise<InsightResponse> {
  const { data } = await api.post<InsightResponse>(`/insights/generate?force=${force}`, { month });
  return data;
}
export async function patchEssential(id: string, essentialOverride: boolean | null): Promise<void> {
  await api.patch(`/transactions/${id}/essential`, { essential_override: essentialOverride });
}
export async function fetchTopMerchants(month: string, limit: number = 5): Promise<MerchantBucket[]> {
  const { data } = await api.get<MerchantBucket[]>(`/dashboard/top-merchants?month=${month}&limit=${limit}`);
  return data;
}
