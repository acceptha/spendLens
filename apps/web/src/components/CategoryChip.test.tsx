import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

const { patchMock } = vi.hoisted(() => ({ patchMock: vi.fn() }));
vi.mock("../lib/api", () => ({ patchCategory: patchMock }));

import { CategoryChip } from "./CategoryChip";

describe("CategoryChip", () => {
  beforeEach(() => patchMock.mockReset());

  it("displays effective category", () => {
    render(
      <CategoryChip
        transactionId="t1"
        effective="coffee"
        isOverridden={false}
        onChange={() => {}}
      />,
    );
    expect(screen.getByRole("button", { name: /coffee/ })).toBeInTheDocument();
  });

  it("shows override dot when overridden", () => {
    render(
      <CategoryChip
        transactionId="t1"
        effective="groceries"
        isOverridden={true}
        onChange={() => {}}
      />,
    );
    expect(screen.getByRole("button", { name: /groceries/ }).textContent).toContain("•");
  });

  it("opens dropdown on click and calls patch on selection", async () => {
    patchMock.mockResolvedValueOnce(undefined);
    const onChange = vi.fn();
    render(
      <CategoryChip
        transactionId="t1"
        effective="unknown"
        isOverridden={false}
        onChange={onChange}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /unknown/ }));
    const groceriesOption = screen.getByRole("button", { name: /groceries/ });
    fireEvent.click(groceriesOption);

    expect(onChange).toHaveBeenCalledWith("groceries");
    await waitFor(() => expect(patchMock).toHaveBeenCalledWith("t1", "groceries"));
  });

  it("rolls back onChange on patch failure", async () => {
    patchMock.mockRejectedValueOnce(new Error("network"));
    const onChange = vi.fn();
    render(
      <CategoryChip
        transactionId="t1"
        effective="unknown"
        isOverridden={false}
        onChange={onChange}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /unknown/ }));
    fireEvent.click(screen.getByRole("button", { name: /groceries/ }));

    await waitFor(() => {
      expect(onChange).toHaveBeenNthCalledWith(1, "groceries");
      expect(onChange).toHaveBeenNthCalledWith(2, "unknown");
    });
  });
});
