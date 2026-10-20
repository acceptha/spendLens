import { describe, it, expect } from "vitest";
import { uploadErrorMessage, uploadSuccessMessage } from "./uploadMessages";

const apiError = (status: number, detail: unknown) => ({ response: { status, data: { detail } } });

describe("uploadSuccessMessage", () => {
  it("reports new rows and skipped duplicates in Korean", () => {
    expect(uploadSuccessMessage({ uploaded: 12, skipped: 3 })).toBe("12건 추가, 이미 있던 3건은 건너뜀");
    expect(uploadSuccessMessage({ uploaded: 5, skipped: 0 })).toBe("5건 추가");
    expect(uploadSuccessMessage({ uploaded: 0, skipped: 7 })).toBe("새 거래 없음 (이미 있던 7건은 건너뜀)");
  });
});

describe("uploadErrorMessage", () => {
  it("maps API error codes to friendly Korean (no raw JSON)", () => {
    expect(uploadErrorMessage(apiError(400, { error: "INVALID_FILE_TYPE", expected: ".xlsx" })))
      .toBe("엑셀 파일(.xlsx, .xls)만 올릴 수 있습니다.");
    expect(uploadErrorMessage(apiError(400, { error: "FILE_TOO_LARGE" })))
      .toBe("파일이 너무 큽니다 (최대 10MB).");
    expect(uploadErrorMessage(apiError(413, undefined))).toBe("파일이 너무 큽니다 (최대 10MB).");
    expect(uploadErrorMessage(apiError(400, { error: "WORKBOOK_LOAD_FAILED", reason: "x" })))
      .toMatch(/엑셀 파일을 열 수 없습니다/);
    expect(uploadErrorMessage(apiError(400, { error: "UNKNOWN_CARD_FORMAT" })))
      .toMatch(/지원하지 않는 명세서 형식입니다/);
    expect(uploadErrorMessage(apiError(400, { error: "HEADER_NOT_FOUND" })))
      .toMatch(/거래 내역을 찾지 못했습니다/);
  });

  it("falls back to a generic message for unknown/network errors", () => {
    expect(uploadErrorMessage(new Error("Network Error"))).toBe("업로드에 실패했습니다. 잠시 후 다시 시도해주세요.");
    expect(uploadErrorMessage(apiError(500, "boom"))).toBe("업로드에 실패했습니다. 잠시 후 다시 시도해주세요.");
  });
});
