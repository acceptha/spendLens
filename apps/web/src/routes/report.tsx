import { Link, useSearchParams } from "react-router-dom";
import { BudgetBar } from "../components/BudgetBar";
import type { MonthlyReport, ReportCategoryChange } from "../lib/api";
import { categoryLabel } from "../lib/categories";
import { formatWon } from "../lib/format";
import { useMonthlyReport } from "../lib/queries";

function monthTitle(month: string): string {
  return `${month.slice(0, 4)}년 ${Number(month.slice(5, 7))}월 결산`;
}

function signedWon(diff: string): string {
  const n = Number(diff);
  return n > 0 ? `+${formatWon(n)}` : formatWon(n);
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="border border-zinc-800 rounded-lg p-4 space-y-3">
      <h3 className="text-sm text-zinc-400">{title}</h3>
      {children}
    </section>
  );
}

function ChangeList({ items, tone }: { items: ReportCategoryChange[]; tone: string }) {
  if (items.length === 0) return <p className="text-sm text-zinc-500">없음</p>;
  return (
    <ul className="space-y-1 text-sm">
      {items.map((c) => (
        <li key={c.category} className={tone}>{`${categoryLabel(c.category)} ${signedWon(c.diff)}`}</li>
      ))}
    </ul>
  );
}

function Summary({ s }: { s: NonNullable<MonthlyReport["summary"]> }) {
  const diff = s.spent_diff_pct;
  return (
    <div className="border border-zinc-800 rounded-lg p-4 flex flex-wrap items-baseline gap-x-6 gap-y-2">
      <div>
        <div className="text-xs text-zinc-400">지출</div>
        <div className="text-2xl font-semibold">{formatWon(s.spent)}</div>
        {diff !== null && (
          <div className="text-xs text-zinc-400">{`전월 대비 ${diff > 0 ? "+" : ""}${Math.round(diff)}%`}</div>
        )}
      </div>
      <div>
        <div className="text-xs text-zinc-400">수입</div>
        <div className="text-lg">{formatWon(s.income)}</div>
      </div>
      <div>
        <div className="text-xs text-zinc-400">순저축</div>
        <div className="text-lg">{formatWon(s.net_savings)}</div>
        {s.savings_rate !== null && (
          <div className="text-xs text-zinc-400">{`저축률 ${Math.round(s.savings_rate)}%`}</div>
        )}
      </div>
    </div>
  );
}

export function ReportPage() {
  const [params, setParams] = useSearchParams();
  const requested = params.get("month") ?? undefined;
  const q = useMonthlyReport(requested);
  const r = q.data;

  if (q.isLoading) return <p className="p-8 text-zinc-400 text-sm">로딩…</p>;
  if (q.isError) {
    return (
      <div role="alert" className="m-8 bg-red-900/30 border border-red-700 text-red-200 text-sm rounded p-3">
        결산을 불러오는 중 오류가 발생했습니다.
      </div>
    );
  }
  if (!r || !r.month || !r.summary) {
    return <p className="p-8 text-zinc-400">아직 거래가 없습니다. 거래내역에서 명세서를 업로드하세요.</p>;
  }

  const overItems = r.budget?.items.filter((i) => i.level === "over") ?? [];

  return (
    <div className="max-w-3xl mx-auto p-4 sm:p-8 space-y-4">
      <div className="flex items-center gap-3">
        <h2 className="text-2xl">{monthTitle(r.month)}</h2>
        <select
          value={r.month}
          onChange={(e) => setParams({ month: e.target.value })}
          className="bg-zinc-900 border border-zinc-700 rounded px-2 py-1 text-sm"
          aria-label="결산 월 선택"
        >
          {r.available_months.map((m) => <option key={m} value={m}>{m}</option>)}
        </select>
      </div>

      <Summary s={r.summary} />

      <Section title="예산 성적표">
        {r.budget ? (
          <>
            <p className="text-lg">{`${r.budget.total}개 중 ${r.budget.kept}개 지켰어요`}</p>
            {overItems.map((i) => <BudgetBar key={i.category} item={i} />)}
          </>
        ) : (
          <p className="text-sm text-zinc-400">
            예산을 정하면 결산에 성적표가 나와요.{" "}
            <Link to="/budget" className="underline">예산 설정</Link>
          </p>
        )}
      </Section>

      {r.available_months.includes(r.summary.prev_month) ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <Section title="전월보다 늘어난 지출">
            <ChangeList items={r.category_changes.increased} tone="text-red-300" />
          </Section>
          <Section title="전월보다 줄어든 지출">
            <ChangeList items={r.category_changes.decreased} tone="text-emerald-300" />
          </Section>
        </div>
      ) : (
        // 전월 기록이 없으면 모든 카테고리가 "늘어남"으로 보이는 착시 → 비교 생략
        <Section title="전월 대비">
          <p className="text-sm text-zinc-500">비교할 전월 기록이 없어요</p>
        </Section>
      )}

      <Section title="많이 쓴 카테고리 Top 5">
        <ul className="space-y-1 text-sm">
          {r.top_categories.map((c) => (
            <li key={c.category} className="flex justify-between gap-3">
              <span>{categoryLabel(c.category)}</span>
              <span className="text-zinc-300 whitespace-nowrap">
                {`${formatWon(c.amount)} · ${Math.round(c.share * 100)}%`}
              </span>
            </li>
          ))}
        </ul>
      </Section>

      <Section title="이달의 인사이트">
        {r.insight ? (
          <div className="space-y-2 text-sm">
            <p>{r.insight.summary}</p>
            <ul className="space-y-1 text-zinc-300">
              {r.insight.highlights.map((h, i) => (
                <li key={i}><span className="font-medium">{h.title}</span> — {h.detail}</li>
              ))}
            </ul>
          </div>
        ) : (
          <p className="text-sm text-zinc-500">인사이트를 만들지 못했어요</p>
        )}
      </Section>
    </div>
  );
}
