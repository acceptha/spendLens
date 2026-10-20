import type { UploadResult } from "./queries";

const GENERIC = "업로드에 실패했습니다. 잠시 후 다시 시도해주세요.";
const NOT_FOUND = "명세서에서 거래 내역을 찾지 못했습니다. 카드사·은행에서 받은 원본 파일인지 확인해주세요.";

// 서버 에러 코드(transactions/routes.py, parsers) → 사용자 안내 문구.
const MESSAGES: Record<string, string> = {
  INVALID_FILE_TYPE: "엑셀 파일(.xlsx, .xls)만 올릴 수 있습니다.",
  FILE_TOO_LARGE: "파일이 너무 큽니다 (최대 10MB).",
  WORKBOOK_LOAD_FAILED: "엑셀 파일을 열 수 없습니다. 파일이 손상됐거나 엑셀 형식이 아닙니다.",
  UNKNOWN_CARD_FORMAT: "지원하지 않는 명세서 형식입니다. (지원: 삼성카드·우리카드·하나은행)",
  UNSUPPORTED_SOURCE_TYPE: "지원하지 않는 명세서 형식입니다. (지원: 삼성카드·우리카드·하나은행)",
  HEADER_NOT_FOUND: NOT_FOUND,
  SHEET_NOT_FOUND: NOT_FOUND,
  EMPTY_SHEET: NOT_FOUND,
};

export function uploadSuccessMessage({ uploaded, skipped }: UploadResult): string {
  if (uploaded === 0) return `새 거래 없음 (이미 있던 ${skipped}건은 건너뜀)`;
  return skipped > 0 ? `${uploaded}건 추가, 이미 있던 ${skipped}건은 건너뜀` : `${uploaded}건 추가`;
}

export function uploadErrorMessage(err: unknown): string {
  const res = (err as { response?: { status?: number; data?: { detail?: unknown } } })?.response;
  if (res?.status === 413) return MESSAGES.FILE_TOO_LARGE;
  const detail = res?.data?.detail;
  const code = typeof detail === "string" ? detail : (detail as { error?: string } | undefined)?.error;
  return (code && MESSAGES[code]) || GENERIC;
}
