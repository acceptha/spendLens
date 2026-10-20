import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { EssentialToggle } from "./EssentialToggle";

// 서버 요청·롤백은 부모의 useEssentialOverride가 담당 — 토글은 다음 상태만 알린다(이중 PATCH 방지).
describe("EssentialToggle", () => {
  it("cycles 자동 → 필수 and reports it exactly once", () => {
    const onChange = vi.fn();
    render(<EssentialToggle override={null} effective={false} onChange={onChange} />);
    fireEvent.click(screen.getByRole("button"));
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenCalledWith(true);
  });

  it("cycles 필수 → 비필수", () => {
    const onChange = vi.fn();
    render(<EssentialToggle override={true} effective={true} onChange={onChange} />);
    fireEvent.click(screen.getByRole("button"));
    expect(onChange).toHaveBeenCalledWith(false);
  });

  it("cycles 비필수 → 자동(null)", () => {
    const onChange = vi.fn();
    render(<EssentialToggle override={false} effective={true} onChange={onChange} />);
    fireEvent.click(screen.getByRole("button"));
    expect(onChange).toHaveBeenCalledWith(null);
  });
});
