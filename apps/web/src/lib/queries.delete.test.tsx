import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import { QueryClientProvider } from "@tanstack/react-query";
import { makeTestClient } from "../test/renderWithClient";
import type { ReactNode } from "react";
import type { TransactionRow } from "./api";

const { deleteMock } = vi.hoisted(() => ({ deleteMock: vi.fn() }));
vi.mock("./api", () => ({
  fetchTransactions: vi.fn(), fetchMonths: vi.fn(), fetchSummary: vi.fn(),
  fetchByCategory: vi.fn(), fetchCashflowByMonth: vi.fn(), fetchByEssential: vi.fn(),
  fetchTopMerchants: vi.fn(), fetchInsight: vi.fn(), generateInsight: vi.fn(),
  patchCategory: vi.fn(), patchEssential: vi.fn(), deleteTransaction: deleteMock,
  api: { post: vi.fn() },
}));

import { useDeleteTransaction, qk, type TxnFilters } from "./queries";

const FILTERS: TxnFilters = { limit: 200 };
function row(id: string): TransactionRow {
  return {
    id, txn_date: "2026-05-01", txn_time: null, amount: "1000", merchant_raw: "M",
    category: "etc", auto_category: "etc", user_category_override: null, effective_category: "etc",
  };
}
function ctx() {
  const client = makeTestClient();
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  return { client, wrapper };
}

describe("useDeleteTransaction", () => {
  beforeEach(() => deleteMock.mockReset());

  it("removes the row optimistically and restores it on error", async () => {
    const { client, wrapper } = ctx();
    client.setQueryData(qk.transactions(FILTERS), [row("t1"), row("t2")]);

    let reject!: (e: unknown) => void;
    deleteMock.mockReturnValueOnce(new Promise((_res, rej) => { reject = rej; }));

    const { result } = renderHook(() => useDeleteTransaction(), { wrapper });
    act(() => result.current.mutate("t1"));

    await waitFor(() => {
      const rows = client.getQueryData<TransactionRow[]>(qk.transactions(FILTERS))!;
      expect(rows.map((r) => r.id)).toEqual(["t2"]);
    });

    act(() => reject({ message: "boom" }));
    await waitFor(() => {
      const rows = client.getQueryData<TransactionRow[]>(qk.transactions(FILTERS))!;
      expect(rows.map((r) => r.id)).toEqual(["t1", "t2"]);
    });
  });

  it("invalidates months, dashboard and insight after success", async () => {
    const { client, wrapper } = ctx();
    const spy = vi.spyOn(client, "invalidateQueries");
    deleteMock.mockResolvedValueOnce(undefined);

    const { result } = renderHook(() => useDeleteTransaction(), { wrapper });
    await act(() => result.current.mutateAsync("t1"));

    const keys = spy.mock.calls.map((c) => JSON.stringify(c[0]?.queryKey));
    expect(keys).toEqual(expect.arrayContaining([
      '["transactions"]', '["months"]', '["dashboard"]', '["insight"]', '["budget"]',
    ]));
  });
});
