import { Link } from "react-router-dom";
import { BudgetBar } from "./BudgetBar";
import type { BudgetItem } from "../lib/api";
import { TOTAL_KEY, budgetLabel } from "../lib/categories";
import { useBudgetStatus } from "../lib/queries";

function alertText(i: BudgetItem): string {
  const pct = Math.round(i.ratio * 100);
  if (i.level === "over") return `${budgetLabel(i.category)} ${pct}% 초과`;
  if (i.ratio >= 0.8) return `${budgetLabel(i.category)} ${pct}% 사용`;
  return `${budgetLabel(i.category)} 월말 예상 초과`;
}

export function BudgetSummaryCard({ month }: { month: string | undefined }) {
  const q = useBudgetStatus(month);
  if (!month || !q.data) return null;
  const href = `/budget?month=${month}`;
  const items = q.data.items;

  if (items.length === 0) {
    return (
      <Link to={href} className="block border border-zinc-800 rounded-lg p-4 text-sm text-zinc-400 hover:text-white">
        예산 설정하기 →
      </Link>
    );
  }

  // 서버가 ratio 내림차순으로 정렬해 준다 — 초과가 앞에 온다.
  const total = items.find((i) => i.category === TOTAL_KEY);
  const alerts = items
    .filter((i) => i.category !== TOTAL_KEY && i.level !== "ok")
    .slice(0, 3);

  return (
    <Link to={href} className="block border border-zinc-800 rounded-lg p-4 space-y-3 hover:border-zinc-600">
      <div className="text-sm text-zinc-400">이번 달 예산</div>
      {total && <BudgetBar item={total} />}
      {alerts.length > 0 && (
        <ul className="text-sm space-y-1">
          {alerts.map((i) => (
            <li key={i.category} className={i.level === "over" ? "text-red-300" : "text-amber-300"}>
              {alertText(i)}
            </li>
          ))}
        </ul>
      )}
    </Link>
  );
}
