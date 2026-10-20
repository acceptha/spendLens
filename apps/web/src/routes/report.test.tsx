import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { renderWithClient } from "../test/renderWithClient";
import type { MonthlyReport } from "../lib/api";

const { fetchReportMock } = vi.hoisted(() => ({ fetchReportMock: vi.fn() }));
vi.mock("../lib/api", () => ({ fetchMonthlyReport: fetchReportMock, api: {} }));

import { ReportPage } from "./report";

const full: MonthlyReport = {
  month: "2026-09",
  available_months: ["2026-10", "2026-09", "2026-08"],
  summary: {
    spent: "1282530", income: "3500000", net_savings: "2217470", savings_rate: 63.36,
    transaction_count: 41, prev_month: "2026-08", prev_spent: "1100000", spent_diff_pct: 16.59,
  },
  top_categories: [
    { category: "housing", amount: "800000", share: 0.6238 },
    { category: "coffee", amount: "62000", share: 0.0483 },
  ],
  category_changes: {
    increased: [{ category: "coffee", amount: "62000", prev_amount: "30000", diff: "32000" }],
    decreased: [{ category: "dinner", amount: "0", prev_amount: "45000", diff: "-45000" }],
  },
  budget: {
    total: 5, kept: 3, over: 2,
    items: [{ category: "coffee", budget: "50000", spent: "62000", ratio: 1.24, projected: null, level: "over" }],
  },
  insight: { summary: "이번 달 지출 ₩1,282,530.", highlights: [], generated_at: "2026-10-20T00:00:00Z" },
};

function setup(path = "/report") {
  return renderWithClient(<MemoryRouter initialEntries={[path]}><ReportPage /></MemoryRouter>);
}

describe("ReportPage", () => {
  beforeEach(() => fetchReportMock.mockReset());

  it("renders summary, scorecard, changes, top categories and insight", async () => {
    fetchReportMock.mockResolvedValue(full);
    setup();
    expect(await screen.findByText("2026년 9월 결산")).toBeInTheDocument();
    expect(screen.getByText("₩1,282,530")).toBeInTheDocument();
    expect(screen.getByText("전월 대비 +17%")).toBeInTheDocument();
    expect(screen.getByText("저축률 63%")).toBeInTheDocument();
    expect(screen.getByText("5개 중 3개 지켰어요")).toBeInTheDocument();
    expect(screen.getByText("커피 +₩32,000")).toBeInTheDocument();
    expect(screen.getByText("저녁 -₩45,000")).toBeInTheDocument();
    expect(screen.getByText("주거")).toBeInTheDocument();
    expect(screen.getByText("₩800,000 · 62%")).toBeInTheDocument();
    expect(screen.getByText("이번 달 지출 ₩1,282,530.")).toBeInTheDocument();
    expect(fetchReportMock).toHaveBeenCalledWith(undefined);
  });

  it("shows empty states for missing budget and insight", async () => {
    fetchReportMock.mockResolvedValue({ ...full, budget: null, insight: null });
    setup();
    expect(await screen.findByText(/예산을 정하면 결산에 성적표가 나와요/)).toBeInTheDocument();
    expect(screen.getByText("인사이트를 만들지 못했어요")).toBeInTheDocument();
  });

  it("shows upload hint when there are no transactions", async () => {
    fetchReportMock.mockResolvedValue({
      ...full, month: null, available_months: [], summary: null, top_categories: [],
      category_changes: { increased: [], decreased: [] }, budget: null, insight: null,
    });
    setup();
    expect(await screen.findByText(/아직 거래가 없습니다/)).toBeInTheDocument();
  });

  it("requests the month from the URL", async () => {
    fetchReportMock.mockResolvedValue({ ...full, month: "2026-08" });
    setup("/report?month=2026-08");
    await waitFor(() => expect(fetchReportMock).toHaveBeenCalledWith("2026-08"));
    expect(await screen.findByText("2026년 8월 결산")).toBeInTheDocument();
  });
});
