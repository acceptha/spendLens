import { Card, Title, Text } from "@tremor/react";
import { useInsight, useGenerateInsight } from "../lib/queries";

const TYPE_LABEL: Record<string, string> = {
  top_growth: "📈 급증", anomaly: "⚠️ 이상", saving_tip: "💡 절약 팁",
};

export function InsightCard({ month }: { month: string }) {
  const insightQuery = useInsight(month);
  const generate = useGenerateInsight();
  const insight = insightQuery.data ?? null;
  const loading = generate.isPending;

  let error: string | null = null;
  if (generate.isError) {
    const status = (generate.error as { response?: { status?: number } })?.response?.status;
    error =
      status === 503
        ? "이번 달 LLM 예산을 초과했습니다. 나중에 다시 시도하세요."
        : "인사이트 생성에 실패했습니다.";
  }

  function onGenerate() {
    // 이미 인사이트가 있으면 "다시 생성" → force=true로 캐시 무시하고 재생성
    generate.mutate({ month, force: insight != null });
  }

  return (
    <Card>
      <div className="flex items-center justify-between">
        <Title>월간 인사이트</Title>
        <button onClick={onGenerate} disabled={loading}
          className="bg-blue-700 text-white text-xs px-3 py-1 rounded disabled:opacity-50">
          {loading ? "생성 중…" : insight ? "다시 생성" : "인사이트 생성"}
        </button>
      </div>
      {error && <Text className="text-red-400 mt-2">{error}</Text>}
      {insight && (
        <div className="mt-3 space-y-2">
          <Text className="text-zinc-200">{insight.summary}</Text>
          <ul className="space-y-1">
            {insight.highlights.map((h, i) => (
              <li key={i} className="text-sm text-zinc-300">
                <span className="text-zinc-400">{TYPE_LABEL[h.type] ?? h.type}</span>{" "}
                <b>{h.title}</b> — {h.detail}
              </li>
            ))}
          </ul>
        </div>
      )}
      {!insight && !error && (
        <Text className="text-zinc-500 mt-2">버튼을 눌러 이번 달 지출 인사이트를 생성하세요.</Text>
      )}
    </Card>
  );
}
