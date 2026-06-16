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
