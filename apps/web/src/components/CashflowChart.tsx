import { Card, Title, LineChart } from "@tremor/react";
import type { CashflowBucket } from "../lib/api";

export function CashflowChart({ data }: { data: CashflowBucket[] }) {
  return (
    <Card>
      <Title>월별 추세 — 지출 vs 수입</Title>
      <LineChart
        data={data.map((d) => ({ month: d.month, 지출: Number(d.expense), 수입: Number(d.income) }))}
        index="month"
        categories={["지출", "수입"]}
        valueFormatter={(v) => `₩${v.toLocaleString()}`}
        colors={["cyan", "emerald"]}
      />
    </Card>
  );
}
