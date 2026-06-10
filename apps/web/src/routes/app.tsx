import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, fetchTransactions, type TransactionRow } from "../lib/api";
import { useAuth } from "../stores/auth";
import { UploadDropzone } from "../components/UploadDropzone";
import { TransactionList } from "../components/TransactionList";
import { FilterBar } from "../components/FilterBar";

export function AppPage() {
  const [txns, setTxns] = useState<TransactionRow[]>([]);
  const [msg, setMsg] = useState<string | null>(null);
  const [month, setMonth] = useState<string | null>(null);
  const [categories, setCategories] = useState<string[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const isAuthed = useAuth((s) => s.isAuthed());
  const nav = useNavigate();

  useEffect(() => {
    if (!isAuthed) {
      nav("/login");
    }
  }, [isAuthed, nav]);

  useEffect(() => {
    if (!isAuthed) return;
    setLoading(true);
    fetchTransactions({
      month: month ?? undefined,
      category: categories.length ? categories : undefined,
      search: search || undefined,
      limit: 200,
    })
      .then(setTxns)
      .finally(() => setLoading(false));
  }, [isAuthed, month, categories, search]);

  async function upload(file: File) {
    const fd = new FormData();
    fd.append("file", file);
    setMsg("업로드 중...");
    try {
      const r = await api.post<{ uploaded: number; skipped: number }>(
        "/transactions/upload",
        fd,
      );
      setMsg(`업로드 ${r.data.uploaded}건, dedup ${r.data.skipped}건`);
      // 업로드 후 새로고침 (현 필터 유지)
      const data = await fetchTransactions({
        month: month ?? undefined,
        category: categories.length ? categories : undefined,
        search: search || undefined,
        limit: 200,
      });
      setTxns(data);
    } catch (e: unknown) {
      const detail =
        (e as { response?: { data?: { detail?: unknown } } })?.response?.data
          ?.detail ?? (e as Error).message;
      setMsg(`실패: ${JSON.stringify(detail)}`);
    }
  }

  function onCategoryChange(id: string, newCategory: string) {
    setTxns((prev) =>
      prev.map((t) =>
        t.id === id
          ? {
              ...t,
              user_category_override: newCategory,
              effective_category: newCategory,
            }
          : t,
      ),
    );
  }

  function onEssentialChange(id: string, override: boolean | null) {
    setTxns((prev) =>
      prev.map((t) => (t.id === id ? { ...t, essential_override: override } : t)),
    );
  }

  return (
    <div className="min-h-screen">
      <div className="max-w-3xl mx-auto p-8">
        <h2 className="text-2xl mb-4">My Transactions</h2>
        <UploadDropzone onFile={upload} />
        {msg && <p className="my-4 text-sm text-zinc-400">{msg}</p>}
      </div>
      <FilterBar
        month={month}
        setMonth={setMonth}
        categories={categories}
        setCategories={setCategories}
        search={search}
        setSearch={setSearch}
      />
      <div className="max-w-3xl mx-auto p-8">
        {loading ? (
          <p className="text-zinc-400 text-sm">로딩…</p>
        ) : (
          <TransactionList items={txns} onCategoryChange={onCategoryChange} onEssentialChange={onEssentialChange} />
        )}
      </div>
    </div>
  );
}
