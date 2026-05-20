import { useEffect, useState } from "react";
import { api, type TransactionRow } from "../lib/api";
import { TransactionList } from "../components/TransactionList";

export function GuestPage() {
  const [txns, setTxns] = useState<TransactionRow[]>([]);
  useEffect(() => {
    api.get<TransactionRow[]>("/seed/transactions").then((r) => setTxns(r.data));
  }, []);
  return (
    <div className="p-8 max-w-3xl mx-auto">
      <h2 className="text-2xl mb-4">Guest Demo · 김지출의 한 달</h2>
      <TransactionList items={txns} />
    </div>
  );
}
