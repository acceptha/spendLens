import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MetricStrip } from "./MetricStrip";

const summary = {
  month: "2026-05", total_amount: "30000", transaction_count: 2,
  prev_month: "2026-04", prev_month_total: "20000", prev_month_diff_pct: 50,
  income_total: "100000", net_savings: "70000", savings_rate: 70,
};

describe("MetricStrip", () => {
  it("renders four metrics with savings rate", () => {
    render(<MetricStrip summary={summary as any} />);
    expect(screen.getByText(/지출 총액/)).toBeInTheDocument();
    expect(screen.getByText(/수입 총액/)).toBeInTheDocument();
    expect(screen.getByText(/순저축/)).toBeInTheDocument();
    expect(screen.getByText("70.0%")).toBeInTheDocument();
  });
  it("shows dash when savings_rate is null", () => {
    render(<MetricStrip summary={{ ...summary, savings_rate: null } as any} />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });
});
