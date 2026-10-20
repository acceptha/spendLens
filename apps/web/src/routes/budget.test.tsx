import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { renderWithClient } from "../test/renderWithClient";
import type { BudgetStatus } from "../lib/api";

const { fetchMonthsMock, fetchBudgetStatusMock, putBudgetMock } = vi.hoisted(() => ({
  fetchMonthsMock: vi.fn(), fetchBudgetStatusMock: vi.fn(), putBudgetMock: vi.fn(),
}));
vi.mock("../lib/api", () => ({
  fetchMonths: fetchMonthsMock,
  fetchBudgetStatus: fetchBudgetStatusMock,
  putBudget: putBudgetMock,
  api: { post: vi.fn() },
}));
vi.mock("../lib/month", () => ({ currentMonthKST: () => "2026-10" }));

import { BudgetPage } from "./budget";

const status = (o: Partial<BudgetStatus>): BudgetStatus => ({
  month: "2026-10", is_current: true, days_elapsed: 20, days_in_month: 31, items: [], ...o,
});
const coffee = {
  category: "coffee", budget: "50000", spent: "62000", ratio: 1.24,
  projected: "96100", level: "over" as const,
};

function setup(path = "/budget") {
  return renderWithClient(<MemoryRouter initialEntries={[path]}><BudgetPage /></MemoryRouter>);
}

describe("BudgetPage", () => {
  beforeEach(() => {
    fetchMonthsMock.mockReset().mockResolvedValue(["2026-09"]);
    fetchBudgetStatusMock.mockReset();
    putBudgetMock.mockReset().mockResolvedValue(undefined);
  });

  it("empty current month asks for a total budget first", async () => {
    fetchBudgetStatusMock.mockResolvedValue(status({}));
    setup();
    expect(await screen.findByText(/총 지출 한도부터 정해보세요/)).toBeInTheDocument();
    expect(screen.getByText(/이전 달 기록에도 적용/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("총 지출 예산"), { target: { value: "1500000" } });
    fireEvent.click(screen.getByRole("button", { name: "저장" }));
    await waitFor(() => expect(putBudgetMock).toHaveBeenCalledWith("_total", 1500000));
  });

  it("edits a category budget and clears it with an empty value", async () => {
    fetchBudgetStatusMock.mockResolvedValue(status({ items: [coffee] }));
    setup();
    fireEvent.click(await screen.findByRole("button", { name: "편집: 커피" }));
    const input = screen.getByLabelText("커피 예산");
    fireEvent.change(input, { target: { value: "70000" } });
    fireEvent.click(screen.getByRole("button", { name: "저장" }));
    await waitFor(() => expect(putBudgetMock).toHaveBeenCalledWith("coffee", 70000));

    fireEvent.click(await screen.findByRole("button", { name: "편집: 커피" }));
    fireEvent.change(screen.getByLabelText("커피 예산"), { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: "저장" }));
    await waitFor(() => expect(putBudgetMock).toHaveBeenLastCalledWith("coffee", null));
  });

  it("adds a budget for a category without one", async () => {
    fetchBudgetStatusMock.mockResolvedValue(status({ items: [coffee] }));
    setup();
    await screen.findByText("커피");
    fireEvent.change(screen.getByLabelText("예산 추가 카테고리"), { target: { value: "shopping" } });
    fireEvent.change(screen.getByLabelText("예산 추가 금액"), { target: { value: "300000" } });
    fireEvent.click(screen.getByRole("button", { name: "추가" }));
    await waitFor(() => expect(putBudgetMock).toHaveBeenCalledWith("shopping", 300000));
  });

  it("past month is read-only with a notice", async () => {
    fetchBudgetStatusMock.mockResolvedValue(
      status({ month: "2026-09", is_current: false, days_elapsed: 30, days_in_month: 30,
               items: [{ ...coffee, projected: null }] }));
    setup("/budget?month=2026-09");
    expect(await screen.findByText(/예산 변경은 이번 달부터 적용됩니다/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /편집/ })).toBeNull();
    expect(screen.queryByRole("button", { name: "추가" })).toBeNull();
    expect(fetchBudgetStatusMock).toHaveBeenCalledWith("2026-09");
  });
});
