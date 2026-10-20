import { useState, useRef, useEffect } from "react";
import { categoryLabel } from "../lib/categories";

export const CATEGORIES = [
  "coffee", "lunch", "dinner", "snack_late",
  "groceries", "transport", "telecom",
  "subscription", "entertainment", "health",
  "shopping", "utilities", "etc", "unknown",
  "savings", "insurance", "income", "transfer", "housing",
] as const;

type Props = {
  effective: string;
  isOverridden: boolean;
  onChange: (newCategory: string) => void;
};

export function CategoryChip({ effective, isOverridden, onChange }: Props) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    if (open) document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, [open]);

  // 서버 요청·낙관적 갱신·롤백은 부모의 useCategoryOverride가 담당한다 (여기서 보내면 이중 PATCH).
  function pick(cat: string) {
    setOpen(false);
    if (cat !== effective) onChange(cat);
  }

  const bg = effective === "unknown" ? "bg-zinc-700" : "bg-blue-700";
  const dot = isOverridden ? "•" : "";

  return (
    <div ref={ref} className="relative inline-block">
      <button
        onClick={() => setOpen((v) => !v)}
        className={`${bg} text-white text-xs px-2 py-0.5 rounded`}
        aria-label={`카테고리: ${categoryLabel(effective)}`}
      >
        {categoryLabel(effective)}{dot} ▾
      </button>
      {open && (
        <div className="absolute top-full left-0 mt-1 bg-zinc-900 border border-zinc-700 rounded shadow-lg z-10 max-h-60 overflow-y-auto">
          {CATEGORIES.map((c) => (
            <button
              key={c}
              onClick={() => pick(c)}
              className={`block w-full text-left px-3 py-1 text-xs hover:bg-zinc-800 whitespace-nowrap ${
                c === effective ? "text-blue-400" : "text-zinc-200"
              }`}
            >
              {c === effective ? "✓ " : "  "}{categoryLabel(c)}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
