import { useEffect, useState } from "react";
import { Card, DonutChart, BarChart, Title, Text, Metric } from "@tremor/react";
import {
  fetchMonths,
  fetchSummary,
  fetchByCategory,
  fetchByMonth,
  fetchTopMerchants,
  type SummaryResponse,
  type CategoryBucket,
  type MonthBucket,
  type MerchantBucket,
} from "../lib/api";

export function DashboardPage() {
  const [months, setMonths] = useState<string[]>([]);
  const [month, setMonth] = useState<string>("");
  const [summary, setSummary] = useState<SummaryResponse | null>(null);
  const [byCategory, setByCategory] = useState<CategoryBucket[]>([]);
  const [byMonth, setByMonth] = useState<MonthBucket[]>([]);
  const [topMerchants, setTopMerchants] = useState<MerchantBucket[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchMonths()
      .then((ms) => {
        setMonths(ms);
        if (ms.length > 0) setMonth(ms[0]);
        else setLoading(false);
      })
      .catch(() => {
        setError("월 목록을 불러올 수 없습니다.");
        setLoading(false);
      });
  }, []);

  useEffect(() => {
    if (!month) return;
    setLoading(true);
    setError(null);
    Promise.all([
      fetchSummary(month),
      fetchByCategory(month),
      fetchByMonth(6),
      fetchTopMerchants(month, 5),
    ])
      .then(([s, c, m, t]) => {
        setSummary(s);
        setByCategory(c);
        setByMonth(m);
        setTopMerchants(t);
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
        <select
          value={month}
          onChange={(e) => setMonth(e.target.value)}
          className="bg-zinc-900 border border-zinc-700 rounded px-2 py-1 text-sm"
          aria-label="월 선택"
        >
          {months.map((m) => (
            <option key={m} value={m}>{m}</option>
          ))}
        </select>
        {summary && (
          <Text className="text-zinc-400">
            {summary.transaction_count}건 거래 · 합계 ₩{Number(summary.total_amount).toLocaleString()}
          </Text>
        )}
      </div>

      {loading ? (
        <p className="text-zinc-400 text-sm">로딩…</p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Card>
            <Title>카테고리별 지출</Title>
            <DonutChart
              data={byCategory.map((c) => ({ name: c.category, value: Number(c.amount) }))}
              category="value"
              index="name"
              valueFormatter={(v) => `₩${v.toLocaleString()}`}
              colors={[
                "cyan", "amber", "rose", "lime", "violet",
                "orange", "blue", "fuchsia", "emerald", "indigo",
                "yellow", "pink", "teal", "sky", "purple",
                "green", "red", "slate", "gray",
              ]}
            />
          </Card>

          <Card>
            <Title>월별 추이 (최근 6개월)</Title>
            <BarChart
              data={byMonth.map((m) => ({ month: m.month, amount: Number(m.amount) }))}
              index="month"
              categories={["amount"]}
              valueFormatter={(v) => `₩${v.toLocaleString()}`}
              colors={["cyan"]}
            />
          </Card>

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

          <Card>
            <Title>전월 대비</Title>
            <Metric>
              {summary && summary.prev_month_diff_pct !== null
                ? `${summary.prev_month_diff_pct > 0 ? "+" : ""}${summary.prev_month_diff_pct.toFixed(1)}%`
                : "전월 데이터 없음"}
            </Metric>
            {summary && summary.prev_month_diff_pct !== null && (
              <Text className="text-zinc-400 mt-2">
                전월 ₩{Number(summary.prev_month_total).toLocaleString()} → 이번달 ₩{Number(summary.total_amount).toLocaleString()}
              </Text>
            )}
          </Card>
        </div>
      )}
    </div>
  );
}
