import { useState } from "react";
import { patchEssential } from "../lib/api";

type Override = boolean | null;

function next(o: Override): Override {
  if (o === null) return true;
  if (o === true) return false;
  return null;
}

type Props = {
  transactionId: string;
  override: Override;
  effective: boolean;
  onChange: (next: Override) => void;
};

export function EssentialToggle({ transactionId, override, effective, onChange }: Props) {
  const [saving, setSaving] = useState(false);

  const label =
    override === true ? "필수"
    : override === false ? "비필수"
    : `자동(${effective ? "필수" : "비필수"})`;

  const cls =
    override === true ? "bg-emerald-700"
    : override === false ? "bg-amber-700"
    : "bg-zinc-700";

  async function onClick() {
    const target = next(override);
    const prev = override;
    setSaving(true);
    onChange(target);
    try {
      await patchEssential(transactionId, target);
    } catch {
      onChange(prev);
    } finally {
      setSaving(false);
    }
  }

  return (
    <button onClick={onClick} disabled={saving}
      className={`${cls} text-white text-xs px-2 py-0.5 rounded disabled:opacity-50`}
      aria-label={`필수 여부: ${label}`}>
      {label}
    </button>
  );
}
