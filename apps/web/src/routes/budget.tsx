import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { BudgetBar } from "../components/BudgetBar";
import { BUDGETABLE_CATEGORIES, TOTAL_KEY, budgetLabel } from "../lib/categories";
import { currentMonthKST } from "../lib/month";
import { useBudgetStatus, useMonths, useSaveBudget } from "../lib/queries";

/** 숫자만 받는 금액 입력 폼. 빈 값 제출 = null(예산 해제). */
function AmountForm({ label, initial, onSubmit, onCancel, pending }: {
  label: string;
  initial?: string;
  onSubmit: (amount: number | null) => void;
  onCancel?: () => void;
  pending: boolean;
}) {
  const [value, setValue] = useState(initial ?? "");
  return (
    <form
      className="flex items-center gap-2"
      onSubmit={(e) => {
        e.preventDefault();
        const n = value.trim() === "" ? null : Number(value.replace(/[^0-9]/g, ""));
        onSubmit(n === null || Number.isNaN(n) || n <= 0 ? null : n);
      }}
    >
      <input
        aria-label={label}
        inputMode="numeric"
        placeholder="금액(원)"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        className="w-36 bg-zinc-900 border border-zinc-700 rounded px-2 py-1 text-sm"
      />
      <button disabled={pending} className="text-sm px-3 py-1 rounded bg-blue-600 disabled:opacity-50">
        저장
      </button>
      {onCancel && (
        <button type="button" onClick={onCancel} className="text-sm text-zinc-400 hover:text-white">
          취소
        </button>
      )}
    </form>
  );
}

export function BudgetPage() {
  const [params, setParams] = useSearchParams();
  const current = currentMonthKST();
  const month = params.get("month") ?? current;
  const monthsQuery = useMonths();
  const monthOptions = Array.from(new Set([current, ...(monthsQuery.data ?? [])]))
    .filter((m) => m <= current)
    .sort()
    .reverse();

  const statusQ = useBudgetStatus(month);
  const save = useSaveBudget();
  const [editing, setEditing] = useState<string | null>(null);
  const [addCategory, setAddCategory] = useState("");
  const [addAmount, setAddAmount] = useState("");

  const status = statusQ.data;
  const editable = status?.is_current ?? month === current;
  const items = status?.items ?? [];
  const unused = [TOTAL_KEY, ...BUDGETABLE_CATEGORIES].filter(
    (c) => !items.some((i) => i.category === c),
  );

  function submit(category: string, amount: number | null) {
    save.mutate({ category, amount }, { onSuccess: () => setEditing(null) });
  }

  return (
    <div className="max-w-3xl mx-auto p-4 sm:p-8 space-y-4">
      <div className="flex items-center gap-3">
        <h2 className="text-2xl">예산</h2>
        <select
          value={month}
          onChange={(e) => setParams({ month: e.target.value })}
          className="bg-zinc-900 border border-zinc-700 rounded px-2 py-1 text-sm"
          aria-label="월 선택"
        >
          {monthOptions.map((m) => <option key={m} value={m}>{m}</option>)}
        </select>
      </div>

      {!editable && (
        <p className="text-sm text-zinc-400">지난 달 기록입니다. 예산 변경은 이번 달부터 적용됩니다.</p>
      )}
      {statusQ.isError && (
        <div role="alert" className="bg-red-900/30 border border-red-700 text-red-200 text-sm rounded p-3">
          예산을 불러오는 중 오류가 발생했습니다.
        </div>
      )}
      {save.isError && (
        <p role="alert" className="text-sm text-red-400">저장에 실패했습니다. 잠시 후 다시 시도해주세요.</p>
      )}

      {statusQ.isLoading ? (
        <p className="text-zinc-400 text-sm">로딩…</p>
      ) : items.length === 0 && editable ? (
        <div className="border border-zinc-800 rounded p-4 space-y-3">
          <p className="text-zinc-300">한 달 총 지출 한도부터 정해보세요.</p>
          <AmountForm label="총 지출 예산" pending={save.isPending}
                      onSubmit={(a) => submit(TOTAL_KEY, a)} />
        </div>
      ) : items.length === 0 ? (
        <p className="text-zinc-400 text-sm">이 달에는 설정된 예산이 없습니다.</p>
      ) : (
        <ul className="space-y-3">
          {items.map((item) => (
            <li key={item.category} className="border border-zinc-800 rounded p-4 space-y-2">
              <BudgetBar item={item} />
              {editable && (editing === item.category ? (
                <AmountForm
                  label={`${budgetLabel(item.category)} 예산`}
                  initial={String(Number(item.budget))}
                  pending={save.isPending}
                  onSubmit={(a) => submit(item.category, a)}
                  onCancel={() => setEditing(null)}
                />
              ) : (
                <button
                  onClick={() => setEditing(item.category)}
                  className="text-xs text-zinc-400 hover:text-white"
                  aria-label={`편집: ${budgetLabel(item.category)}`}
                >
                  편집
                </button>
              ))}
            </li>
          ))}
        </ul>
      )}

      {editable && items.length > 0 && unused.length > 0 && (
        <form
          className="flex flex-wrap items-center gap-2 border border-dashed border-zinc-700 rounded p-3"
          onSubmit={(e) => {
            e.preventDefault();
            const n = Number(addAmount.replace(/[^0-9]/g, ""));
            if (!addCategory || !n) return;
            save.mutate({ category: addCategory, amount: n }, {
              onSuccess: () => { setAddCategory(""); setAddAmount(""); },
            });
          }}
        >
          <span className="text-sm text-zinc-400">+ 예산 추가</span>
          <select
            aria-label="예산 추가 카테고리"
            value={addCategory}
            onChange={(e) => setAddCategory(e.target.value)}
            className="bg-zinc-900 border border-zinc-700 rounded px-2 py-1 text-sm"
          >
            <option value="">카테고리 선택</option>
            {unused.map((c) => <option key={c} value={c}>{budgetLabel(c)}</option>)}
          </select>
          <input
            aria-label="예산 추가 금액"
            inputMode="numeric"
            placeholder="금액(원)"
            value={addAmount}
            onChange={(e) => setAddAmount(e.target.value)}
            className="w-36 bg-zinc-900 border border-zinc-700 rounded px-2 py-1 text-sm"
          />
          <button disabled={save.isPending} className="text-sm px-3 py-1 rounded bg-blue-600 disabled:opacity-50">
            추가
          </button>
        </form>
      )}
    </div>
  );
}
