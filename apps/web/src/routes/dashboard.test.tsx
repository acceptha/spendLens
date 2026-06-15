import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { renderWithClient } from "../test/renderWithClient";

const { fetchMonthsMock } = vi.hoisted(() => ({ fetchMonthsMock: vi.fn() }));
vi.mock("../lib/api", () => ({
  fetchMonths: fetchMonthsMock,
  fetchTransactions: vi.fn(), fetchSummary: vi.fn(), fetchByCategory: vi.fn(),
  fetchCashflowByMonth: vi.fn(), fetchByEssential: vi.fn(), fetchTopMerchants: vi.fn(),
  fetchInsight: vi.fn(), generateInsight: vi.fn(),
  patchCategory: vi.fn(), patchEssential: vi.fn(), api: { post: vi.fn() },
}));

import { DashboardPage } from "./dashboard";

describe("DashboardPage", () => {
  beforeEach(() => fetchMonthsMock.mockReset());

  it("renders empty state (not an infinite spinner) when there are no months", async () => {
    fetchMonthsMock.mockResolvedValueOnce([]);
    renderWithClient(<DashboardPage />);
    await waitFor(() =>
      expect(screen.getByText(/아직 거래가 없습니다/)).toBeInTheDocument());
    expect(screen.queryByText("로딩…")).not.toBeInTheDocument();
  });
});
