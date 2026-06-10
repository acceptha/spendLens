import { Card, Title, DonutChart } from "@tremor/react";
import type { EssentialBucket } from "../lib/api";

export function EssentialDonut({ data }: { data: EssentialBucket[] }) {
  return (
    <Card>
      <Title>필수 vs 비필수</Title>
      <DonutChart
        data={data.map((b) => ({ name: b.essential ? "필수" : "비필수", value: Number(b.amount) }))}
        category="value" index="name"
        valueFormatter={(v) => `₩${v.toLocaleString()}`}
        colors={["emerald", "amber"]}
      />
    </Card>
  );
}
