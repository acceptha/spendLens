import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { renderWithClient } from "../test/renderWithClient";

const { fetchMonthsMock } = vi.hoisted(() => ({ fetchMonthsMock: vi.fn() }));
vi.mock("../lib/api", () => ({
  fetchMonths: fetchMonthsMock,
  fetchTransactions: vi.fn(),
  fetchSummary: vi.fn().mockResolvedValue(null),
  fetchByCategory: vi.fn().mockResolvedValue([]),
  fetchCashflowByMonth: vi.fn().mockResolvedValue([]),
  fetchByEssential: vi.fn().mockResolvedValue([]),
  fetchTopMerchants: vi.fn().mockResolvedValue([]),
  fetchInsight: vi.fn(), generateInsight: vi.fn(),
  patchCategory: vi.fn(), patchEssential: vi.fn(), api: { post: vi.fn() },
}));

import { DashboardPage } from "./dashboard";

describe("DashboardPage", () => {
  beforeEach(() => fetchMonthsMock.mockReset());

  it("renders empty state (not an infinite spinner) when there are no months", async () => {
    fetchMonthsMock.mockResolvedValueOnce([]);
    renderWithClient(<MemoryRouter><DashboardPage /></MemoryRouter>);
    await waitFor(() =>
      expect(screen.getByText(/아직 거래가 없습니다/)).toBeInTheDocument());
    expect(screen.queryByText("로딩…")).not.toBeInTheDocument();
  });
});
