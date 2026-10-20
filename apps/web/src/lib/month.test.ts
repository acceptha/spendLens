import { describe, it, expect, vi, afterEach } from "vitest";
import { currentMonthKST } from "./month";

describe("currentMonthKST", () => {
  afterEach(() => vi.useRealTimers());
  it("uses Asia/Seoul (UTC 2026-09-30 16:00 = KST 10-01)", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-09-30T16:00:00Z"));
    expect(currentMonthKST()).toBe("2026-10");
  });
});
