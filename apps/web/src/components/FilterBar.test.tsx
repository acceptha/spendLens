import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

const { fetchMock } = vi.hoisted(() => ({
  fetchMock: vi.fn().mockResolvedValue(["2026-05", "2026-04"]),
}));
vi.mock("../lib/api", () => ({ fetchMonths: fetchMock }));

import { FilterBar } from "./FilterBar";

describe("FilterBar", () => {
  beforeEach(() => {
    fetchMock.mockClear();
    fetchMock.mockResolvedValue(["2026-05", "2026-04"]);
  });

  it("renders month options from fetchMonths", async () => {
    render(
      <FilterBar
        month={null}
        setMonth={() => {}}
        categories={[]}
        setCategories={() => {}}
        search=""
        setSearch={() => {}}
      />,
    );
    await screen.findByText("2026-05");
    expect(screen.getByText("2026-04")).toBeInTheDocument();
  });

  it("calls setMonth on selection", async () => {
    const setMonth = vi.fn();
    render(
      <FilterBar
        month={null}
        setMonth={setMonth}
        categories={[]}
        setCategories={() => {}}
        search=""
        setSearch={() => {}}
      />,
    );
    await screen.findByText("2026-05");
    fireEvent.change(screen.getByLabelText("월 선택"), { target: { value: "2026-05" } });
    expect(setMonth).toHaveBeenCalledWith("2026-05");
  });

  it("calls setSearch on input", () => {
    const setSearch = vi.fn();
    render(
      <FilterBar
        month={null}
        setMonth={() => {}}
        categories={[]}
        setCategories={() => {}}
        search=""
        setSearch={setSearch}
      />,
    );
    fireEvent.change(screen.getByLabelText("검색"), { target: { value: "스타벅스" } });
    expect(setSearch).toHaveBeenCalledWith("스타벅스");
  });

  it("toggles categories", () => {
    const setCategories = vi.fn();
    render(
      <FilterBar
        month={null}
        setMonth={() => {}}
        categories={["coffee"]}
        setCategories={setCategories}
        search=""
        setSearch={() => {}}
      />,
    );
    fireEvent.click(screen.getByText(/카테고리 \(1\)/));
    const checkbox = screen.getByLabelText("lunch");
    fireEvent.click(checkbox);
    expect(setCategories).toHaveBeenCalledWith(["coffee", "lunch"]);
  });
});
