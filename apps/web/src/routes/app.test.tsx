import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { renderWithClient } from "../test/renderWithClient";
import { useAuth } from "../stores/auth";

const { fetchTransactionsMock } = vi.hoisted(() => ({ fetchTransactionsMock: vi.fn() }));
vi.mock("../lib/api", () => ({
  fetchTransactions: fetchTransactionsMock,
  fetchMonths: vi.fn(() => Promise.resolve([])),
  fetchSummary: vi.fn(), fetchByCategory: vi.fn(),
  fetchCashflowByMonth: vi.fn(), fetchByEssential: vi.fn(), fetchTopMerchants: vi.fn(),
  fetchInsight: vi.fn(), generateInsight: vi.fn(),
  patchCategory: vi.fn(), patchEssential: vi.fn(), api: { post: vi.fn() },
}));

import { AppPage } from "./app";

describe("AppPage", () => {
  beforeEach(() => {
    fetchTransactionsMock.mockReset().mockResolvedValue([]);
    useAuth.getState().setAccess("test-token"); // 인증 상태 → /login 리다이렉트 방지
  });

  it("debounces search: only the final value triggers a fetch", async () => {
    renderWithClient(<MemoryRouter><AppPage /></MemoryRouter>);
    await waitFor(() => expect(fetchTransactionsMock).toHaveBeenCalled());

    const box = screen.getByPlaceholderText(/가맹점/);
    fireEvent.change(box, { target: { value: "c" } });
    fireEvent.change(box, { target: { value: "co" } });
    fireEvent.change(box, { target: { value: "cof" } });

    await waitFor(
      () => expect(fetchTransactionsMock).toHaveBeenCalledWith(
        expect.objectContaining({ search: "cof" }),
      ),
      { timeout: 1500 },
    );
    const calledSearches = fetchTransactionsMock.mock.calls.map(([f]) => f.search);
    expect(calledSearches).not.toContain("c");
    expect(calledSearches).not.toContain("co");
  });
});
