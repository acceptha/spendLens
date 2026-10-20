type Override = boolean | null;

function next(o: Override): Override {
  if (o === null) return true;
  if (o === true) return false;
  return null;
}

type Props = {
  override: Override;
  effective: boolean;
  onChange: (next: Override) => void;
};

export function EssentialToggle({ override, effective, onChange }: Props) {
  const label =
    override === true ? "필수"
    : override === false ? "비필수"
    : `자동(${effective ? "필수" : "비필수"})`;

  const cls =
    override === true ? "bg-emerald-700"
    : override === false ? "bg-amber-700"
    : "bg-zinc-700";

  return (
    <button onClick={() => onChange(next(override))}
      className={`${cls} text-white text-xs px-2 py-0.5 rounded`}
      aria-label={`필수 여부: ${label}`}>
      {label}
    </button>
  );
}
