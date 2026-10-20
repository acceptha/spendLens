import type { BudgetItem, BudgetLevel } from "../lib/api";
import { budgetLabel } from "../lib/categories";
import { formatWon } from "../lib/format";

const BAR: Record<BudgetLevel, string> = {
  ok: "bg-emerald-500",
  warn: "bg-amber-500",
  over: "bg-red-500",
};
const BADGE: Record<BudgetLevel, string | null> = { ok: null, warn: "주의", over: "초과" };

export function BudgetBar({ item }: { item: BudgetItem }) {
  const pct = Math.round(item.ratio * 100);
  const badge = BADGE[item.level];
  return (
    <div className="space-y-1">
      <div className="flex items-baseline justify-between gap-3 text-sm">
        <span className="flex items-center gap-2 min-w-0">
          <span className="text-zinc-100">{budgetLabel(item.category)}</span>
          {badge && (
            <span className={`text-xs px-1.5 rounded ${
              item.level === "over" ? "bg-red-900/60 text-red-200" : "bg-amber-900/60 text-amber-200"
            }`}>{badge}</span>
          )}
        </span>
        <span className="text-zinc-300 whitespace-nowrap">
          <span>{`${formatWon(item.spent)} / ${formatWon(item.budget)}`}</span>
          <span className="ml-2 text-zinc-400">{`${pct}%`}</span>
        </span>
      </div>
      <div
        role="progressbar"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`${budgetLabel(item.category)} 예산 사용률`}
        className="h-2 rounded bg-zinc-800 overflow-hidden"
      >
        <div className={`h-full ${BAR[item.level]}`} style={{ width: `${Math.min(pct, 100)}%` }} />
      </div>
      {item.projected !== null && (
        <p className="text-xs text-zinc-500">{`이 속도면 월말 ${formatWon(item.projected)} 예상`}</p>
      )}
    </div>
  );
}
