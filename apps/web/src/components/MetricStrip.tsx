import { Card, Text, Metric } from "@tremor/react";
import type { SummaryResponse } from "../lib/api";

function won(s: string): string {
  return `₩${Number(s).toLocaleString()}`;
}

export function MetricStrip({ summary }: { summary: SummaryResponse }) {
  const diff = summary.prev_month_diff_pct;
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      <Card>
        <Text>지출 총액</Text>
        <Metric>{won(summary.total_amount)}</Metric>
        {diff !== null && (
          <Text className="text-zinc-400 mt-1">
            전월 대비 {diff > 0 ? "+" : ""}{diff.toFixed(1)}%
          </Text>
        )}
      </Card>
      <Card><Text>수입 총액</Text><Metric>{won(summary.income_total)}</Metric></Card>
      <Card><Text>순저축</Text><Metric>{won(summary.net_savings)}</Metric></Card>
      <Card>
        <Text>저축률</Text>
        <Metric>{summary.savings_rate !== null ? `${summary.savings_rate.toFixed(1)}%` : "—"}</Metric>
      </Card>
    </div>
  );
}
