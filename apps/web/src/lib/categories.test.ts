import { describe, it, expect } from "vitest";
import { CATEGORIES } from "../components/CategoryChip";
import { CATEGORY_LABELS, categoryKey, categoryLabel } from "./categories";

describe("category labels", () => {
  it("covers every category key", () => {
    expect(Object.keys(CATEGORY_LABELS).sort()).toEqual([...CATEGORIES].sort());
  });

  it("round-trips label ↔ key and falls back to input", () => {
    expect(categoryLabel("coffee")).toBe("커피");
    expect(categoryKey("커피")).toBe("coffee");
    expect(categoryLabel("nope")).toBe("nope");
    expect(categoryKey("nope")).toBe("nope");
  });
});
