import { useEffect, useState } from "react";

/** value가 delayMs 동안 변하지 않으면 그 값을 반영한다. 빠른 연속 변경은 마지막 값만 통과. */
export function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState<T>(value);

  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(t);
  }, [value, delayMs]);

  return debounced;
}
