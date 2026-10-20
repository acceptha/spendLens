/** 원화 표기. 음수는 부호를 기호 앞에 둔다: -₩12,950 (₩-12,950 아님). */
export function formatWon(value: number | string): string {
  const n = Number(value);
  return `${n < 0 ? "-" : ""}₩${Math.abs(n).toLocaleString()}`;
}

/** 조사 '(으)로' 중 맞는 쪽: 받침 있으면 '으로', 없거나 ㄹ받침이면 '로'. 한글이 아니면 '로'. */
export function ro(word: string): "로" | "으로" {
  const code = word.charCodeAt(word.length - 1) - 0xac00;
  if (code < 0 || code > 11171) return "로";
  const jong = code % 28;
  return jong === 0 || jong === 8 ? "로" : "으로";
}
