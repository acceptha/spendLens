import { useState } from "react";
import { CATEGORIES } from "./CategoryChip";
import { categoryLabel } from "../lib/categories";
import { todayKST } from "../lib/month";
import { useCreateTransaction } from "../lib/queries";

const ERRORS: Record<string, string> = {
  FUTURE_DATE: "미래 날짜는 입력할 수 없습니다.",
};

function errorMessage(err: unknown): string {
  const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  return (typeof detail === "string" && ERRORS[detail]) || "저장에 실패했습니다. 입력값을 확인해주세요.";
}

const inputCls = "bg-zinc-900 border border-zinc-700 rounded px-2 py-1 text-sm";

/** 현금 등 명세서에 없는 지출·수입 직접 입력. */
export function ManualEntryForm() {
  const [open, setOpen] = useState(false);
  const [kind, setKind] = useState<"expense" | "income">("expense");
  const [date, setDate] = useState(todayKST);
  const [amount, setAmount] = useState("");
  const [merchant, setMerchant] = useState("");
  const [category, setCategory] = useState("");
  const create = useCreateTransaction();

  const amountNum = Number(amount.replace(/[^0-9]/g, ""));
  const canSubmit = amountNum > 0 && merchant.trim().length > 0 && !create.isPending;

  if (!open) {
    return (
      <button onClick={() => setOpen(true)} className="mt-3 text-sm text-zinc-400 hover:text-white">
        + 직접 입력
      </button>
    );
  }

  return (
    <form
      className="mt-3 border border-zinc-800 rounded p-3 space-y-2"
      onSubmit={(e) => {
        e.preventDefault();
        if (!canSubmit) return;
        create.mutate(
          { kind, txn_date: date, amount: amountNum, merchant: merchant.trim(), category: category || null },
          { onSuccess: () => { setAmount(""); setMerchant(""); setCategory(""); } },
        );
      }}
    >
      <div className="flex flex-wrap items-center gap-2">
        <label className="text-sm flex items-center gap-1">
          <input type="radio" name="kind" checked={kind === "expense"} onChange={() => setKind("expense")} />
          지출
        </label>
        <label className="text-sm flex items-center gap-1">
          <input type="radio" name="kind" checked={kind === "income"} onChange={() => setKind("income")} />
          수입
        </label>
        <input aria-label="날짜" type="date" value={date} max={todayKST()}
          onChange={(e) => setDate(e.target.value)} className={inputCls} />
        <input aria-label="금액" inputMode="numeric" placeholder="금액(원)" value={amount}
          onChange={(e) => setAmount(e.target.value)} className={`${inputCls} w-32`} />
        <input aria-label="내용" placeholder="예) 동네 분식" value={merchant} maxLength={100}
          onChange={(e) => setMerchant(e.target.value)} className={`${inputCls} flex-1 min-w-[140px]`} />
        <select aria-label="카테고리" value={category} onChange={(e) => setCategory(e.target.value)}
          className={inputCls}>
          <option value="">자동</option>
          {CATEGORIES.map((c) => <option key={c} value={c}>{categoryLabel(c)}</option>)}
        </select>
        <button disabled={!canSubmit} className="text-sm px-3 py-1 rounded bg-blue-600 disabled:opacity-50">
          추가
        </button>
        <button type="button" onClick={() => setOpen(false)} className="text-sm text-zinc-400 hover:text-white">
          닫기
        </button>
      </div>
      {create.isSuccess && <p role="status" className="text-sm text-emerald-300">추가됨</p>}
      {create.isError && <p role="alert" className="text-sm text-red-400">{errorMessage(create.error)}</p>}
    </form>
  );
}
