import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../stores/auth";
import { UploadDropzone } from "../components/UploadDropzone";
import { TransactionList } from "../components/TransactionList";
import { FilterBar } from "../components/FilterBar";
import { SameMerchantBanner, type SameMerchantOffer } from "../components/SameMerchantBanner";
import { useDebouncedValue } from "../lib/useDebouncedValue";
import { uploadErrorMessage, uploadSuccessMessage } from "../lib/uploadMessages";
import {
  useTransactions,
  useUploadStatement,
  useCategoryOverride,
  useEssentialOverride,
  useDeleteTransaction,
  useApplyToMerchant,
} from "../lib/queries";

export function AppPage() {
  const [searchParams] = useSearchParams();
  const categoryParam = searchParams.get("category");
  const [month, setMonth] = useState<string | null>(null);
  const [categories, setCategories] = useState<string[]>(() =>
    categoryParam ? categoryParam.split(",") : [],
  );
  const [search, setSearch] = useState("");
  const debouncedSearch = useDebouncedValue(search, 300);
  const isAuthed = useAuth((s) => s.isAuthed());
  const nav = useNavigate();

  useEffect(() => {
    if (!isAuthed) nav("/login");
  }, [isAuthed, nav]);

  // 대시보드 차트에서 넘어온 ?category= 를 필터에 반영(이미 마운트돼 있어도).
  useEffect(() => {
    if (categoryParam) setCategories(categoryParam.split(","));
  }, [categoryParam]);

  const txnsQuery = useTransactions({
    month: month ?? undefined,
    category: categories.length ? categories : undefined,
    search: debouncedSearch || undefined,
    limit: 200,
  });
  const upload = useUploadStatement();
  const categoryOverride = useCategoryOverride();
  const essentialOverride = useEssentialOverride();
  const deleteTxn = useDeleteTransaction();
  const applyToMerchant = useApplyToMerchant();
  const [offer, setOffer] = useState<SameMerchantOffer | null>(null);
  const [appliedMsg, setAppliedMsg] = useState<string | null>(null);

  function changeCategory(id: string, category: string) {
    setAppliedMsg(null);
    categoryOverride.mutate({ id, category }, {
      onSuccess: (res) => {
        setOffer(res && res.same_merchant_pending > 0 && res.merchant
          ? { id, merchant: res.merchant, category, count: res.same_merchant_pending }
          : null);
      },
    });
  }

  function applyOffer() {
    if (!offer) return;
    applyToMerchant.mutate(offer.id, {
      onSuccess: (res) => {
        setOffer(null);
        setAppliedMsg(`${res.updated}건 변경됨`);
      },
    });
  }

  const txns = txnsQuery.data ?? [];

  let msg: string | null = null;
  if (upload.isPending) {
    msg = "업로드 중...";
  } else if (upload.isError) {
    msg = uploadErrorMessage(upload.error);
  } else if (upload.isSuccess) {
    msg = uploadSuccessMessage(upload.data);
  }

  return (
    <div className="min-h-screen">
      <div className="max-w-3xl mx-auto p-4 sm:p-8">
        <h2 className="text-2xl mb-4">거래내역</h2>
        <UploadDropzone onFile={(file) => upload.mutate(file)} />
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
      <div className="max-w-3xl mx-auto p-4 sm:p-8">
        {txnsQuery.isError && (
          <div role="alert" className="mb-4 bg-red-900/30 border border-red-700 text-red-200 text-sm rounded p-3">
            거래를 불러오는 중 오류가 발생했습니다.
          </div>
        )}
        {offer && (
          <SameMerchantBanner
            offer={offer}
            pending={applyToMerchant.isPending}
            onApply={applyOffer}
            onDismiss={() => setOffer(null)}
          />
        )}
        {appliedMsg && <p role="status" className="mb-4 text-sm text-emerald-300">{appliedMsg}</p>}
        {txnsQuery.isPending ? (
          <p className="text-zinc-400 text-sm">로딩…</p>
        ) : (
          <div className={txnsQuery.isPlaceholderData ? "opacity-60 transition-opacity" : "transition-opacity"}>
            <TransactionList
              items={txns}
              onCategoryChange={changeCategory}
              onEssentialChange={(id, override) =>
                essentialOverride.mutate({ id, essentialOverride: override })}
              onDelete={(id) => deleteTxn.mutate(id)}
            />
          </div>
        )}
      </div>
    </div>
  );
}
