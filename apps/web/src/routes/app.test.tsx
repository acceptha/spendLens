import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { renderWithClient } from "../test/renderWithClient";
import { useAuth } from "../stores/auth";
import { CATEGORIES } from "../components/CategoryChip";

const FIRST_CATEGORY = CATEGORIES[0]; // "coffee"

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

  it("refetches immediately when a category filter changes (not debounced)", async () => {
    renderWithClient(<MemoryRouter><AppPage /></MemoryRouter>);
    await waitFor(() => expect(fetchTransactionsMock).toHaveBeenCalled());
    const callsBefore = fetchTransactionsMock.mock.calls.length;

    // open the category dropdown and toggle one category
    fireEvent.click(screen.getByText(/카테고리 \(/));
    fireEvent.click(screen.getByLabelText(FIRST_CATEGORY));

    // immediate (no 300ms wait) — a new fetch with the category should fire quickly
    await waitFor(
      () => expect(fetchTransactionsMock.mock.calls.length).toBeGreaterThan(callsBefore),
      { timeout: 200 },
    );
    const lastFilters = fetchTransactionsMock.mock.calls.at(-1)![0];
    expect(lastFilters.category).toContain(FIRST_CATEGORY);
  });

  it("keeps the previous transaction list visible during a filter transition (keepPreviousData)", async () => {
    // first load resolves with one row
    fetchTransactionsMock.mockResolvedValueOnce([
      {
        id: "old-1",
        txn_date: "2026-05-01",
        txn_time: null,
        amount: "1000",
        merchant_raw: "OLD_MERCHANT",
        category: "coffee",
        auto_category: "coffee",
        user_category_override: null,
        effective_category: "coffee",
        card_last4: null,
        is_canceled: false,
        essential_override: null,
        effective_essential: false,
      },
    ]);
    renderWithClient(<MemoryRouter><AppPage /></MemoryRouter>);
    await waitFor(() => expect(screen.getByText(/OLD_MERCHANT/)).toBeInTheDocument());

    // next fetch (triggered by a category change) is held pending
    let resolveSecond!: (rows: unknown[]) => void;
    fetchTransactionsMock.mockReturnValueOnce(new Promise((res) => { resolveSecond = res; }));

    fireEvent.click(screen.getByText(/카테고리 \(/));
    fireEvent.click(screen.getByLabelText(FIRST_CATEGORY));

    // while the new fetch is pending, the OLD row must still be in the DOM (keepPreviousData)
    await waitFor(() => expect(fetchTransactionsMock.mock.calls.length).toBeGreaterThan(1));
    expect(screen.getByText(/OLD_MERCHANT/)).toBeInTheDocument();

    // resolve the second fetch to avoid an unhandled pending promise
    resolveSecond([]);
  });
});
