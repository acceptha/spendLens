import { useEffect, useRef, useState } from "react";
import { fetchMonths } from "../lib/api";
import { CATEGORIES } from "./CategoryChip";

type Props = {
  month: string | null;
  setMonth: (m: string | null) => void;
  categories: string[];
  setCategories: (cs: string[]) => void;
  search: string;
  setSearch: (s: string) => void;
};

export function FilterBar({ month, setMonth, categories, setCategories, search, setSearch }: Props) {
  const [availableMonths, setAvailableMonths] = useState<string[]>([]);
  const detailsRef = useRef<HTMLDetailsElement>(null);

  useEffect(() => {
    fetchMonths().then(setAvailableMonths).catch(() => setAvailableMonths([]));
  }, []);

  // <details>는 outside click으로 자동으로 안 닫힘 → mousedown 리스너로 처리
  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      const el = detailsRef.current;
      if (el && el.open && !el.contains(e.target as Node)) {
        el.open = false;
      }
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  function toggleCategory(c: string) {
    if (categories.includes(c)) {
      setCategories(categories.filter((x) => x !== c));
    } else {
      setCategories([...categories, c]);
    }
  }

  return (
    <div className="flex flex-wrap gap-2 p-4 border-b border-zinc-800 items-center">
      <select
        value={month ?? ""}
        onChange={(e) => setMonth(e.target.value || null)}
        className="bg-zinc-900 border border-zinc-700 rounded px-2 py-1 text-sm"
        aria-label="월 선택"
      >
        <option value="">전체 기간</option>
        {availableMonths.map((m) => (
          <option key={m} value={m}>
            {m}
          </option>
        ))}
      </select>

      <input
        type="text"
        placeholder="가맹점 검색"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="bg-zinc-900 border border-zinc-700 rounded px-2 py-1 text-sm flex-1 min-w-[120px]"
        aria-label="검색"
      />

      <details ref={detailsRef} className="relative">
        <summary className="cursor-pointer text-sm text-zinc-400 px-2 py-1 border border-zinc-700 rounded list-none">
          카테고리 ({categories.length})
        </summary>
        <div className="absolute top-full right-0 mt-1 bg-zinc-900 border border-zinc-700 rounded p-2 z-10 max-h-72 overflow-y-auto whitespace-nowrap">
          {CATEGORIES.map((c) => (
            <label key={c} className="block text-xs text-zinc-200 hover:bg-zinc-800 px-2 py-1 cursor-pointer">
              <input
                type="checkbox"
                checked={categories.includes(c)}
                onChange={() => toggleCategory(c)}
                className="mr-2"
                aria-label={c}
              />
              {c}
            </label>
          ))}
        </div>
      </details>

      {categories.length > 0 && (
        <button
          onClick={() => setCategories([])}
          className="text-xs text-zinc-500 hover:text-white"
        >
          ✕ 카테고리 초기화
        </button>
      )}
    </div>
  );
}
