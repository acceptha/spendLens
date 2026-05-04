import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { TransactionList, Txn } from "./TransactionList";

describe("TransactionList", () => {
  it("renders empty list without error", () => {
    render(<TransactionList items={[]} />);
    expect(screen.getByTestId("txn-list").children.length).toBe(0);
  });

  it("renders merchant and amount", () => {
    const items: Txn[] = [{
      txn_date: "2026-04-28", txn_time: null, amount: "9500.00",
      merchant_raw: "스타벅스 강남대로점", category: "coffee",
    }];
    render(<TransactionList items={items} />);
    expect(screen.getByText(/스타벅스/)).toBeInTheDocument();
    expect(screen.getByText(/9,500원/)).toBeInTheDocument();
  });

  it("shows Canceled badge", () => {
    const items: Txn[] = [{
      txn_date: "2026-04-24", txn_time: null, amount: "24000",
      merchant_raw: "교보문고", category: "entertainment", is_canceled: true,
    }];
    render(<TransactionList items={items} />);
    expect(screen.getByText("[Canceled]")).toBeInTheDocument();
  });
});
