import { describe, it, expect } from "vitest";
import { formatWon } from "./format";

describe("formatWon", () => {
  it("puts the minus sign before ₩", () => {
    expect(formatWon(-12950)).toBe("-₩12,950");
    expect(formatWon("1282530.00")).toBe("₩1,282,530");
    expect(formatWon(0)).toBe("₩0");
  });
});
