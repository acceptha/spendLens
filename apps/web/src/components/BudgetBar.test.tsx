import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { BudgetBar } from "./BudgetBar";
import type { BudgetItem } from "../lib/api";

const item = (o: Partial<BudgetItem>): BudgetItem => ({
  category: "coffee", budget: "50000", spent: "20000", ratio: 0.4,
  projected: null, level: "ok", ...o,
});

describe("BudgetBar", () => {
  it("shows label, amounts and percent", () => {
    render(<BudgetBar item={item({})} />);
    expect(screen.getByText("커피")).toBeInTheDocument();
    expect(screen.getByText("₩20,000 / ₩50,000")).toBeInTheDocument();
    expect(screen.getByText("40%")).toBeInTheDocument();
  });

  it("marks warn and over with text, not only color", () => {
    const { rerender } = render(<BudgetBar item={item({ level: "warn", ratio: 0.85 })} />);
    expect(screen.getByText("주의")).toBeInTheDocument();
    rerender(<BudgetBar item={item({ level: "over", ratio: 1.24, spent: "62000" })} />);
    expect(screen.getByText("초과")).toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "124");
  });

  it("shows month-end projection only when present", () => {
    const { rerender } = render(<BudgetBar item={item({ projected: "96100" })} />);
    expect(screen.getByText("이 속도면 월말 ₩96,100 예상")).toBeInTheDocument();
    rerender(<BudgetBar item={item({ projected: null })} />);
    expect(screen.queryByText(/월말/)).toBeNull();
  });

  it("labels the total budget", () => {
    render(<BudgetBar item={item({ category: "_total" })} />);
    expect(screen.getByText("총 지출")).toBeInTheDocument();
  });
});
