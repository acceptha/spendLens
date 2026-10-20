/** 이번 달(YYYY-MM), Asia/Seoul 기준 — 서버 예산 "이번 달"과 같은 기준. */
export function currentMonthKST(): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Seoul", year: "numeric", month: "2-digit",
  }).format(new Date());
}
