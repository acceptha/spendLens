import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";


import { CategoryChip } from "./CategoryChip";

describe("CategoryChip", () => {
  it("displays effective category", () => {
    render(
      <CategoryChip
        effective="coffee"
        isOverridden={false}
        onChange={() => {}}
      />,
    );
    expect(screen.getByRole("button", { name: /커피/ })).toBeInTheDocument();
  });

  it("shows override dot when overridden", () => {
    render(
      <CategoryChip
        effective="groceries"
        isOverridden={true}
        onChange={() => {}}
      />,
    );
    expect(screen.getByRole("button", { name: /장보기/ }).textContent).toContain("•");
  });

  it("selecting a category reports it exactly once", () => {
    // 서버 요청은 useCategoryOverride(mutation) 한 곳에서만 — 칩이 직접 보내면 PATCH가 두 번 나간다.
    const onChange = vi.fn();
    render(
      <CategoryChip
        effective="unknown"
        isOverridden={false}
        onChange={onChange}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /미분류/ }));
    fireEvent.click(screen.getByRole("button", { name: /장보기/ }));

    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenCalledWith("groceries");
    expect(screen.queryByRole("button", { name: /^\s*쇼핑/ })).toBeNull(); // 드롭다운 닫힘
  });

  it("picking the current category does nothing", () => {
    const onChange = vi.fn();
    render(
      <CategoryChip effective="unknown" isOverridden={false} onChange={onChange} />,
    );
    fireEvent.click(screen.getByRole("button", { name: /미분류/ }));
    fireEvent.click(screen.getByRole("button", { name: /✓.*미분류/ }));
    expect(onChange).not.toHaveBeenCalled();
  });
});
