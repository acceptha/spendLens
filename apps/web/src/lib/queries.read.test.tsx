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
    expect(fetchSummaryMock).not.toHaveBeenCalled();
    expect(result.current.isLoading).toBe(false);
  });
});
