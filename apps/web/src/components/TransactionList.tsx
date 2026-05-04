export type Txn = {
  id?: string;
  txn_date: string;
  txn_time: string | null;
  amount: string;
  merchant_raw: string;
  category: string;
  card_last4?: string | null;
  is_canceled?: boolean;
  essential?: boolean | null;
  essential_reason?: string | null;
};

export function TransactionList({ items }: { items: Txn[] }) {
  return (
    <ul className="space-y-2" data-testid="txn-list">
      {items.map((t, i) => (
        <li key={t.id ?? i} className="border border-zinc-800 rounded p-3">
          <div className="flex justify-between">
            <span>
              {t.txn_date} · {t.merchant_raw}
              {t.is_canceled && <span className="ml-2 text-red-400 text-xs">[Canceled]</span>}
            </span>
            <span className="font-mono">{Number(t.amount).toLocaleString()}원</span>
          </div>
          <div className="text-xs text-zinc-500 mt-1">
            [{t.category}]
            {t.card_last4 && ` · ****-${t.card_last4}`}
            {t.essential_reason && ` · ${t.essential_reason}`}
          </div>
        </li>
      ))}
    </ul>
  );
}
