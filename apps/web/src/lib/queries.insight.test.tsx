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
