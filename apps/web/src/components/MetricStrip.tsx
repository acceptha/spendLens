import { Card, Text, Metric } from "@tremor/react";
import type { SummaryResponse } from "../lib/api";
import { formatWon } from "../lib/format";

function won(s: string): string {
  return formatWon(s);
}

// 2열 모바일 카드에서 "-₩12,950"이 줄바꿈되지 않게: 작은 화면은 글자를 줄이고 nowrap.
const METRIC_CLS = "text-xl sm:text-tremor-metric whitespace-nowrap";

export function MetricStrip({ summary }: { summary: SummaryResponse }) {
  const diff = summary.prev_month_diff_pct;
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      <Card>
        <Text>지출 총액</Text>
        <Metric className={METRIC_CLS}>{won(summary.total_amount)}</Metric>
        {diff !== null && (
          <Text className="text-zinc-400 mt-1">
            전월 대비 {diff > 0 ? "+" : ""}{diff.toFixed(1)}%
          </Text>
        )}
      </Card>
      <Card><Text>수입 총액</Text><Metric className={METRIC_CLS}>{won(summary.income_total)}</Metric></Card>
      <Card><Text>순저축</Text><Metric className={METRIC_CLS}>{won(summary.net_savings)}</Metric></Card>
      <Card>
        <Text>저축률</Text>
        <Metric className={METRIC_CLS}>{summary.savings_rate !== null ? `${summary.savings_rate.toFixed(1)}%` : "—"}</Metric>
      </Card>
    </div>
  );
}
