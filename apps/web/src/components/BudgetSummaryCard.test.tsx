import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { renderWithClient } from "../test/renderWithClient";

const { fetchBudgetStatusMock } = vi.hoisted(() => ({ fetchBudgetStatusMock: vi.fn() }));
vi.mock("../lib/api", () => ({ fetchBudgetStatus: fetchBudgetStatusMock, api: {} }));

import { BudgetSummaryCard } from "./BudgetSummaryCard";

const base = { month: "2026-10", is_current: true, days_elapsed: 20, days_in_month: 31 };
const item = (
  category: string, level: "ok" | "warn" | "over", ratio: number, projected: string | null = null,
) => ({ category, budget: "100000", spent: String(Math.round(ratio * 100000)), ratio, projected, level });

function setup() {
  return renderWithClient(<MemoryRouter><BudgetSummaryCard month="2026-10" /></MemoryRouter>);
}

describe("BudgetSummaryCard", () => {
  beforeEach(() => fetchBudgetStatusMock.mockReset());

  it("links to budget setup when there are no budgets", async () => {
    fetchBudgetStatusMock.mockResolvedValue({ ...base, items: [] });
    setup();
    const link = await screen.findByRole("link", { name: /예산 설정하기/ });
    expect(link).toHaveAttribute("href", "/budget?month=2026-10");
  });

  it("shows total bar and up to 3 alerts (over/warn only)", async () => {
    fetchBudgetStatusMock.mockResolvedValue({ ...base, items: [
      item("_total", "ok", 0.5),
      item("coffee", "over", 1.24),
      item("shopping", "warn", 0.3, "130000"),
      item("lunch", "warn", 0.85),
      item("dinner", "warn", 0.82),
      item("health", "ok", 0.1),
    ]});
    setup();
    expect(await screen.findByText("총 지출")).toBeInTheDocument();
    expect(screen.getByText("커피 124% 초과")).toBeInTheDocument();
    expect(screen.getByText("쇼핑 월말 예상 초과")).toBeInTheDocument();
    expect(screen.getByText("점심 85% 사용")).toBeInTheDocument();
    expect(screen.queryByText(/저녁/)).toBeNull();   // 최대 3개
    expect(screen.queryByText(/의료/)).toBeNull();   // ok는 표시 안 함
  });
});
