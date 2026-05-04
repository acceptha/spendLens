import { useEffect, useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth } from "../stores/auth";

type Txn = {
  id: string;
  txn_date: string;
  txn_time: string | null;
  amount: string;
  merchant_raw: string;
  card_last4: string | null;
  category: string;
  is_canceled: boolean;
  essential_reason: string | null;
};

export function AppPage() {
  const [txns, setTxns] = useState<Txn[]>([]);
  const [msg, setMsg] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const isAuthed = useAuth((s) => s.isAuthed());
  const nav = useNavigate();

  useEffect(() => {
    if (!isAuthed) {
      nav("/login");
      return;
    }
    refresh();
  }, [isAuthed]);

  async function refresh() {
    const r = await api.get<Txn[]>("/transactions");
    setTxns(r.data);
  }

  async function upload(file: File) {
    const fd = new FormData();
    fd.append("file", file);
    setMsg("업로드 중...");
    try {
      const r = await api.post<{ uploaded: number; skipped: number }>(
        "/transactions/upload", fd,
      );
      setMsg(`업로드 ${r.data.uploaded}건, dedup ${r.data.skipped}건`);
      await refresh();
    } catch (e: any) {
      setMsg(`실패: ${JSON.stringify(e.response?.data?.detail ?? e.message)}`);
    }
  }

  return (
    <div className="p-8 max-w-3xl mx-auto">
      <h2 className="text-2xl mb-4">My Transactions</h2>
      <input ref={fileInputRef} type="file" accept=".xlsx" className="hidden"
             onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])} />
      <button className="px-4 py-2 bg-blue-600 rounded mb-4"
              onClick={() => fileInputRef.current?.click()}>
        삼성카드 XLSX 업로드
      </button>
      {msg && <p className="mb-4 text-sm text-zinc-400">{msg}</p>}
      <ul className="space-y-2">
        {txns.map((t) => (
          <li key={t.id} className="border border-zinc-800 rounded p-3">
            <div className="flex justify-between">
              <span>
                {t.txn_date} · {t.merchant_raw}
                {t.is_canceled && <span className="ml-2 text-red-400 text-xs">[Canceled]</span>}
              </span>
              <span className="font-mono">{Number(t.amount).toLocaleString()}원</span>
            </div>
            <div className="text-xs text-zinc-500 mt-1">
              [{t.category}] · {t.card_last4 ? `****-${t.card_last4}` : ""}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
