// 카테고리 키(API·DB 값) → 화면 표시용 한글 라벨. 키는 백엔드 rulebook/essential과 동기화.
export const CATEGORY_LABELS: Record<string, string> = {
  housing: "주거",
  utilities: "공과금",
  telecom: "통신",
  groceries: "장보기",
  health: "의료",
  insurance: "보험",
  transport: "교통",
  lunch: "점심",
  dinner: "저녁",
  coffee: "커피",
  snack_late: "간식·야식",
  subscription: "구독",
  entertainment: "여가",
  shopping: "쇼핑",
  savings: "저축",
  income: "수입",
  transfer: "이체",
  etc: "기타",
  unknown: "미분류",
};

export function categoryLabel(key: string): string {
  return CATEGORY_LABELS[key] ?? key;
}

/** 라벨 → 키 역조회 (차트 클릭처럼 라벨만 돌려받는 경우). 없으면 입력 그대로. */
export function categoryKey(label: string): string {
  return Object.keys(CATEGORY_LABELS).find((k) => CATEGORY_LABELS[k] === label) ?? label;
}

export const TOTAL_KEY = "_total";

/** 예산을 걸 수 있는 카테고리 — 지출 집계에서 빠지는 수입·이체·저축 제외 (서버와 동일). */
export const BUDGETABLE_CATEGORIES = Object.keys(CATEGORY_LABELS).filter(
  (k) => !["income", "transfer", "savings"].includes(k),
);

export function budgetLabel(key: string): string {
  return key === TOTAL_KEY ? "총 지출" : categoryLabel(key);
}
