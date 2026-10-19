/** 원화 표기. 음수는 부호를 기호 앞에 둔다: -₩12,950 (₩-12,950 아님). */
export function formatWon(value: number | string): string {
  const n = Number(value);
  return `${n < 0 ? "-" : ""}₩${Math.abs(n).toLocaleString()}`;
}
