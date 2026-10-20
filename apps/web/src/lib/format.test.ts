import { describe, it, expect } from "vitest";
import { formatWon, ro } from "./format";

describe("formatWon", () => {
  it("puts the minus sign before ₩", () => {
    expect(formatWon(-12950)).toBe("-₩12,950");
    expect(formatWon("1282530.00")).toBe("₩1,282,530");
    expect(formatWon(0)).toBe("₩0");
  });
});

describe("ro", () => {
  it("picks 으로/로 by the final consonant (ㄹ받침은 로)", () => {
    expect(ro("커피")).toBe("로");
    expect(ro("쇼핑")).toBe("으로");
    expect(ro("간식·야식")).toBe("으로");
    expect(ro("미분류")).toBe("로");
    expect(ro("공과금")).toBe("으로");
    expect(ro("서울")).toBe("로");
    expect(ro("CU")).toBe("로");
  });
});
