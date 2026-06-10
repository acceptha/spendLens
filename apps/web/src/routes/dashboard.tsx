import { useEffect, useState } from "react";
import { Card, DonutChart, Title } from "@tremor/react";
import {
  fetchMonths, fetchSummary, fetchByCategory, fetchCashflowByMonth,
  fetchTopMerchants, fetchByEssential,
  type SummaryResponse, type CategoryBucket, type CashflowBucket,
  type MerchantBucket, type EssentialBucket,
} from "../lib/api";
import { InsightCard } from "../components/InsightCard";
import { MetricStrip } from "../components/MetricStrip";
import { CashflowChart } from "../components/CashflowChart";
import { EssentialDonut } from "../components/EssentialDonut";

export function DashboardPage() {
  const [months, setMonths] = useState<string[]>([]);
  const [month, setMonth] = useState<string>("");
  const [summary, setSummary] = useState<SummaryResponse | null>(null);
  const [byCategory, setByCategory] = useState<CategoryBucket[]>([]);
  const [cashflow, setCashflow] = useState<CashflowBucket[]>([]);
  const [topMerchants, setTopMerchants] = useState<MerchantBucket[]>([]);
  const [byEssential, setByEssential] = useState<EssentialBucket[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchMonths()
      .then((ms) => { setMonths(ms); if (ms.length > 0) setMonth(ms[0]); else setLoading(false); })
      .catch(() => { setError("월 목록을 불러올 수 없습니다."); setLoading(false); });
  }, []);

  useEffect(() => {
    if (!month) return;
    setLoading(true);
    setError(null);
    Promise.all([
      fetchSummary(month), fetchByCategory(month), fetchCashflowByMonth(6),
      fetchTopMerchants(month, 5), fetchByEssential(month),
    ])
      .then(([s, c, cf, t, e]) => {
        setSummary(s); setByCategory(c); setCashflow(cf); setTopMerchants(t); setByEssential(e);
      })
      .catch(() => setError("대시보드 데이터를 불러오는 중 오류가 발생했습니다."))
      .finally(() => setLoading(false));
  }, [month]);

  if (months.length === 0 && !loading) {
    return (
      <div className="p-8 text-zinc-400">
        아직 거래가 없습니다. /app에서 명세서를 업로드하세요.
      </div>
    );
  }

  return (
    <div className="p-6 space-y-4">
      {error && (
        <div role="alert" className="bg-red-900/30 border border-red-700 text-red-200 text-sm rounded p-3">
          {error}
        </div>
      )}
      <div className="flex items-center gap-3">
        <select value={month} onChange={(e) => setMonth(e.target.value)}
          className="bg-zinc-900 border border-zinc-700 rounded px-2 py-1 text-sm" aria-label="월 선택">
          {months.map((m) => (<option key={m} value={m}>{m}</option>))}
        </select>
      </div>

      {loading ? (
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
