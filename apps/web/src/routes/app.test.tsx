import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { renderWithClient } from "../test/renderWithClient";
import { useAuth } from "../stores/auth";
import { CATEGORIES } from "../components/CategoryChip";
import { categoryLabel } from "../lib/categories";

const FIRST_CATEGORY = CATEGORIES[0]; // "coffee"
const FIRST_CATEGORY_LABEL = categoryLabel(FIRST_CATEGORY); // "커피"

const { fetchTransactionsMock, patchCategoryMock, applyMock } = vi.hoisted(() => ({
  fetchTransactionsMock: vi.fn(), patchCategoryMock: vi.fn(), applyMock: vi.fn(),
}));
vi.mock("../lib/api", () => ({
  fetchTransactions: fetchTransactionsMock,
  fetchMonths: vi.fn(() => Promise.resolve([])),
  fetchSummary: vi.fn(), fetchByCategory: vi.fn(),
  fetchCashflowByMonth: vi.fn(), fetchByEssential: vi.fn(), fetchTopMerchants: vi.fn(),
  fetchInsight: vi.fn(), generateInsight: vi.fn(),
  patchCategory: patchCategoryMock, patchEssential: vi.fn(),
  applyCategoryToMerchant: applyMock, createTransaction: vi.fn(), api: { post: vi.fn() },
}));

import { AppPage } from "./app";

describe("AppPage", () => {
  beforeEach(() => {
    fetchTransactionsMock.mockReset().mockResolvedValue([]);
    patchCategoryMock.mockReset();
    applyMock.mockReset();
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
    fireEvent.click(screen.getByLabelText(FIRST_CATEGORY_LABEL));

    // immediate (no 300ms wait) — a new fetch with the category should fire quickly
    await waitFor(
      () => expect(fetchTransactionsMock.mock.calls.length).toBeGreaterThan(callsBefore),
      { timeout: 200 },
    );
    const lastFilters = fetchTransactionsMock.mock.calls.at(-1)![0];
    expect(lastFilters.category).toContain(FIRST_CATEGORY);
  });

  it("shows an error banner when transactions fail to load", async () => {
    fetchTransactionsMock.mockReset().mockRejectedValue(new Error("boom"));
    renderWithClient(<MemoryRouter><AppPage /></MemoryRouter>);
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(/오류가 발생/));
  });

  it("prefills the category filter from the ?category= query param", async () => {
    renderWithClient(
      <MemoryRouter initialEntries={["/app?category=coffee"]}>
        <AppPage />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(fetchTransactionsMock).toHaveBeenCalledWith(
        expect.objectContaining({ category: ["coffee"] }),
      ),
    );
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
    fireEvent.click(screen.getByLabelText(FIRST_CATEGORY_LABEL));

    // while the new fetch is pending, the OLD row must still be in the DOM (keepPreviousData)
    await waitFor(() => expect(fetchTransactionsMock.mock.calls.length).toBeGreaterThan(1));
    expect(screen.getByText(/OLD_MERCHANT/)).toBeInTheDocument();

    // resolve the second fetch to avoid an unhandled pending promise
    resolveSecond([]);
  });

  describe("same-merchant bulk apply", () => {
    const row = {
      id: "t1", txn_date: "2026-10-01", txn_time: null, amount: "4500",
      merchant_raw: "스타벅스 강남점", category: "unknown", auto_category: "unknown",
      user_category_override: null, effective_category: "unknown",
    };

    async function changeToCoffee() {
      fetchTransactionsMock.mockResolvedValue([row]);
      renderWithClient(<MemoryRouter><AppPage /></MemoryRouter>);
      fireEvent.click(await screen.findByRole("button", { name: /카테고리: 미분류/ }));
      fireEvent.click(screen.getByRole("button", { name: /^\s*커피$/ }));
    }

    it("sends one PATCH and offers to apply to the same merchant", async () => {
      patchCategoryMock.mockResolvedValue({ same_merchant_pending: 3, merchant: "스타벅스" });
      applyMock.mockResolvedValue({ updated: 3 });
      await changeToCoffee();

      expect(await screen.findByText("같은 가맹점 '스타벅스' 거래 3건도 '커피'로 바꿀까요?"))
        .toBeInTheDocument();
      expect(patchCategoryMock).toHaveBeenCalledTimes(1);
      expect(patchCategoryMock).toHaveBeenCalledWith("t1", "coffee");

      fireEvent.click(screen.getByRole("button", { name: "모두 변경" }));
      await waitFor(() => expect(applyMock).toHaveBeenCalledWith("t1"));
      expect(await screen.findByText("3건 변경됨")).toBeInTheDocument();
    });

    it("dismiss closes the offer without applying", async () => {
      patchCategoryMock.mockResolvedValue({ same_merchant_pending: 2, merchant: "스타벅스" });
      await changeToCoffee();
      fireEvent.click(await screen.findByRole("button", { name: "닫기" }));
      expect(screen.queryByText(/같은 가맹점/)).toBeNull();
      expect(applyMock).not.toHaveBeenCalled();
    });

    it("no offer when there is nothing else to change", async () => {
      patchCategoryMock.mockResolvedValue({ same_merchant_pending: 0, merchant: "스타벅스" });
      await changeToCoffee();
      await waitFor(() => expect(patchCategoryMock).toHaveBeenCalled());
      expect(screen.queryByText(/같은 가맹점/)).toBeNull();
    });
  });
});
