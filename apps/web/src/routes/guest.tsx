import { useEffect, useState } from "react";
import { api } from "../lib/api";

type Txn = {
  txn_date: string;
  txn_time: string | null;
  amount: string;
  merchant_raw: string;
  category: string;
  essential: boolean | null;
  essential_reason: string | null;
};

export function GuestPage() {
  const [txns, setTxns] = useState<Txn[]>([]);
  useEffect(() => {
    api.get<Txn[]>("/seed/transactions").then((r) => setTxns(r.data));
  }, []);
  return (
    <div className="p-8 max-w-3xl mx-auto">
      <h2 className="text-2xl mb-4">Guest Demo · 김지출의 한 달</h2>
      <ul className="space-y-2">
        {txns.map((t, i) => (
          <li key={i} className="border border-zinc-800 rounded p-3">
            <div className="flex justify-between">
              <span>{t.txn_date} · {t.merchant_raw}</span>
              <span className="font-mono">{Number(t.amount).toLocaleString()}원</span>
            </div>
            <div className="text-xs text-zinc-500 mt-1">
              [{t.category}] {t.essential === false ? "비필수" : "필수"} · {t.essential_reason}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
