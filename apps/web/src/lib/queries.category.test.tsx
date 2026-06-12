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

    await waitFor(() => {
      const rows = client.getQueryData<TransactionRow[]>(qk.transactions(FILTERS))!;
      expect(rows[0].effective_category).toBe("groceries");
      expect(rows[0].user_category_override).toBe("groceries");
    });

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

    act(() => res1());
    await waitFor(() => expect(patchCategoryMock).toHaveBeenCalledTimes(2));
    expect(txnInvalidations()).toBe(0);

    act(() => res2());
    await waitFor(() => expect(txnInvalidations()).toBe(1));
  });
});
