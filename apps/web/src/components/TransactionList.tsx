import type { TransactionRow } from "../lib/api";
import { CategoryChip } from "./CategoryChip";
import { EssentialToggle } from "./EssentialToggle";

// W3: TransactionRow는 lib/api.ts의 단일 타입 — 여기선 re-export로 backward-compat
export type Txn = TransactionRow;

type Props = {
  items: TransactionRow[];
  onCategoryChange?: (id: string, newCategory: string) => void;
  onEssentialChange?: (id: string, override: boolean | null) => void;
};

export function TransactionList({ items, onCategoryChange, onEssentialChange }: Props) {
  return (
    <ul className="space-y-2" data-testid="txn-list">
      {items.map((t) => (
        <li key={t.id} className="border border-zinc-800 rounded p-3">
          <div className="flex justify-between items-center">
            <span>
              {t.txn_date} · {t.merchant_raw}
              {t.is_canceled && <span className="ml-2 text-red-400 text-xs">[Canceled]</span>}
            </span>
            <span className="font-mono">{Number(t.amount).toLocaleString()}원</span>
          </div>
          <div className="text-xs text-zinc-500 mt-1 flex items-center gap-2">
            {onCategoryChange ? (
              <CategoryChip
                transactionId={t.id}
                effective={t.effective_category}
                isOverridden={t.user_category_override !== null}
                onChange={(newCat) => onCategoryChange(t.id, newCat)}
              />
            ) : (
              <span>[{t.effective_category ?? t.category}]</span>
            )}
            {t.card_last4 && <span>· ****-{t.card_last4}</span>}
            {onEssentialChange && (
              <EssentialToggle
                transactionId={t.id}
                override={t.essential_override ?? null}
                effective={t.effective_essential ?? false}
                onChange={(ov) => onEssentialChange(t.id, ov)}
              />
            )}
          </div>
        </li>
      ))}
    </ul>
  );
}
