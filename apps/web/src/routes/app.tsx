import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth } from "../stores/auth";
import { UploadDropzone } from "../components/UploadDropzone";
import { TransactionList } from "../components/TransactionList";

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
      <UploadDropzone onFile={upload} />
      {msg && <p className="mb-4 text-sm text-zinc-400">{msg}</p>}
      <TransactionList items={txns} />
    </div>
  );
}
