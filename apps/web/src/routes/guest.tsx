import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { TransactionList } from "../components/TransactionList";

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
      <TransactionList items={txns} />
    </div>
  );
}
