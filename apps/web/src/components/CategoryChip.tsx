import { useState, useRef, useEffect } from "react";
import { patchCategory } from "../lib/api";

export const CATEGORIES = [
  "coffee", "lunch", "dinner", "snack_late",
  "groceries", "transport", "telecom",
  "subscription", "entertainment", "health",
  "shopping", "utilities", "etc", "unknown",
  "savings", "insurance", "income", "transfer", "housing",
] as const;

type Props = {
  transactionId: string;
  effective: string;
  isOverridden: boolean;
  onChange: (newCategory: string) => void;
};

export function CategoryChip({ transactionId, effective, isOverridden, onChange }: Props) {
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    if (open) document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, [open]);

  async function pick(cat: string) {
    if (cat === effective) {
      setOpen(false);
      return;
    }
    setSaving(true);
    const prev = effective;
    onChange(cat); // 낙관적 업데이트
    try {
      await patchCategory(transactionId, cat);
      setOpen(false);
    } catch {
      onChange(prev); // 롤백
    } finally {
      setSaving(false);
    }
  }

  const bg = effective === "unknown" ? "bg-zinc-700" : "bg-blue-700";
  const dot = isOverridden ? "•" : "";

  return (
    <div ref={ref} className="relative inline-block">
      <button
        onClick={() => setOpen((v) => !v)}
        disabled={saving}
        className={`${bg} text-white text-xs px-2 py-0.5 rounded disabled:opacity-50`}
        aria-label={`카테고리: ${effective}`}
      >
        {effective}{dot} ▾
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
              {c === effective ? "✓ " : "  "}{c}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
