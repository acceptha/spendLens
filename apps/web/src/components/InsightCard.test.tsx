import { describe, expect, it, vi, beforeEach } from "vitest";
import { screen, fireEvent, waitFor } from "@testing-library/react";
import { renderWithClient } from "../test/renderWithClient";

const { fetchMock, genMock } = vi.hoisted(() => ({ fetchMock: vi.fn(), genMock: vi.fn() }));
vi.mock("../lib/api", () => ({
  fetchInsight: fetchMock,
  generateInsight: genMock,
  fetchTransactions: vi.fn(), fetchMonths: vi.fn(), fetchSummary: vi.fn(),
  fetchByCategory: vi.fn(), fetchCashflowByMonth: vi.fn(), fetchByEssential: vi.fn(),
  fetchTopMerchants: vi.fn(), patchCategory: vi.fn(), patchEssential: vi.fn(),
  api: { post: vi.fn() },
}));

import { InsightCard } from "./InsightCard";

describe("InsightCard", () => {
  beforeEach(() => { fetchMock.mockReset(); genMock.mockReset(); });

  it("shows generate button when no cached insight", async () => {
    fetchMock.mockResolvedValue(null);
    renderWithClient(<InsightCard month="2026-05" />);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /인사이트 생성/ })).toBeInTheDocument());
  });

  it("renders highlights after generate", async () => {
    fetchMock.mockResolvedValue(null);
    genMock.mockResolvedValueOnce({
      month: "2026-05", summary: "요약입니다",
      highlights: [{ type: "saving_tip", title: "팁", detail: "내용" }],
      generated_at: "2026-06-12T00:00:00Z",
    });
    renderWithClient(<InsightCard month="2026-05" />);
    await waitFor(() => screen.getByRole("button", { name: /인사이트 생성/ }));
    fireEvent.click(screen.getByRole("button", { name: /인사이트 생성/ }));
    await waitFor(() => expect(screen.getByText("요약입니다")).toBeInTheDocument());
    expect(screen.getByText("팁")).toBeInTheDocument();
  });

  it("shows budget error on 503", async () => {
    fetchMock.mockResolvedValue(null);
    genMock.mockRejectedValueOnce({ response: { status: 503 } });
    renderWithClient(<InsightCard month="2026-05" />);
    await waitFor(() => screen.getByRole("button", { name: /인사이트 생성/ }));
    fireEvent.click(screen.getByRole("button", { name: /인사이트 생성/ }));
    await waitFor(() => expect(screen.getByText(/예산/)).toBeInTheDocument());
  });
});
