import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
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
    expect(screen.getByText(/\[커피\]/)).toBeInTheDocument();  // no onCategoryChange → 텍스트 칩
  });

  it("shows canceled badge in Korean", () => {
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
    expect(screen.getByText("[취소]")).toBeInTheDocument();
  });

  it("deletes only after the user confirms", () => {
    const onDelete = vi.fn();
    const confirm = vi.spyOn(window, "confirm");
    render(<TransactionList items={[makeTxn({})]} onDelete={onDelete} />);
    const btn = screen.getByRole("button", { name: /삭제: 스타벅스/ });

    confirm.mockReturnValueOnce(false);
    fireEvent.click(btn);
    expect(onDelete).not.toHaveBeenCalled();

    confirm.mockReturnValueOnce(true);
    fireEvent.click(btn);
    expect(onDelete).toHaveBeenCalledWith("t1");
    confirm.mockRestore();
  });

  it("hides the delete button when onDelete is not given (guest)", () => {
    render(<TransactionList items={[makeTxn({})]} />);
    expect(screen.queryByRole("button", { name: /삭제/ })).toBeNull();
  });

  it("marks manually entered transactions", () => {
    render(<TransactionList items={[makeTxn({ source_type: "manual" }), makeTxn({ id: "t2" })]} />);
    expect(screen.getAllByText("직접 입력")).toHaveLength(1);
  });
});
