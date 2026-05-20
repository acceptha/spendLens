import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { TransactionList, type Txn } from "./TransactionList";

function makeTxn(overrides: Partial<Txn>): Txn {
  return {
    id: "t1",
    txn_date: "2026-04-28",
    txn_time: null,
    amount: "9500.00",
    merchant_raw: "스타벅스 강남대로점",
    category: "coffee",
    auto_category: "coffee",
    user_category_override: null,
    effective_category: "coffee",
    ...overrides,
  };
}

describe("TransactionList", () => {
  it("renders empty list without error", () => {
    render(<TransactionList items={[]} />);
    expect(screen.getByTestId("txn-list").children.length).toBe(0);
  });

  it("renders merchant and amount", () => {
    const items: Txn[] = [makeTxn({})];
    render(<TransactionList items={items} />);
    expect(screen.getByText(/스타벅스/)).toBeInTheDocument();
    expect(screen.getByText(/9,500원/)).toBeInTheDocument();
    expect(screen.getByText(/\[coffee\]/)).toBeInTheDocument();  // no onCategoryChange → 텍스트 칩
  });

  it("shows Canceled badge", () => {
    const items: Txn[] = [
      makeTxn({
        id: "t2",
        txn_date: "2026-04-24",
        amount: "24000",
        merchant_raw: "교보문고",
        category: "entertainment",
        auto_category: "entertainment",
        effective_category: "entertainment",
        is_canceled: true,
      }),
    ];
    render(<TransactionList items={items} />);
    expect(screen.getByText("[Canceled]")).toBeInTheDocument();
  });
});
