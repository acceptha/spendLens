# W8 — 월 마감 결산 페이지 설계

- 작성일: 2026-10-20
- 상태: 확정 (사용자 승인)
- 범위: 백엔드 `app/reports/` 신규 모듈(`GET /reports/monthly`), 웹 `/report` 결산 페이지 + Nav + 대시보드 진입 링크

## 1. 목표

닫힌 달을 한 화면에서 돌아본다: 지출·수입·저축률과 전월 대비, 예산 성적표, 전월보다 늘거나 준 카테고리, 많이 쓴 카테고리, 그 달 인사이트(자동 생성). 대시보드는 "지금 현황", 결산은 "닫힌 달 돌아보기".

### 결정 사항 (사용자 확정)

| 항목 | 결정 |
|---|---|
| 위치 | 새 `결산` 페이지(`/report`) |
| 인사이트 | 결산 조회 시 없으면 자동 생성(기존 캐시 재사용, 무효화 트리거와 연동) |
| 구조 | 결산 전용 API 1개가 기존 서비스(dashboard/budgets/insights)를 조합 (접근 A) |
| 기본 월 | 이번 달(KST) **이전** 중 거래가 있는 최근 달, 없으면 거래 있는 최근 달 |

### 비목표
결산 스냅샷 저장, PDF/공유, 이메일 발송, 연간 결산.

## 2. API — `GET /reports/monthly?month=YYYY-MM`

모듈 `app/reports/` (`routes.py`, `schemas.py`, `service.py`). 인증 필요. `month` 생략 가능.

- 형식 오류 → 400 `INVALID_MONTH_FORMAT`.
- 거래가 하나도 없으면 200 `{"month": null, "available_months": [], ...나머지 null/빈 값}`.
- `available_months`: 거래가 있는 달(내림차순, 이번 달 포함 — 사용자가 진행 중인 달도 볼 수 있게).
- 기본 월: `available_months` 중 `< 이번 달(KST)` 인 첫 값, 없으면 `available_months[0]`.

응답 `MonthlyReportResponse`:

| 필드 | 내용 |
|---|---|
| `month` | 결산 월 또는 null |
| `available_months` | list[str] |
| `summary` | `{spent, income, net_savings, savings_rate, transaction_count, prev_month, prev_spent, spent_diff_pct}` — `dashboard.service.summary` 값 매핑 |
| `top_categories` | `dashboard.service.by_category` 상위 5, 각 `{category, amount, share}` (share = amount / 그 달 지출 합, 소수 4자리; 합이 0이면 0) |
| `category_changes` | `{increased: [...], decreased: [...]}` — 이번 달·전월 by_category를 카테고리 합집합으로 비교, `diff = amount - prev_amount`. increased: diff > 0 내림차순 상위 3, decreased: diff < 0 오름차순(가장 많이 준 것부터) 상위 3. 각 `{category, amount, prev_amount, diff}` |
| `budget` | `budgets.service.status` 결과가 항목 1개 이상이면 `{total, kept, over, items}` (`kept` = level != "over" 개수, `over` = "over" 개수), 없으면 null |
| `insight` | `insights.service.generate(force=False)` 결과 `{summary, highlights, generated_at}`. `BudgetExceededError`·`InsightError` 발생 시 null (나머지 결산은 정상 응답) |

- 지출 규칙은 dashboard와 동일(재사용으로 보장).
- GET이 인사이트 캐시를 채우는 부수효과가 있다 — 멱등(같은 데이터면 같은 결과), 거래 변경 시 기존 트리거(migration 0006)가 캐시를 지운다.

## 3. 웹 — `/report`

- Nav: `거래내역 · 대시보드 · 예산 · 결산`. 375px에서 넘치지 않도록 **모바일에서 로고 텍스트 숨김**(`hidden sm:inline`).
- 대시보드 월 선택 옆 링크 `이 달 결산 보기 →` (`/report?month=`).
- 페이지 구성: 제목 `YYYY년 M월 결산` + 월 선택(`available_months`), 요약 카드(지출·전월 대비·수입·저축률), 예산 성적표(`N개 중 K개 지켰어요` + 초과 항목 `BudgetBar`), 늘어난/줄어든 지출(각 최대 3), 많이 쓴 카테고리 Top 5(금액·비중), 이달의 인사이트.
- 빈 상태: 예산 없음 → "예산을 정하면 결산에 성적표가 나와요 → 예산 설정"; 인사이트 null → "인사이트를 만들지 못했어요"; 거래 없음 → "아직 거래가 없습니다. 명세서를 업로드하세요".
- 데이터: `fetchMonthlyReport(month?)`, `qk.report(month)`, `useMonthlyReport(month)`. 거래 변경 mutation(업로드·삭제·카테고리·필수·일괄 변경)과 예산 저장 시 `["report"]` 무효화.
- 금액 `formatWon`, 카테고리 `categoryLabel`, 퍼센트 정수 반올림.

## 4. 테스트

- API: 기본 월(이번 달 제외, 이번 달만 있으면 그 달, 거래 없음 null), summary가 dashboard summary와 일치, top_categories 5개·share, category_changes 증가/감소 정렬·3개 제한·전월에만 있는 카테고리 처리, budget kept/over·예산 없으면 null, insight 자동 생성 후 캐시 재사용(generated_at 동일), insight 생성 실패 시 null + 200, 사용자 격리, 400/401. 오늘 날짜는 `budgets.service.today_kst` monkeypatch.
- 웹: 섹션 렌더(요약·성적표·변화·Top5·인사이트), 빈 상태 3종, 월 변경 시 해당 월로 재조회, Nav 375px 수동 확인.
