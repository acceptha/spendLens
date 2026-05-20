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

async function tryRefresh(): Promise<string | null> {
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
        useAuth.getState().setAccess(null);
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
      const newToken = await tryRefresh();
      if (newToken) {
        original.headers.Authorization = `Bearer ${newToken}`;
        return api(original);
      }
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
  essential?: boolean | null;
  essential_reason?: string | null;
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
