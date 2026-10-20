import { categoryLabel } from "../lib/categories";
import { ro } from "../lib/format";

export type SameMerchantOffer = { id: string; merchant: string; category: string; count: number };

/** 카테고리 수정 직후 "같은 가맹점 N건도 바꿀까요?" 제안. */
export function SameMerchantBanner({ offer, onApply, onDismiss, pending }: {
  offer: SameMerchantOffer;
  onApply: () => void;
  onDismiss: () => void;
  pending: boolean;
}) {
  const label = categoryLabel(offer.category);
  return (
    <div role="status" className="mb-4 flex flex-wrap items-center gap-2 bg-blue-950/50 border border-blue-800 text-blue-100 text-sm rounded p-3">
      <span className="flex-1 min-w-0">
        {`같은 가맹점 '${offer.merchant}' 거래 ${offer.count}건도 '${label}'${ro(label)} 바꿀까요?`}
      </span>
      <button onClick={onApply} disabled={pending}
        className="px-3 py-1 rounded bg-blue-600 text-white disabled:opacity-50">
        모두 변경
      </button>
      <button onClick={onDismiss} className="px-2 py-1 text-blue-200 hover:text-white">
        닫기
      </button>
    </div>
  );
}
