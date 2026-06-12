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
