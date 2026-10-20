# W8 월 마감 결산 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 닫힌 달 결산(요약·예산 성적표·전월 대비 변화·Top 5·자동 인사이트)을 `GET /reports/monthly`와 `/report` 페이지로 제공한다.

**Architecture:** `app/reports/` 모듈이 `dashboard.service`(summary, by_category), `budgets.service.status`, `insights.service.generate`를 조합해 한 응답으로 낸다. 순수 계산(기본 월, Top 5, 증감)은 함수로 분리해 단위 테스트. 웹은 TanStack Query 훅 하나 + 페이지.

**Tech Stack:** FastAPI, asyncpg raw SQL, pytest; React 18, TanStack Query v5, vitest.

**Spec:** `docs/superpowers/specs/2026-10-20-monthly-report-design.md`

## Global Constraints

- DB는 `async with acquire() as conn`, 서비스 함수는 `conn`을 인자로. `Depends`는 인증만. 에러는 라우터에서 `HTTPException`(`INVALID_MONTH_FORMAT`).
- 지출 수치는 dashboard 서비스 재사용(직접 SQL 재작성 금지).
- "이번 달"은 `app.budgets.service.today_kst()` (테스트에서 monkeypatch).
- 인사이트 생성 실패(`BudgetExceededError`, `InsightError`) → `insight: null`, 응답 200 유지.
- 웹 금액 `formatWon`, 카테고리 `categoryLabel`, 퍼센트 `Math.round`.
- 커밋: Conventional Commits + 스코프, 끝에 `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
- 실행: API `cd apps/api && uv run pytest -q && uv run ruff check .`; 웹 `cd apps/web && npx vitest run && npx tsc --noEmit -p .`.

---

### Task 1: API — `app/reports/`

**Files:** Create `apps/api/app/reports/{__init__,schemas,service,routes}.py`, `apps/api/tests/reports/{__init__,test_service,test_routes}.py`; Modify `apps/api/app/main.py`.

**Interfaces (Produces):**
- `service.default_month(months: list[str], current: str) -> str | None`
- `service.top_categories(rows: list[dict], n: int = 5) -> list[dict]` (`{category, amount, share}`)
- `service.category_changes(cur: list[dict], prev: list[dict], n: int = 3) -> dict` (`{increased, decreased}`, 각 `{category, amount, prev_amount, diff}`)
- `service.monthly_report(conn, user_id, month: str | None, today: date) -> dict`
- HTTP `GET /reports/monthly?month=` → `MonthlyReportResponse`

- [ ] **Step 1: 순수 함수 실패 테스트** — `tests/reports/test_service.py`:
```python
from decimal import Decimal

from app.reports.service import category_changes, default_month, top_categories


def test_default_month_prefers_last_closed_month():
    assert default_month(["2026-10", "2026-09", "2026-08"], "2026-10") == "2026-09"
    assert default_month(["2026-10"], "2026-10") == "2026-10"
    assert default_month([], "2026-10") is None


def test_top_categories_share_and_limit():
    rows = [{"category": f"c{i}", "amount": Decimal(100 - i * 10), "count": 1} for i in range(7)]
    out = top_categories(rows)
    assert [r["category"] for r in out] == ["c0", "c1", "c2", "c3", "c4"]
    assert out[0]["share"] == round(100 / 490, 4)
    assert top_categories([]) == []


def test_category_changes_sorted_and_limited():
    cur = [{"category": "coffee", "amount": Decimal(62000)},
           {"category": "shopping", "amount": Decimal(10000)},
           {"category": "lunch", "amount": Decimal(50000)},
           {"category": "health", "amount": Decimal(1000)},
           {"category": "etc", "amount": Decimal(9000)}]
    prev = [{"category": "coffee", "amount": Decimal(30000)},
            {"category": "shopping", "amount": Decimal(55000)},
            {"category": "dinner", "amount": Decimal(40000)},
            {"category": "etc", "amount": Decimal(1000)}]
    out = category_changes(cur, prev)
    assert [(c["category"], c["diff"]) for c in out["increased"]] == [
        ("lunch", Decimal(50000)), ("coffee", Decimal(32000)), ("etc", Decimal(8000))]
    assert [(c["category"], c["diff"]) for c in out["decreased"]] == [
        ("shopping", Decimal(-45000)), ("dinner", Decimal(-40000))]
    assert out["decreased"][1]["amount"] == Decimal(0)  # 이번 달엔 없던 카테고리
```
Run → FAIL (module 없음).

- [ ] **Step 2: service 구현** — `app/reports/service.py`:
```python
"""월 결산 — dashboard·budgets·insights 서비스를 조합한 닫힌 달 돌아보기."""
from datetime import date
from decimal import Decimal
from uuid import UUID

import asyncpg

from app.budgets import service as budgets
from app.dashboard import service as dash
from app.insights import service as insights
from app.insights.llm import InsightError


async def available_months(conn: asyncpg.Connection, user_id: UUID) -> list[str]:
    rows = await conn.fetch(
        "SELECT DISTINCT to_char(txn_date, 'YYYY-MM') AS m FROM transactions "
        "WHERE user_id = $1 ORDER BY m DESC",
        user_id,
    )
    return [r["m"] for r in rows]


def default_month(months: list[str], current: str) -> str | None:
    """이번 달 이전 중 최근 달(명세서는 월이 지난 뒤 올라온다). 없으면 최근 달."""
    closed = [m for m in months if m < current]
    if closed:
        return closed[0]
    return months[0] if months else None


def top_categories(rows: list[dict], n: int = 5) -> list[dict]:
    total = sum((r["amount"] for r in rows), Decimal(0))
    return [
        {
            "category": r["category"],
            "amount": r["amount"],
            "share": round(float(r["amount"] / total), 4) if total > 0 else 0.0,
        }
        for r in rows[:n]
    ]


def category_changes(cur: list[dict], prev: list[dict], n: int = 3) -> dict:
    cur_map = {r["category"]: r["amount"] for r in cur}
    prev_map = {r["category"]: r["amount"] for r in prev}
    changes = []
    for cat in cur_map.keys() | prev_map.keys():
        amount = cur_map.get(cat, Decimal(0))
        prev_amount = prev_map.get(cat, Decimal(0))
        changes.append({"category": cat, "amount": amount, "prev_amount": prev_amount,
                        "diff": amount - prev_amount})
    increased = sorted((c for c in changes if c["diff"] > 0), key=lambda c: -c["diff"])
    decreased = sorted((c for c in changes if c["diff"] < 0), key=lambda c: c["diff"])
    return {"increased": increased[:n], "decreased": decreased[:n]}


async def monthly_report(
    conn: asyncpg.Connection, user_id: UUID, month: str | None, today: date
) -> dict:
    if month is not None:
        dash.validate_month(month)
    months = await available_months(conn, user_id)
    month = month or default_month(months, today.strftime("%Y-%m"))
    if month is None:
        return {"month": None, "available_months": [], "summary": None,
                "top_categories": [], "category_changes": {"increased": [], "decreased": []},
                "budget": None, "insight": None}

    s = await dash.summary(conn, user_id, month)
    cur = await dash.by_category(conn, user_id, month)
    prev = await dash.by_category(conn, user_id, s["prev_month"])

    status = await budgets.status(conn, user_id, month, today)
    items = status["items"]
    budget = None
    if items:
        over = sum(1 for i in items if i["level"] == "over")
        budget = {"total": len(items), "kept": len(items) - over, "over": over, "items": items}

    try:
        ins = await insights.generate(conn, user_id, month, force=False)
        insight = {"summary": ins["summary"], "highlights": ins["highlights"],
                   "generated_at": ins["generated_at"]}
    except (insights.BudgetExceededError, InsightError):
        insight = None

    return {
        "month": month,
        "available_months": months,
        "summary": {
            "spent": s["total_amount"], "income": s["income_total"],
            "net_savings": s["net_savings"], "savings_rate": s["savings_rate"],
            "transaction_count": s["transaction_count"], "prev_month": s["prev_month"],
            "prev_spent": s["prev_month_total"], "spent_diff_pct": s["prev_month_diff_pct"],
        },
        "top_categories": top_categories(cur),
        "category_changes": category_changes(cur, prev),
        "budget": budget,
        "insight": insight,
    }
```
Run Step 1 tests → PASS.

- [ ] **Step 3: 라우트 실패 테스트** — `tests/reports/test_routes.py`: 오늘 2026-10-20 고정(monkeypatch `budgets.service.today_kst`), 시나리오 — (a) 거래 없음 → `month` null; (b) 9·10월 거래 → 기본 2026-09, `available_months == ["2026-10","2026-09"]`; (c) summary.spent == `/dashboard/summary` total_amount, transfer 제외; (d) category_changes increased/decreased; (e) 예산(_total 9월 소급, coffee 초과) → budget total/kept/over; 예산 없으면 null; (f) insight 생성 후 두 번째 호출 generated_at 동일; (g) `insights.service.generate`를 `BudgetExceededError` 던지게 monkeypatch → 200 + insight null; (h) 사용자 격리; (i) `month=2026-1` 400, 미인증 401.

- [ ] **Step 4: schemas·routes·main** — `schemas.py`(ReportSummaryOut, TopCategoryOut, CategoryChangeOut, CategoryChangesOut, ReportBudgetOut(items: list[BudgetItemOut]), ReportInsightOut, MonthlyReportResponse — Decimal/float/Optional), `routes.py`:
```python
@router.get("/monthly", response_model=MonthlyReportResponse)
async def monthly_report(month: str | None = None, user_id: UUID = Depends(current_user_id)):
    try:
        async with acquire() as conn:
            data = await service.monthly_report(conn, user_id, month, budgets.today_kst())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="INVALID_MONTH_FORMAT") from exc
    return MonthlyReportResponse(**data)
```
`main.py`에 `reports_router` 등록. Run 전체 pytest + ruff → PASS.

- [ ] **Step 5: Commit** `feat(api): GET /reports/monthly — closed-month report (summary, budget scorecard, changes, auto insight)`

### Task 2: Web — `/report` 페이지 + Nav + 진입 링크 + 무효화

**Files:** Modify `lib/api.ts`(타입 + `fetchMonthlyReport(month?)`), `lib/queries.ts`(`qk.report`, `useMonthlyReport`, 무효화에 `["report"]`), `components/Nav.tsx`(결산 링크, 모바일 로고 숨김), `App.tsx`(lazy 라우트), `routes/dashboard.tsx`(`이 달 결산 보기 →`); Create `routes/report.tsx`, `routes/report.test.tsx`.

**Interfaces:** Consumes Task 1 HTTP. Produces `MonthlyReport` 타입, `useMonthlyReport(month: string | undefined)` (`month` undefined면 서버 기본 월).

- [ ] **Step 1: 실패 테스트** `routes/report.test.tsx` — api mock: (a) 전체 섹션 렌더(제목 "2026년 9월 결산", "지출 ₩1,282,530", "전월 대비 +17%", "5개 중 3개 지켰어요", "커피 +₩32,000", "주거 ₩800,000 · 62%", 인사이트 요약); (b) 예산 null → "예산을 정하면 결산에 성적표가 나와요"; 인사이트 null → "인사이트를 만들지 못했어요"; (c) month null → "아직 거래가 없습니다"; (d) `/report?month=2026-08` → `fetchMonthlyReport("2026-08")`.
- [ ] **Step 2: 구현** — 페이지, Nav(`<span className="hidden sm:inline ...">spendLens</span>` + `결산` 링크), App 라우트, 대시보드 링크, 무효화(업로드·삭제·카테고리·필수·일괄 변경·예산 저장에 `["report"]`).
- [ ] **Step 3: 전체 vitest + tsc → PASS. Commit** `feat(web): /report monthly closing page + nav + dashboard link`

### Task 3: 문서·배포·운영 검증

- [ ] FEATURES.md(3.9 월 결산, API 표, 라우트 표) 커밋 `docs(infra): W8 monthly report in FEATURES.md`
- [ ] PR → CI → squash 머지 → Deploy API 대기
- [ ] 운영: QA 계정 `/report` 기본 월(2026-05) 렌더, 월 변경, 인사이트 자동 생성, 375px Nav 넘침 없음(SW 캐시 비운 뒤, `$B chain`으로 한 번에)
