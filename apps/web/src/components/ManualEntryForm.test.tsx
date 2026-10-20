import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, fireEvent, waitFor } from "@testing-library/react";
import { renderWithClient } from "../test/renderWithClient";

const { createMock } = vi.hoisted(() => ({ createMock: vi.fn() }));
vi.mock("../lib/api", () => ({ createTransaction: createMock, api: {} }));
vi.mock("../lib/month", () => ({ todayKST: () => "2026-10-20", currentMonthKST: () => "2026-10" }));

import { ManualEntryForm } from "./ManualEntryForm";

function open() {
  renderWithClient(<ManualEntryForm />);
  fireEvent.click(screen.getByRole("button", { name: "+ 직접 입력" }));
}

describe("ManualEntryForm", () => {
  beforeEach(() => createMock.mockReset().mockResolvedValue({ id: "n1" }));

  it("submits an expense with today's date and auto category by default", async () => {
    open();
    fireEvent.change(screen.getByLabelText("금액"), { target: { value: "4,500" } });
    fireEvent.change(screen.getByLabelText("내용"), { target: { value: "동네 분식" } });
    fireEvent.click(screen.getByRole("button", { name: "추가" }));
    await waitFor(() => expect(createMock).toHaveBeenCalledWith({
      kind: "expense", txn_date: "2026-10-20", amount: 4500, merchant: "동네 분식", category: null,
    }));
    expect(await screen.findByText("추가됨")).toBeInTheDocument();
    expect(screen.getByLabelText("금액")).toHaveValue("");
    expect(screen.getByLabelText("내용")).toHaveValue("");
  });

  it("submits income with a chosen category", async () => {
    open();
    fireEvent.click(screen.getByLabelText("수입"));
    fireEvent.change(screen.getByLabelText("날짜"), { target: { value: "2026-10-01" } });
    fireEvent.change(screen.getByLabelText("금액"), { target: { value: "50000" } });
    fireEvent.change(screen.getByLabelText("내용"), { target: { value: "용돈" } });
    fireEvent.change(screen.getByLabelText("카테고리"), { target: { value: "etc" } });
    fireEvent.click(screen.getByRole("button", { name: "추가" }));
    await waitFor(() => expect(createMock).toHaveBeenCalledWith({
      kind: "income", txn_date: "2026-10-01", amount: 50000, merchant: "용돈", category: "etc",
    }));
  });

  it("blocks submit until amount and description are filled", () => {
    open();
    expect(screen.getByRole("button", { name: "추가" })).toBeDisabled();
    fireEvent.change(screen.getByLabelText("금액"), { target: { value: "1000" } });
    expect(screen.getByRole("button", { name: "추가" })).toBeDisabled();
    fireEvent.change(screen.getByLabelText("내용"), { target: { value: "  " } });
    expect(screen.getByRole("button", { name: "추가" })).toBeDisabled();
  });

  it("shows an error when saving fails", async () => {
    createMock.mockRejectedValueOnce({ response: { status: 400, data: { detail: "FUTURE_DATE" } } });
    open();
    fireEvent.change(screen.getByLabelText("금액"), { target: { value: "1000" } });
    fireEvent.change(screen.getByLabelText("내용"), { target: { value: "x" } });
    fireEvent.click(screen.getByRole("button", { name: "추가" }));
    expect(await screen.findByText("미래 날짜는 입력할 수 없습니다.")).toBeInTheDocument();
  });
});
