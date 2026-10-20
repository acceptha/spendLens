# W7 월 예산 목표 + 초과 경고 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 총 지출·카테고리별 월 예산을 설정하고, 진행률·월말 예상·초과 경고를 `/budget` 탭과 대시보드 카드에서 보여준다.

**Architecture:** 백엔드는 `app/budgets/` 도메인 모듈(routes/schemas/service) + `budgets` 테이블(적용 시작 월 `effective_from` 행). 사용액은 저장하지 않고 조회 시 dashboard와 같은 규칙으로 집계. 웹은 TanStack Query 훅 + `/budget` 페이지 + 대시보드 요약 카드.

**Tech Stack:** FastAPI, asyncpg raw SQL, Alembic raw SQL, pytest; React 18, TanStack Query v5, Tailwind, vitest.

**Spec:** `docs/superpowers/specs/2026-10-20-budget-goals-design.md`

## Global Constraints

- DB: asyncpg raw SQL만, `async with acquire() as conn`. ORM 금지. 마이그레이션은 Alembic raw SQL(`op.execute`).
- DI: `Depends()`는 인증(`current_user_id`)에만.
- 에러: 라우터에서 `HTTPException` 직접 raise, 코드는 `UPPER_SNAKE_CASE` (`INVALID_MONTH_FORMAT`, `INVALID_CATEGORY`).
- 스키마 네이밍: `{도메인}{Request|Response}` / `{도메인}{In|Out}`.
- "이번 달/오늘"은 `Asia/Seoul`.
- 총액 키는 `_total`. 예산 불가 카테고리: `income`, `transfer`, `savings`.
- level: `over` = spent ≥ budget, `warn` = spent ≥ 0.8·budget 또는 projected > budget, 그 외 `ok`.
- projected = 이번 달이고 경과일 ≥ 1일 때만 `round(spent / days_elapsed * days_in_month)`, 아니면 null.
- 웹 금액 표기는 `formatWon`, 카테고리 표시는 `categoryLabel`.
- 커밋: Conventional Commits + 스코프, 본문 끝에 `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
- 테스트 실행: API `cd apps/api && uv run pytest -q`, lint `uv run ruff check .`; 웹 `cd apps/web && npx vitest run`, `npx tsc --noEmit -p .`.
- 로컬 테스트 DB는 자동 마이그레이션되지 않는다: 마이그레이션 추가 후 `cd apps/api && export $(grep DATABASE_URL tests/.env.test) && uv run alembic upgrade head`.

---

### Task 1: API — budgets 테이블 + `app/budgets/` 모듈

**Files:**
- Create: `apps/api/migrations/versions/0007_add_budgets.py`
- Create: `apps/api/app/budgets/__init__.py` (빈 파일)
- Create: `apps/api/app/budgets/service.py`
- Create: `apps/api/app/budgets/schemas.py`
- Create: `apps/api/app/budgets/routes.py`
- Modify: `apps/api/app/main.py` (router 등록)
- Modify: `apps/api/tests/conftest.py` (TRUNCATE에 `budgets`)
- Test: `apps/api/tests/budgets/__init__.py`, `tests/budgets/test_service.py`, `tests/budgets/test_routes.py`

**Interfaces:**
- Produces (HTTP): `GET /budgets/status?month=YYYY-MM` → `{month, is_current, days_elapsed, days_in_month, items: [{category, budget, spent, ratio, projected, level}]}`; `PUT /budgets` body `{category: str, amount: int|null}` → 204.
- Produces (Python): `service.TOTAL = "_total"`, `service.ALLOWED_CATEGORIES: tuple[str, ...]`, `service.today_kst() -> date`, `service.current_month() -> str`, `service.month_days(month, today) -> tuple[int, int, bool]`, `service.project(spent, days_elapsed, days_in_month, is_current) -> Decimal | None`, `service.budget_level(spent, budget, projected) -> str`, `service.status(conn, user_id, month, today) -> dict`, `service.set_budget(conn, user_id, category, amount, month) -> None`.

- [ ] **Step 1: 마이그레이션 작성**

`apps/api/migrations/versions/0007_add_budgets.py`:
```python
"""add budgets (monthly recurring, effective-dated)

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-20
"""
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE budgets (
          user_id        UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          category       TEXT NOT NULL,
          amount         NUMERIC(14,0) NULL,
          effective_from TEXT NOT NULL,
          updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
          PRIMARY KEY (user_id, category, effective_from)
        );
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS budgets;")
```
`tests/conftest.py` TRUNCATE 목록 첫 줄을 `TRUNCATE budgets, monthly_insights, llm_usage_log, transactions,` 로 수정.
테스트 DB에 적용: `export $(grep DATABASE_URL tests/.env.test) && uv run alembic upgrade head`.

- [ ] **Step 2: 순수 함수 실패 테스트**

`tests/budgets/__init__.py` 빈 파일. `tests/budgets/test_service.py`:
```python
from datetime import date
from decimal import Decimal

from app.budgets.service import ALLOWED_CATEGORIES, budget_level, month_days, project


def test_level_boundaries():
    b = Decimal("100000")
    assert budget_level(Decimal("79900"), b, None) == "ok"
    assert budget_level(Decimal("80000"), b, None) == "warn"
    assert budget_level(Decimal("100000"), b, None) == "over"


def test_level_warns_when_projection_exceeds_budget():
    assert budget_level(Decimal("30000"), Decimal("100000"), Decimal("120000")) == "warn"
    assert budget_level(Decimal("30000"), Decimal("100000"), Decimal("90000")) == "ok"


def test_month_days_current_past_future():
    today = date(2026, 10, 20)
    assert month_days("2026-10", today) == (20, 31, True)
    assert month_days("2026-09", today) == (30, 30, False)
    assert month_days("2026-11", today) == (0, 30, False)
    assert month_days("2024-02", today) == (29, 29, False)


def test_project_only_for_current_month():
    assert project(Decimal("100000"), 10, 30, True) == Decimal("300000")
    assert project(Decimal("100000"), 30, 30, False) is None
    assert project(Decimal("0"), 0, 30, True) is None


def test_project_rounds_half_up():
    assert project(Decimal("10"), 3, 31, True) == Decimal("103")  # 103.33…


def test_allowed_categories_exclude_non_spending_and_income():
    assert "_total" in ALLOWED_CATEGORIES
    assert "coffee" in ALLOWED_CATEGORIES
    for c in ("income", "transfer", "savings"):
        assert c not in ALLOWED_CATEGORIES
```
Run: `uv run pytest -q tests/budgets/test_service.py` → FAIL (ModuleNotFoundError: app.budgets).

- [ ] **Step 3: service 구현**

`apps/api/app/budgets/service.py`:
```python
"""월 예산 — 적용 시작 월(effective_from) 행 + 조회 시 지출 집계.

월 M의 예산 = 카테고리별 effective_from <= M 인 가장 최근 행(amount NULL이면 해제).
지출 집계는 dashboard와 같은 규칙: 출금(amount > 0), effective_category 기준,
NON_SPENDING_CATEGORIES 제외. "이번 달/오늘"은 Asia/Seoul.
"""
import calendar
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

import asyncpg

from app.categorization.essential import NON_SPENDING_CATEGORIES
from app.categorization.rulebook import CATEGORIES
from app.dashboard.service import validate_month

TOTAL = "_total"
ALLOWED_CATEGORIES: tuple[str, ...] = (TOTAL,) + tuple(
    c for c in CATEGORIES if c not in NON_SPENDING_CATEGORIES and c != "income"
)
_KST = ZoneInfo("Asia/Seoul")
_WARN_RATIO = Decimal("0.8")


def today_kst() -> date:
    return datetime.now(_KST).date()


def current_month() -> str:
    return today_kst().strftime("%Y-%m")


def month_days(month: str, today: date) -> tuple[int, int, bool]:
    """(경과일, 월 일수, 이번 달 여부). 지난달은 경과일=월 일수, 미래 달은 0."""
    y, m = int(month[:4]), int(month[5:7])
    days_in_month = calendar.monthrange(y, m)[1]
    cur = today.strftime("%Y-%m")
    if month == cur:
        return today.day, days_in_month, True
    if month < cur:
        return days_in_month, days_in_month, False
    return 0, days_in_month, False


def project(
    spent: Decimal, days_elapsed: int, days_in_month: int, is_current: bool
) -> Decimal | None:
    if not is_current or days_elapsed < 1:
        return None
    return (spent / days_elapsed * days_in_month).quantize(Decimal("1"), ROUND_HALF_UP)


def budget_level(spent: Decimal, budget: Decimal, projected: Decimal | None) -> str:
    if spent >= budget:
        return "over"
    if spent >= budget * _WARN_RATIO or (projected is not None and projected > budget):
        return "warn"
    return "ok"


async def _budgets_for_month(
    conn: asyncpg.Connection, user_id: UUID, month: str
) -> dict[str, Decimal]:
    rows = await conn.fetch(
        """
        SELECT DISTINCT ON (category) category, amount
        FROM budgets
        WHERE user_id = $1 AND effective_from <= $2
        ORDER BY category, effective_from DESC
        """,
        user_id, month,
    )
    return {r["category"]: r["amount"] for r in rows if r["amount"] is not None}


async def _spent_by_category(
    conn: asyncpg.Connection, user_id: UUID, month: str
) -> dict[str, Decimal]:
    rows = await conn.fetch(
        """
        SELECT COALESCE(user_category_override, category) AS cat,
               COALESCE(SUM(amount), 0)::numeric AS spent
        FROM transactions
        WHERE user_id = $1 AND to_char(txn_date, 'YYYY-MM') = $2 AND amount > 0
          AND NOT (COALESCE(user_category_override, category) = ANY($3::text[]))
        GROUP BY 1
        """,
        user_id, month, list(NON_SPENDING_CATEGORIES),
    )
    return {r["cat"]: r["spent"] for r in rows}


async def status(conn: asyncpg.Connection, user_id: UUID, month: str, today: date) -> dict:
    validate_month(month)
    budgets = await _budgets_for_month(conn, user_id, month)
    spent_map = await _spent_by_category(conn, user_id, month)
    days_elapsed, days_in_month, is_current = month_days(month, today)

    items = []
    for category, budget in budgets.items():
        spent = (
            sum(spent_map.values(), Decimal(0)) if category == TOTAL
            else spent_map.get(category, Decimal(0))
        )
        projected = project(spent, days_elapsed, days_in_month, is_current)
        items.append({
            "category": category,
            "budget": budget,
            "spent": spent,
            "ratio": round(float(spent / budget), 4),
            "projected": projected,
            "level": budget_level(spent, budget, projected),
        })
    items.sort(key=lambda i: (i["category"] != TOTAL, -i["ratio"]))
    return {
        "month": month,
        "is_current": is_current,
        "days_elapsed": days_elapsed,
        "days_in_month": days_in_month,
        "items": items,
    }


async def set_budget(
    conn: asyncpg.Connection, user_id: UUID, category: str, amount: int | None, month: str
) -> None:
    """이번 달(month)부터 적용. 같은 달 재저장은 덮어쓰기, amount None = 해제."""
    await conn.execute(
        """
        INSERT INTO budgets (user_id, category, amount, effective_from)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (user_id, category, effective_from)
        DO UPDATE SET amount = EXCLUDED.amount, updated_at = now()
        """,
        user_id, category, amount, month,
    )
```
Run: `uv run pytest -q tests/budgets/test_service.py` → PASS (6).

- [ ] **Step 4: 라우트 실패 테스트**

`tests/budgets/test_routes.py`:
```python
import datetime
from uuid import uuid4

import httpx
import pytest
from httpx import ASGITransport

from app.budgets import service
from app.main import app


@pytest.fixture
def today(monkeypatch):
    """오늘을 2026-10-20(KST)로 고정. current_month()도 이 값을 따른다."""
    holder = {"d": datetime.date(2026, 10, 20)}
    monkeypatch.setattr(service, "today_kst", lambda: holder["d"])
    return holder


async def _client():
    return httpx.AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    )


async def _signup(ac):
    email = f"_bud-{uuid4()}@example.com"
    r = await ac.post("/auth/signup", json={"email": email, "password": "abcd1234"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}, email


async def _txn(pool, email, d, amount, category="etc", override=None):
    async with pool.acquire() as conn:
        uid = await conn.fetchval("SELECT id FROM users WHERE email=$1", email)
        await conn.execute(
            "INSERT INTO transactions (user_id, source_type, txn_date, amount, merchant_raw, "
            "category, user_category_override, dedup_hash, raw_row) "
            "VALUES ($1,'test',$2,$3,'M',$4,$5,$6,'{}'::jsonb)",
            uid, datetime.date.fromisoformat(d), amount, category, override, str(uuid4()))


async def test_status_empty_without_budgets(test_db_pool, today):
    async with await _client() as ac:
        h, _ = await _signup(ac)
        r = await ac.get("/budgets/status?month=2026-10", headers=h)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["items"] == []
        assert (body["is_current"], body["days_elapsed"], body["days_in_month"]) == (True, 20, 31)


async def test_set_and_status_with_projection_and_levels(test_db_pool, today):
    async with await _client() as ac:
        h, email = await _signup(ac)
        await _txn(test_db_pool, email, "2026-10-05", 62000, "coffee")
        await _txn(test_db_pool, email, "2026-10-06", 10000, "shopping")
        await _txn(test_db_pool, email, "2026-10-07", 500000, "transfer")  # 지출 제외
        for cat, amt in (("_total", 300000), ("coffee", 50000), ("shopping", 100000)):
            assert (await ac.put("/budgets", headers=h,
                                 json={"category": cat, "amount": amt})).status_code == 204

        items = (await ac.get("/budgets/status?month=2026-10", headers=h)).json()["items"]
        by = {i["category"]: i for i in items}
        assert items[0]["category"] == "_total"
        assert float(by["_total"]["spent"]) == 72000
        assert float(by["_total"]["projected"]) == 111600  # 72000/20*31
        assert by["_total"]["level"] == "ok"
        assert by["coffee"]["level"] == "over"
        assert by["coffee"]["ratio"] == 1.24
        assert float(by["shopping"]["spent"]) == 10000
        assert [i["category"] for i in items] == ["_total", "coffee", "shopping"]


async def test_spent_matches_dashboard_rules(test_db_pool, today):
    async with await _client() as ac:
        h, email = await _signup(ac)
        await _txn(test_db_pool, email, "2026-10-01", 30000, "etc", override="coffee")
        await _txn(test_db_pool, email, "2026-10-02", 20000, "transfer", override="shopping")
        await _txn(test_db_pool, email, "2026-10-03", 40000, "savings")
        await _txn(test_db_pool, email, "2026-10-04", -100000, "income")
        await ac.put("/budgets", headers=h, json={"category": "_total", "amount": 100000})
        await ac.put("/budgets", headers=h, json={"category": "coffee", "amount": 100000})

        items = {i["category"]: i for i in
                 (await ac.get("/budgets/status?month=2026-10", headers=h)).json()["items"]}
        summary = (await ac.get("/dashboard/summary?month=2026-10", headers=h)).json()
        by_cat = {c["category"]: c for c in
                  (await ac.get("/dashboard/by-category?month=2026-10", headers=h)).json()}
        assert float(items["_total"]["spent"]) == float(summary["total_amount"]) == 50000
        assert float(items["coffee"]["spent"]) == float(by_cat["coffee"]["amount"]) == 30000


async def test_change_applies_from_this_month_and_keeps_past(test_db_pool, today):
    async with await _client() as ac:
        h, _ = await _signup(ac)
        today["d"] = datetime.date(2026, 9, 10)
        await ac.put("/budgets", headers=h, json={"category": "coffee", "amount": 50000})
        today["d"] = datetime.date(2026, 10, 20)
        await ac.put("/budgets", headers=h, json={"category": "coffee", "amount": 80000})
        await ac.put("/budgets", headers=h, json={"category": "coffee", "amount": 70000})

        sep = (await ac.get("/budgets/status?month=2026-09", headers=h)).json()
        octo = (await ac.get("/budgets/status?month=2026-10", headers=h)).json()
        assert float(sep["items"][0]["budget"]) == 50000
        assert sep["items"][0]["projected"] is None
        assert float(octo["items"][0]["budget"]) == 70000  # 같은 달 재저장 = 덮어쓰기


async def test_clear_budget_from_this_month_only(test_db_pool, today):
    async with await _client() as ac:
        h, _ = await _signup(ac)
        today["d"] = datetime.date(2026, 9, 10)
        await ac.put("/budgets", headers=h, json={"category": "coffee", "amount": 50000})
        today["d"] = datetime.date(2026, 10, 20)
        r = await ac.put("/budgets", headers=h, json={"category": "coffee", "amount": None})
        assert r.status_code == 204
        assert (await ac.get("/budgets/status?month=2026-10", headers=h)).json()["items"] == []
        assert len((await ac.get("/budgets/status?month=2026-09", headers=h)).json()["items"]) == 1


async def test_users_are_isolated(test_db_pool, today):
    async with await _client() as ac:
        h1, _ = await _signup(ac)
        h2, _ = await _signup(ac)
        await ac.put("/budgets", headers=h1, json={"category": "_total", "amount": 100000})
        assert (await ac.get("/budgets/status?month=2026-10", headers=h2)).json()["items"] == []


@pytest.mark.parametrize("category", ["income", "transfer", "savings", "nope"])
async def test_invalid_category_400(test_db_pool, today, category):
    async with await _client() as ac:
        h, _ = await _signup(ac)
        r = await ac.put("/budgets", headers=h, json={"category": category, "amount": 1000})
        assert r.status_code == 400
        assert r.json()["detail"] == "INVALID_CATEGORY"


@pytest.mark.parametrize("amount", [0, -5, 10**12])
async def test_invalid_amount_422(test_db_pool, today, amount):
    async with await _client() as ac:
        h, _ = await _signup(ac)
        r = await ac.put("/budgets", headers=h, json={"category": "coffee", "amount": amount})
        assert r.status_code == 422


async def test_invalid_month_400_and_auth_required(test_db_pool, today):
    async with await _client() as ac:
        h, _ = await _signup(ac)
        r = await ac.get("/budgets/status?month=2026-1", headers=h)
        assert r.status_code == 400
        assert r.json()["detail"] == "INVALID_MONTH_FORMAT"
        assert (await ac.get("/budgets/status?month=2026-10")).status_code == 401
        assert (await ac.put("/budgets", json={"category": "coffee", "amount": 1})).status_code == 401
```
Run: `uv run pytest -q tests/budgets/test_routes.py` → FAIL (404, routes 없음).

- [ ] **Step 5: schemas + routes + main 등록**

`apps/api/app/budgets/schemas.py`:
```python
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class BudgetSetRequest(BaseModel):
    category: str
    # None = 이번 달부터 예산 해제
    amount: int | None = Field(..., ge=1, lt=10**12)


class BudgetItemOut(BaseModel):
    category: str
    budget: Decimal
    spent: Decimal
    ratio: float
    projected: Decimal | None
    level: Literal["ok", "warn", "over"]


class BudgetStatusResponse(BaseModel):
    month: str
    is_current: bool
    days_elapsed: int
    days_in_month: int
    items: list[BudgetItemOut]
```
`apps/api/app/budgets/routes.py`:
```python
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.auth.deps import current_user_id
from app.budgets import service
from app.budgets.schemas import BudgetSetRequest, BudgetStatusResponse
from app.db import acquire

router = APIRouter(prefix="/budgets", tags=["budgets"])


@router.get("/status", response_model=BudgetStatusResponse)
async def budget_status(
    month: str,
    user_id: UUID = Depends(current_user_id),  # noqa: B008
) -> BudgetStatusResponse:
    try:
        async with acquire() as conn:
            data = await service.status(conn, user_id, month, service.today_kst())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="INVALID_MONTH_FORMAT") from exc
    return BudgetStatusResponse(**data)


@router.put("", status_code=204)
async def set_budget(
    req: BudgetSetRequest,
    user_id: UUID = Depends(current_user_id),  # noqa: B008
) -> None:
    if req.category not in service.ALLOWED_CATEGORIES:
        raise HTTPException(status_code=400, detail="INVALID_CATEGORY")
    async with acquire() as conn:
        await service.set_budget(
            conn, user_id, req.category, req.amount, service.current_month()
        )
```
`apps/api/app/main.py`: import `from app.budgets.routes import router as budgets_router` (알파벳 순, `auth` 다음) 후 `app.include_router(budgets_router)` 를 `insights_router` 다음 줄에 추가.

- [ ] **Step 6: 전체 테스트 + lint**

Run: `uv run pytest -q` → 전부 PASS. `uv run ruff check .` → All checks passed.

- [ ] **Step 7: Commit**

```bash
git add apps/api
git commit -m "feat(api): monthly budgets (effective-dated) + status with projection/levels"
```

---

### Task 2: Web — 예산 API·훅 + `/budget` 페이지 + Nav

**Files:**
- Modify: `apps/web/src/lib/api.ts` (타입 + `fetchBudgetStatus`, `putBudget`)
- Modify: `apps/web/src/lib/queries.ts` (`qk.budget`, `useBudgetStatus`, `useSaveBudget`)
- Modify: `apps/web/src/lib/categories.ts` (`TOTAL_KEY`, `BUDGETABLE_CATEGORIES`, `budgetLabel`)
- Create: `apps/web/src/lib/month.ts` (`currentMonthKST`)
- Create: `apps/web/src/components/BudgetBar.tsx`
- Create: `apps/web/src/routes/budget.tsx`
- Modify: `apps/web/src/components/Nav.tsx`, `apps/web/src/App.tsx`
- Test: `components/BudgetBar.test.tsx`, `routes/budget.test.tsx`, `lib/month.test.ts`

**Interfaces:**
- Consumes: Task 1 HTTP API.
- Produces: `BudgetItem`, `BudgetStatus`, `BudgetLevel` 타입(api.ts); `fetchBudgetStatus(month: string): Promise<BudgetStatus>`; `putBudget(category: string, amount: number | null): Promise<void>`; `qk.budget(month) = ["budget", month]`; `useBudgetStatus(month: string | undefined)`; `useSaveBudget()` (mutate `{category, amount}`); `TOTAL_KEY = "_total"`; `budgetLabel(key): string`; `currentMonthKST(): string`; `<BudgetBar item={BudgetItem} />`.

- [ ] **Step 1: 실패 테스트 작성**

`lib/month.test.ts`:
```ts
import { describe, it, expect, vi, afterEach } from "vitest";
import { currentMonthKST } from "./month";

describe("currentMonthKST", () => {
  afterEach(() => vi.useRealTimers());
  it("uses Asia/Seoul (UTC 2026-09-30 16:00 = KST 10-01)", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-09-30T16:00:00Z"));
    expect(currentMonthKST()).toBe("2026-10");
  });
});
```
`components/BudgetBar.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { BudgetBar } from "./BudgetBar";
import type { BudgetItem } from "../lib/api";

const item = (o: Partial<BudgetItem>): BudgetItem => ({
  category: "coffee", budget: "50000", spent: "20000", ratio: 0.4,
  projected: null, level: "ok", ...o,
});

describe("BudgetBar", () => {
  it("shows label, amounts and percent", () => {
    render(<BudgetBar item={item({})} />);
    expect(screen.getByText("커피")).toBeInTheDocument();
    expect(screen.getByText("₩20,000 / ₩50,000")).toBeInTheDocument();
    expect(screen.getByText("40%")).toBeInTheDocument();
  });

  it("marks warn and over with text, not only color", () => {
    const { rerender } = render(<BudgetBar item={item({ level: "warn", ratio: 0.85 })} />);
    expect(screen.getByText("주의")).toBeInTheDocument();
    rerender(<BudgetBar item={item({ level: "over", ratio: 1.24, spent: "62000" })} />);
    expect(screen.getByText("초과")).toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "124");
  });

  it("shows month-end projection only when present", () => {
    const { rerender } = render(<BudgetBar item={item({ projected: "96100" })} />);
    expect(screen.getByText("이 속도면 월말 ₩96,100 예상")).toBeInTheDocument();
    rerender(<BudgetBar item={item({ projected: null })} />);
    expect(screen.queryByText(/월말/)).toBeNull();
  });

  it("labels the total budget", () => {
    render(<BudgetBar item={item({ category: "_total" })} />);
    expect(screen.getByText("총 지출")).toBeInTheDocument();
  });
});
```
`routes/budget.test.tsx`:
```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { renderWithClient } from "../test/renderWithClient";
import type { BudgetStatus } from "../lib/api";

const { fetchMonthsMock, fetchBudgetStatusMock, putBudgetMock } = vi.hoisted(() => ({
  fetchMonthsMock: vi.fn(), fetchBudgetStatusMock: vi.fn(), putBudgetMock: vi.fn(),
}));
vi.mock("../lib/api", () => ({
  fetchMonths: fetchMonthsMock,
  fetchBudgetStatus: fetchBudgetStatusMock,
  putBudget: putBudgetMock,
  api: { post: vi.fn() },
}));
vi.mock("../lib/month", () => ({ currentMonthKST: () => "2026-10" }));

import { BudgetPage } from "./budget";

const status = (o: Partial<BudgetStatus>): BudgetStatus => ({
  month: "2026-10", is_current: true, days_elapsed: 20, days_in_month: 31, items: [], ...o,
});
const coffee = {
  category: "coffee", budget: "50000", spent: "62000", ratio: 1.24,
  projected: "96100", level: "over" as const,
};

function setup(path = "/budget") {
  return renderWithClient(<MemoryRouter initialEntries={[path]}><BudgetPage /></MemoryRouter>);
}

describe("BudgetPage", () => {
  beforeEach(() => {
    fetchMonthsMock.mockReset().mockResolvedValue(["2026-09"]);
    fetchBudgetStatusMock.mockReset();
    putBudgetMock.mockReset().mockResolvedValue(undefined);
  });

  it("empty current month asks for a total budget first", async () => {
    fetchBudgetStatusMock.mockResolvedValue(status({}));
    setup();
    expect(await screen.findByText(/총 지출 한도부터 정해보세요/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("총 지출 예산"), { target: { value: "1500000" } });
    fireEvent.click(screen.getByRole("button", { name: "저장" }));
    await waitFor(() => expect(putBudgetMock).toHaveBeenCalledWith("_total", 1500000));
  });

  it("edits a category budget and clears it with an empty value", async () => {
    fetchBudgetStatusMock.mockResolvedValue(status({ items: [coffee] }));
    setup();
    fireEvent.click(await screen.findByRole("button", { name: "편집: 커피" }));
    const input = screen.getByLabelText("커피 예산");
    fireEvent.change(input, { target: { value: "70000" } });
    fireEvent.click(screen.getByRole("button", { name: "저장" }));
    await waitFor(() => expect(putBudgetMock).toHaveBeenCalledWith("coffee", 70000));

    fireEvent.click(await screen.findByRole("button", { name: "편집: 커피" }));
    fireEvent.change(screen.getByLabelText("커피 예산"), { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: "저장" }));
    await waitFor(() => expect(putBudgetMock).toHaveBeenLastCalledWith("coffee", null));
  });

  it("adds a budget for a category without one", async () => {
    fetchBudgetStatusMock.mockResolvedValue(status({ items: [coffee] }));
    setup();
    await screen.findByText("커피");
    fireEvent.change(screen.getByLabelText("예산 추가 카테고리"), { target: { value: "shopping" } });
    fireEvent.change(screen.getByLabelText("예산 추가 금액"), { target: { value: "300000" } });
    fireEvent.click(screen.getByRole("button", { name: "추가" }));
    await waitFor(() => expect(putBudgetMock).toHaveBeenCalledWith("shopping", 300000));
  });

  it("past month is read-only with a notice", async () => {
    fetchBudgetStatusMock.mockResolvedValue(
      status({ month: "2026-09", is_current: false, days_elapsed: 30, days_in_month: 30,
               items: [{ ...coffee, projected: null }] }));
    setup("/budget?month=2026-09");
    expect(await screen.findByText(/예산 변경은 이번 달부터 적용됩니다/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /편집/ })).toBeNull();
    expect(screen.queryByRole("button", { name: "추가" })).toBeNull();
    expect(fetchBudgetStatusMock).toHaveBeenCalledWith("2026-09");
  });
});
```
Run: `npx vitest run src/lib/month.test.ts src/components/BudgetBar.test.tsx src/routes/budget.test.tsx` → FAIL (모듈 없음).

- [ ] **Step 2: 라이브러리 코드**

`lib/month.ts`:
```ts
/** 이번 달(YYYY-MM), Asia/Seoul 기준 — 서버 예산 "이번 달"과 같은 기준. */
export function currentMonthKST(): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Seoul", year: "numeric", month: "2-digit",
  }).format(new Date());
}
```
`lib/categories.ts` 끝에 추가:
```ts
export const TOTAL_KEY = "_total";

/** 예산을 걸 수 있는 카테고리 — 지출 집계에서 빠지는 수입·이체·저축 제외 (서버와 동일). */
export const BUDGETABLE_CATEGORIES = Object.keys(CATEGORY_LABELS).filter(
  (k) => !["income", "transfer", "savings"].includes(k),
);

export function budgetLabel(key: string): string {
  return key === TOTAL_KEY ? "총 지출" : categoryLabel(key);
}
```
`lib/api.ts` 끝에 추가:
```ts
export type BudgetLevel = "ok" | "warn" | "over";
export type BudgetItem = {
  category: string;
  budget: string;
  spent: string;
  ratio: number;
  projected: string | null;
  level: BudgetLevel;
};
export type BudgetStatus = {
  month: string;
  is_current: boolean;
  days_elapsed: number;
  days_in_month: number;
  items: BudgetItem[];
};

export async function fetchBudgetStatus(month: string): Promise<BudgetStatus> {
  const { data } = await api.get<BudgetStatus>(`/budgets/status?month=${month}`);
  return data;
}
export async function putBudget(category: string, amount: number | null): Promise<void> {
  await api.put("/budgets", { category, amount });
}
```
`lib/queries.ts`: import 목록에 `fetchBudgetStatus, putBudget,` 추가. `qk`에 `budget: (month: string) => ["budget", month] as const,` 추가. 읽기 훅 영역에:
```ts
export function useBudgetStatus(month: string | undefined) {
  return useQuery({
    queryKey: qk.budget(month ?? ""),
    queryFn: () => fetchBudgetStatus(month!),
    enabled: !!month,
  });
}
```
mutation 영역에:
```ts
export function useSaveBudget() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ category, amount }: { category: string; amount: number | null }) =>
      putBudget(category, amount),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["budget"] });
    },
  });
}
```

- [ ] **Step 3: BudgetBar**

`components/BudgetBar.tsx`:
```tsx
import type { BudgetItem, BudgetLevel } from "../lib/api";
import { budgetLabel } from "../lib/categories";
import { formatWon } from "../lib/format";

const BAR: Record<BudgetLevel, string> = {
  ok: "bg-emerald-500",
  warn: "bg-amber-500",
  over: "bg-red-500",
};
const BADGE: Record<BudgetLevel, string | null> = { ok: null, warn: "주의", over: "초과" };

export function BudgetBar({ item }: { item: BudgetItem }) {
  const pct = Math.round(item.ratio * 100);
  const badge = BADGE[item.level];
  return (
    <div className="space-y-1">
      <div className="flex items-baseline justify-between gap-3 text-sm">
        <span className="flex items-center gap-2 min-w-0">
          <span className="text-zinc-100">{budgetLabel(item.category)}</span>
          {badge && (
            <span className={`text-xs px-1.5 rounded ${
              item.level === "over" ? "bg-red-900/60 text-red-200" : "bg-amber-900/60 text-amber-200"
            }`}>{badge}</span>
          )}
        </span>
        <span className="text-zinc-300 whitespace-nowrap">
          <span>{`${formatWon(item.spent)} / ${formatWon(item.budget)}`}</span>
          <span className="ml-2 text-zinc-400">{`${pct}%`}</span>
        </span>
      </div>
      <div
        role="progressbar"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`${budgetLabel(item.category)} 예산 사용률`}
        className="h-2 rounded bg-zinc-800 overflow-hidden"
      >
        <div className={`h-full ${BAR[item.level]}`} style={{ width: `${Math.min(pct, 100)}%` }} />
      </div>
      {item.projected !== null && (
        <p className="text-xs text-zinc-500">{`이 속도면 월말 ${formatWon(item.projected)} 예상`}</p>
      )}
    </div>
  );
}
```

- [ ] **Step 4: BudgetPage**

`routes/budget.tsx`:
```tsx
import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { BudgetBar } from "../components/BudgetBar";
import { BUDGETABLE_CATEGORIES, TOTAL_KEY, budgetLabel } from "../lib/categories";
import { currentMonthKST } from "../lib/month";
import { useBudgetStatus, useMonths, useSaveBudget } from "../lib/queries";

/** 숫자만 받는 금액 입력 폼. 빈 값 제출 = null(예산 해제). */
function AmountForm({ label, initial, onSubmit, onCancel, pending }: {
  label: string;
  initial?: string;
  onSubmit: (amount: number | null) => void;
  onCancel?: () => void;
  pending: boolean;
}) {
  const [value, setValue] = useState(initial ?? "");
  return (
    <form
      className="flex items-center gap-2"
      onSubmit={(e) => {
        e.preventDefault();
        const n = value.trim() === "" ? null : Number(value.replace(/[^0-9]/g, ""));
        onSubmit(n === null || Number.isNaN(n) || n <= 0 ? null : n);
      }}
    >
      <input
        aria-label={label}
        inputMode="numeric"
        placeholder="금액(원)"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        className="w-36 bg-zinc-900 border border-zinc-700 rounded px-2 py-1 text-sm"
      />
      <button disabled={pending} className="text-sm px-3 py-1 rounded bg-blue-600 disabled:opacity-50">
        저장
      </button>
      {onCancel && (
        <button type="button" onClick={onCancel} className="text-sm text-zinc-400 hover:text-white">
          취소
        </button>
      )}
    </form>
  );
}

export function BudgetPage() {
  const [params, setParams] = useSearchParams();
  const current = currentMonthKST();
  const month = params.get("month") ?? current;
  const monthsQuery = useMonths();
  const monthOptions = Array.from(new Set([current, ...(monthsQuery.data ?? [])]))
    .filter((m) => m <= current)
    .sort()
    .reverse();

  const statusQ = useBudgetStatus(month);
  const save = useSaveBudget();
  const [editing, setEditing] = useState<string | null>(null);
  const [addCategory, setAddCategory] = useState("");
  const [addAmount, setAddAmount] = useState("");

  const status = statusQ.data;
  const editable = status?.is_current ?? month === current;
  const items = status?.items ?? [];
  const unused = [TOTAL_KEY, ...BUDGETABLE_CATEGORIES].filter(
    (c) => !items.some((i) => i.category === c),
  );

  function submit(category: string, amount: number | null) {
    save.mutate({ category, amount }, { onSuccess: () => setEditing(null) });
  }

  return (
    <div className="max-w-3xl mx-auto p-4 sm:p-8 space-y-4">
      <div className="flex items-center gap-3">
        <h2 className="text-2xl">예산</h2>
        <select
          value={month}
          onChange={(e) => setParams({ month: e.target.value })}
          className="bg-zinc-900 border border-zinc-700 rounded px-2 py-1 text-sm"
          aria-label="월 선택"
        >
          {monthOptions.map((m) => <option key={m} value={m}>{m}</option>)}
        </select>
      </div>

      {!editable && (
        <p className="text-sm text-zinc-400">지난 달 기록입니다. 예산 변경은 이번 달부터 적용됩니다.</p>
      )}
      {statusQ.isError && (
        <div role="alert" className="bg-red-900/30 border border-red-700 text-red-200 text-sm rounded p-3">
          예산을 불러오는 중 오류가 발생했습니다.
        </div>
      )}
      {save.isError && (
        <p role="alert" className="text-sm text-red-400">저장에 실패했습니다. 잠시 후 다시 시도해주세요.</p>
      )}

      {statusQ.isLoading ? (
        <p className="text-zinc-400 text-sm">로딩…</p>
      ) : items.length === 0 && editable ? (
        <div className="border border-zinc-800 rounded p-4 space-y-3">
          <p className="text-zinc-300">한 달 총 지출 한도부터 정해보세요.</p>
          <AmountForm label="총 지출 예산" pending={save.isPending}
                      onSubmit={(a) => submit(TOTAL_KEY, a)} />
        </div>
      ) : items.length === 0 ? (
        <p className="text-zinc-400 text-sm">이 달에는 설정된 예산이 없습니다.</p>
      ) : (
        <ul className="space-y-3">
          {items.map((item) => (
            <li key={item.category} className="border border-zinc-800 rounded p-4 space-y-2">
              <BudgetBar item={item} />
              {editable && (editing === item.category ? (
                <AmountForm
                  label={`${budgetLabel(item.category)} 예산`}
                  initial={String(Number(item.budget))}
                  pending={save.isPending}
                  onSubmit={(a) => submit(item.category, a)}
                  onCancel={() => setEditing(null)}
                />
              ) : (
                <button
                  onClick={() => setEditing(item.category)}
                  className="text-xs text-zinc-400 hover:text-white"
                  aria-label={`편집: ${budgetLabel(item.category)}`}
                >
                  편집
                </button>
              ))}
            </li>
          ))}
        </ul>
      )}

      {editable && items.length > 0 && unused.length > 0 && (
        <form
          className="flex flex-wrap items-center gap-2 border border-dashed border-zinc-700 rounded p-3"
          onSubmit={(e) => {
            e.preventDefault();
            const n = Number(addAmount.replace(/[^0-9]/g, ""));
            if (!addCategory || !n) return;
            save.mutate({ category: addCategory, amount: n }, {
              onSuccess: () => { setAddCategory(""); setAddAmount(""); },
            });
          }}
        >
          <span className="text-sm text-zinc-400">+ 예산 추가</span>
          <select
            aria-label="예산 추가 카테고리"
            value={addCategory}
            onChange={(e) => setAddCategory(e.target.value)}
            className="bg-zinc-900 border border-zinc-700 rounded px-2 py-1 text-sm"
          >
            <option value="">카테고리 선택</option>
            {unused.map((c) => <option key={c} value={c}>{budgetLabel(c)}</option>)}
          </select>
          <input
            aria-label="예산 추가 금액"
            inputMode="numeric"
            placeholder="금액(원)"
            value={addAmount}
            onChange={(e) => setAddAmount(e.target.value)}
            className="w-36 bg-zinc-900 border border-zinc-700 rounded px-2 py-1 text-sm"
          />
          <button disabled={save.isPending} className="text-sm px-3 py-1 rounded bg-blue-600 disabled:opacity-50">
            추가
          </button>
        </form>
      )}
    </div>
  );
}
```

- [ ] **Step 5: Nav + 라우트**

`components/Nav.tsx`: 대시보드 링크 다음에 `<Link to="/budget" className={linkCls("/budget")}>예산</Link>` 추가.
`App.tsx`: lazy 선언 추가
```tsx
const BudgetPage = lazy(() =>
  import("./routes/budget").then((m) => ({ default: m.BudgetPage })),
);
```
Routes에 `<Route path="/budget" element={<ProtectedRoute><BudgetPage /></ProtectedRoute>} />` 추가.

- [ ] **Step 6: 테스트·타입체크**

Run: `npx vitest run` → 전부 PASS. `npx tsc --noEmit -p .` → 에러 없음.

- [ ] **Step 7: Commit**

```bash
git add apps/web
git commit -m "feat(web): /budget page — set monthly budgets, progress, projection, warnings"
```

---

### Task 3: Web — 대시보드 예산 요약 카드 + 거래 변경 시 예산 갱신

**Files:**
- Create: `apps/web/src/components/BudgetSummaryCard.tsx`
- Modify: `apps/web/src/routes/dashboard.tsx` (InsightCard 아래 카드)
- Modify: `apps/web/src/lib/queries.ts` (거래 mutation 무효화에 `["budget"]`)
- Modify: `apps/web/src/routes/dashboard.test.tsx` (api mock에 `fetchBudgetStatus`)
- Test: `components/BudgetSummaryCard.test.tsx`, `lib/queries.delete.test.tsx` (budget 무효화 단언 추가)

**Interfaces:**
- Consumes: Task 2 `useBudgetStatus`, `BudgetBar`, `budgetLabel`, `TOTAL_KEY`, `BudgetItem`.
- Produces: `<BudgetSummaryCard month={string | undefined} />`.

- [ ] **Step 1: 실패 테스트**

`components/BudgetSummaryCard.test.tsx`:
```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { renderWithClient } from "../test/renderWithClient";

const { fetchBudgetStatusMock } = vi.hoisted(() => ({ fetchBudgetStatusMock: vi.fn() }));
vi.mock("../lib/api", () => ({ fetchBudgetStatus: fetchBudgetStatusMock, api: {} }));

import { BudgetSummaryCard } from "./BudgetSummaryCard";

const base = { month: "2026-10", is_current: true, days_elapsed: 20, days_in_month: 31 };
const it_ = (category: string, level: "ok" | "warn" | "over", ratio: number, projected: string | null = null) => ({
  category, budget: "100000", spent: String(ratio * 100000), ratio, projected, level,
});

function setup() {
  return renderWithClient(<MemoryRouter><BudgetSummaryCard month="2026-10" /></MemoryRouter>);
}

describe("BudgetSummaryCard", () => {
  beforeEach(() => fetchBudgetStatusMock.mockReset());

  it("links to budget setup when there are no budgets", async () => {
    fetchBudgetStatusMock.mockResolvedValue({ ...base, items: [] });
    setup();
    const link = await screen.findByRole("link", { name: /예산 설정하기/ });
    expect(link).toHaveAttribute("href", "/budget?month=2026-10");
  });

  it("shows total bar and up to 3 alerts (over/warn only)", async () => {
    fetchBudgetStatusMock.mockResolvedValue({ ...base, items: [
      it_("_total", "ok", 0.5),
      it_("coffee", "over", 1.24),
      it_("shopping", "warn", 0.3, "130000"),
      it_("lunch", "warn", 0.85),
      it_("dinner", "warn", 0.82),
      it_("health", "ok", 0.1),
    ]});
    setup();
    expect(await screen.findByText("총 지출")).toBeInTheDocument();
    expect(screen.getByText("커피 124% 초과")).toBeInTheDocument();
    expect(screen.getByText("쇼핑 월말 예상 초과")).toBeInTheDocument();
    expect(screen.getByText("점심 85% 사용")).toBeInTheDocument();
    expect(screen.queryByText(/저녁/)).toBeNull();   // 최대 3개
    expect(screen.queryByText(/의료/)).toBeNull();   // ok는 표시 안 함
  });
});
```
`lib/queries.delete.test.tsx`의 무효화 테스트 `arrayContaining` 목록에 `'["budget"]'` 추가.
Run: `npx vitest run src/components/BudgetSummaryCard.test.tsx src/lib/queries.delete.test.tsx` → FAIL.

- [ ] **Step 2: 카드 구현**

`components/BudgetSummaryCard.tsx`:
```tsx
import { Link } from "react-router-dom";
import { BudgetBar } from "./BudgetBar";
import type { BudgetItem } from "../lib/api";
import { TOTAL_KEY, budgetLabel } from "../lib/categories";
import { useBudgetStatus } from "../lib/queries";

function alertText(i: BudgetItem): string {
  const pct = Math.round(i.ratio * 100);
  if (i.level === "over") return `${budgetLabel(i.category)} ${pct}% 초과`;
  if (i.ratio >= 0.8) return `${budgetLabel(i.category)} ${pct}% 사용`;
  return `${budgetLabel(i.category)} 월말 예상 초과`;
}

export function BudgetSummaryCard({ month }: { month: string | undefined }) {
  const q = useBudgetStatus(month);
  if (!month || !q.data) return null;
  const href = `/budget?month=${month}`;
  const items = q.data.items;

  if (items.length === 0) {
    return (
      <Link to={href} className="block border border-zinc-800 rounded-lg p-4 text-sm text-zinc-400 hover:text-white">
        예산 설정하기 →
      </Link>
    );
  }

  const total = items.find((i) => i.category === TOTAL_KEY);
  const alerts = items
    .filter((i) => i.category !== TOTAL_KEY && i.level !== "ok")
    .slice(0, 3);

  return (
    <Link to={href} className="block border border-zinc-800 rounded-lg p-4 space-y-3 hover:border-zinc-600">
      <div className="text-sm text-zinc-400">이번 달 예산</div>
      {total && <BudgetBar item={total} />}
      {alerts.length > 0 && (
        <ul className="text-sm space-y-1">
          {alerts.map((i) => (
            <li key={i.category} className={i.level === "over" ? "text-red-300" : "text-amber-300"}>
              {alertText(i)}
            </li>
          ))}
        </ul>
      )}
    </Link>
  );
}
```
(`items`는 서버가 ratio 내림차순으로 정렬해 준다 — over가 앞에 온다.)

- [ ] **Step 3: 대시보드 배치 + 무효화**

`routes/dashboard.tsx`: `import { BudgetSummaryCard } from "../components/BudgetSummaryCard";` 추가, `{month && <InsightCard month={month} />}` 바로 다음 줄에 `<BudgetSummaryCard month={month} />`.
`routes/dashboard.test.tsx`의 `vi.mock("../lib/api", ...)` 객체에 `fetchBudgetStatus: vi.fn().mockResolvedValue({ month: "", is_current: true, days_elapsed: 1, days_in_month: 30, items: [] }),` 추가.
`lib/queries.ts`:
- `useCategoryOverride`·`useEssentialOverride`의 `onSettled` 무효화 블록에 `qc.invalidateQueries({ queryKey: ["budget"] });` 추가.
- `useDeleteTransaction`의 `onSettled`, `useUploadStatement`의 `onSuccess`에 같은 줄 추가.

- [ ] **Step 4: 테스트·타입체크**

Run: `npx vitest run` → PASS. `npx tsc --noEmit -p .` → 에러 없음.

- [ ] **Step 5: Commit**

```bash
git add apps/web
git commit -m "feat(web): dashboard budget summary card + refresh budgets on transaction changes"
```

---

### Task 4: 문서 + 배포 + 운영 검증

**Files:**
- Modify: `docs/FEATURES.md` (API 표, 기능 섹션, 프론트 라우트 표)

- [ ] **Step 1: FEATURES.md**

- 3장에 `### 3.8 월 예산` 섹션: 총액·카테고리별 매월 반복 예산, 변경은 이번 달부터(KST), 지출 집계는 대시보드와 동일 규칙, 진행률·월말 예상·level(ok/warn/over) 기준, `/budget` 탭과 대시보드 카드.
- 4장 API 표에 `GET /budgets/status`, `PUT /budgets` 행, 에러 코드에 `INVALID_CATEGORY`.
- 5장 라우트 표에 `/budget` 행.

- [ ] **Step 2: Commit + PR + 머지**

```bash
git add docs/FEATURES.md
git commit -m "docs(infra): W7 budgets in FEATURES.md"
git push -u origin feat/budget-goals
gh pr create --title "feat: monthly budget goals + in-app overspend warnings (W7)" --body "..."
```
CI(api/web/Vercel) 통과 후 squash 머지 → Deploy API 완료 대기 (migration 0007 자동 적용).

- [ ] **Step 3: 운영 검증**

- `curl $WEB/api/healthz` 200.
- QA 계정(`qa-proxy-20261019@example.com`)으로 `/budget` 접속 → 총 지출 예산 설정 → 카테고리 추가 → 진행률·월말 예상 표시 확인.
- 대시보드 요약 카드 표시·링크 확인, 지난달 선택 시 읽기 전용 확인.
- 거래 1건 카테고리 변경 후 예산 사용액 갱신 확인.
- 375px 모바일에서 Nav 한 줄·예산 행 레이아웃 확인 (SW 캐시 비운 뒤).
