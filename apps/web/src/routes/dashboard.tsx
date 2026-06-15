import { useState } from "react";
import { Card, DonutChart, Title } from "@tremor/react";
import { InsightCard } from "../components/InsightCard";
import { MetricStrip } from "../components/MetricStrip";
import { CashflowChart } from "../components/CashflowChart";
import { EssentialDonut } from "../components/EssentialDonut";
import {
  useMonths, useSummary, useByCategory, useCashflow, useTopMerchants, useByEssential,
} from "../lib/queries";

export function DashboardPage() {
  const monthsQuery = useMonths();
  const months = monthsQuery.data ?? [];
  // 사용자가 고르기 전엔 null → 항상 최신 months[0]을 따른다(파생값). useEffect 동기화 금지.
  const [selectedMonth, setSelectedMonth] = useState<string | null>(null);
  const month = selectedMonth ?? months[0];

  const summaryQ = useSummary(month);
  const byCategoryQ = useByCategory(month);
  const cashflowQ = useCashflow(6);
  const topMerchantsQ = useTopMerchants(month, 5);
  const byEssentialQ = useByEssential(month);

  if (!monthsQuery.isLoading && months.length === 0) {
    return (
      <div className="p-8 text-zinc-400">
        아직 거래가 없습니다. /app에서 명세서를 업로드하세요.
      </div>
    );
  }

  // 비활성 쿼리(enabled:false)는 v5에서 isPending이 계속 true → isLoading으로 판정해야 무한 스피너 방지.
  const isLoading =
    monthsQuery.isLoading || summaryQ.isLoading || byCategoryQ.isLoading ||
    cashflowQ.isLoading || topMerchantsQ.isLoading || byEssentialQ.isLoading;
  const isError =
    monthsQuery.isError || summaryQ.isError || byCategoryQ.isError ||
    cashflowQ.isError || topMerchantsQ.isError || byEssentialQ.isError;

  const summary = summaryQ.data ?? null;
  const byCategory = byCategoryQ.data ?? [];
  const cashflow = cashflowQ.data ?? [];
  const topMerchants = topMerchantsQ.data ?? [];
  const byEssential = byEssentialQ.data ?? [];

  return (
    <div className="p-6 space-y-4">
      {isError && (
        <div role="alert" className="bg-red-900/30 border border-red-700 text-red-200 text-sm rounded p-3">
          대시보드 데이터를 불러오는 중 오류가 발생했습니다.
        </div>
      )}
      <div className="flex items-center gap-3">
        <select value={month ?? ""} onChange={(e) => setSelectedMonth(e.target.value)}
          className="bg-zinc-900 border border-zinc-700 rounded px-2 py-1 text-sm" aria-label="월 선택">
          {months.map((m) => (<option key={m} value={m}>{m}</option>))}
        </select>
      </div>

      {isLoading ? (
        <p className="text-zinc-400 text-sm">로딩…</p>
      ) : (
        <div className="space-y-4">
          {month && <InsightCard month={month} />}
          {summary && <MetricStrip summary={summary} />}
          <CashflowChart data={cashflow} />
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Card>
              <Title>카테고리별 지출</Title>
              <DonutChart
                data={byCategory.map((c) => ({ name: c.category, value: Number(c.amount) }))}
                category="value" index="name"
                valueFormatter={(v) => `₩${v.toLocaleString()}`}
                colors={["cyan","amber","rose","lime","violet","orange","blue","fuchsia","emerald","indigo","yellow","pink","teal","sky","purple","green","red","slate","gray"]}
              />
            </Card>
            <EssentialDonut data={byEssential} />
          </div>
          <Card>
            <Title>Top 5 가맹점</Title>
            <ul className="text-sm text-zinc-300 space-y-1 mt-2">
              {topMerchants.length === 0 ? (
                <li className="text-zinc-500">데이터 없음</li>
              ) : (
                topMerchants.map((t, i) => (
                  <li key={t.merchant_raw} className="flex justify-between">
                    <span>{i + 1}. {t.merchant_raw}</span>
                    <span>₩{Number(t.amount).toLocaleString()} ({t.count}건)</span>
                  </li>
                ))
              )}
            </ul>
          </Card>
        </div>
      )}
    </div>
  );
}
