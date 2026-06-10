import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

const { patchMock } = vi.hoisted(() => ({ patchMock: vi.fn() }));
vi.mock("../lib/api", () => ({ patchEssential: patchMock }));

import { EssentialToggle } from "./EssentialToggle";

describe("EssentialToggle", () => {
  beforeEach(() => patchMock.mockReset());

  it("cycles 자동 → 필수 on click and patches true", async () => {
    patchMock.mockResolvedValueOnce(undefined);
    const onChange = vi.fn();
    render(<EssentialToggle transactionId="t1" override={null} effective={false} onChange={onChange} />);
    fireEvent.click(screen.getByRole("button"));
    expect(onChange).toHaveBeenCalledWith(true);
    await waitFor(() => expect(patchMock).toHaveBeenCalledWith("t1", true));
  });

  it("cycles 필수 → 비필수", async () => {
    patchMock.mockResolvedValue(undefined);
    const onChange = vi.fn();
    render(<EssentialToggle transactionId="t1" override={true} effective={true} onChange={onChange} />);
    fireEvent.click(screen.getByRole("button"));
    expect(onChange).toHaveBeenCalledWith(false);
  });

  it("rolls back on failure", async () => {
    patchMock.mockRejectedValueOnce(new Error("net"));
    const onChange = vi.fn();
    render(<EssentialToggle transactionId="t1" override={null} effective={false} onChange={onChange} />);
    fireEvent.click(screen.getByRole("button"));
    await waitFor(() => {
      expect(onChange).toHaveBeenNthCalledWith(1, true);
      expect(onChange).toHaveBeenNthCalledWith(2, null);
    });
  });
});
