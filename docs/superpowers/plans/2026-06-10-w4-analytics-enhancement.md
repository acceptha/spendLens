# W4 분석 고도화 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 대시보드에 월간 LLM 인사이트 리포트, 입금/소득 분석, 필수/비필수 토글을 추가해 분석 가치를 끌어올린다.

**Architecture:** asyncpg raw SQL + FastAPI(백엔드), React+Tremor(프론트). 필수/비필수는 저장하지 않고 `effective_category`에서 코드 맵으로 파생(`essential_override` 컬럼만 추가). 인사이트는 온디맨드 생성 후 `monthly_insights` 테이블에 캐시하며 기존 LLM 예산 가드를 공유한다.

**Tech Stack:** Python 3.12 / Pydantic v2 / asyncpg / Alembic raw SQL / anthropic SDK(Haiku) / React / Vite / @tremor/react / axios / pytest / vitest.

**Spec:** `docs/superpowers/specs/2026-06-10-w4-analytics-enhancement-design.md`

**공통 규칙 (CLAUDE.md):** snake_case 파일, 라우터에서 직접 `HTTPException`(코드 `UPPER_SNAKE_CASE`), DB는 `async with acquire()`, 인증만 `Depends(current_user_id)`, Conventional Commits(스코프 `api`/`web`/`infra`). 백엔드 테스트: `cd apps/api && uv run pytest <path> -v`. 프론트 테스트: `cd apps/web && pnpm vitest run <path>`.

---

## Phase 1 — 마이그레이션 + essential 맵

### Task 1: 마이그레이션 0004 (essential_override + monthly_insights)

**Files:**
- Create: `apps/api/migrations/versions/0004_add_essential_override_and_insights.py`
- Modify: `apps/api/tests/conftest.py:51-54` (TRUNCATE 목록에 monthly_insights 추가)

- [ ] **Step 1: 마이그레이션 작성**

```python
"""add essential_override and monthly_insights

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-10
"""
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE transactions ADD COLUMN essential_override BOOLEAN NULL;")
    op.execute(
        """
        CREATE TABLE monthly_insights (
          user_id      UUID NOT NULL REFERENCES users(id),
          month        TEXT NOT NULL,
          payload      JSONB NOT NULL,
          generated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          PRIMARY KEY (user_id, month)
        );
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE monthly_insights;")
    op.execute("ALTER TABLE transactions DROP COLUMN essential_override;")
```

- [ ] **Step 2: 마이그레이션 적용**

Run: `cd apps/api && uv run alembic upgrade head`
Expected: `Running upgrade 0003 -> 0004` 출력, 에러 없음.

- [ ] **Step 3: 테스트 DB에도 적용 + conftest TRUNCATE 갱신**

`apps/api/tests/conftest.py`의 `reset_tables` TRUNCATE 문을 다음으로 교체 (monthly_insights 추가):

```python
        await conn.execute("""
            TRUNCATE monthly_insights, llm_usage_log, transactions, source_files, refresh_tokens, users
            RESTART IDENTITY CASCADE;
        """)
```

테스트 DB 마이그레이션: `cd apps/api && DATABASE_URL=<test db url> uv run alembic upgrade head` (CI는 자동, 로컬은 test DB에도 1회 적용).

- [ ] **Step 4: 스키마 적용 확인**

Run: `cd apps/api && uv run pytest tests/test_health.py -v`
Expected: PASS (앱 기동 + TRUNCATE가 monthly_insights 포함해 성공).

- [ ] **Step 5: Commit**

```bash
git add apps/api/migrations/versions/0004_add_essential_override_and_insights.py apps/api/tests/conftest.py
git commit -m "feat(api): migration 0004 — essential_override column + monthly_insights table"
```

---

### Task 2: essential 기본 매핑 모듈

**Files:**
- Create: `apps/api/app/categorization/essential.py`
- Test: `apps/api/tests/categorization/test_essential.py`

- [ ] **Step 1: 실패 테스트 작성**

```python
from app.categorization.essential import (
    ESSENTIAL_CATEGORIES,
    ESSENTIAL_DEFAULTS,
    is_essential,
)
from app.categorization.rulebook import CATEGORIES


def test_essential_defaults_cover_all_categories():
    # 19개 카테고리 전부 매핑되어 있어야 함 (누락 시 KeyError 위험)
    assert set(ESSENTIAL_DEFAULTS.keys()) == set(CATEGORIES)


def test_is_essential_true_for_housing():
    assert is_essential("housing") is True


def test_is_essential_false_for_coffee():
    assert is_essential("coffee") is False


def test_is_essential_unknown_category_defaults_false():
    assert is_essential("nonexistent") is False


def test_essential_categories_is_subset_of_true_defaults():
    assert set(ESSENTIAL_CATEGORIES) == {c for c, v in ESSENTIAL_DEFAULTS.items() if v}
```

- [ ] **Step 2: 실패 확인**

Run: `cd apps/api && uv run pytest tests/categorization/test_essential.py -v`
Expected: FAIL — `ModuleNotFoundError: app.categorization.essential`.

- [ ] **Step 3: 구현**

`apps/api/app/categorization/essential.py`:

```python
"""카테고리 → 필수/비필수 기본 매핑.

essential은 저장하지 않고 effective_category에서 파생한다. 단일 진실 공급원.
사용자가 명시 토글하면 transactions.essential_override가 우선한다.
CATEGORIES(rulebook)와 키 동기화 유지.
"""
ESSENTIAL_DEFAULTS: dict[str, bool] = {
    "housing": True,
    "utilities": True,
    "telecom": True,
    "groceries": True,
    "health": True,
    "insurance": True,
    "transport": True,
    "lunch": True,
    "dinner": True,
    "savings": True,
    "income": True,
    "transfer": True,
    "coffee": False,
    "snack_late": False,
    "subscription": False,
    "entertainment": False,
    "shopping": False,
    "etc": False,
    "unknown": False,
}

ESSENTIAL_CATEGORIES: tuple[str, ...] = tuple(
    c for c, v in ESSENTIAL_DEFAULTS.items() if v
)


def is_essential(category: str) -> bool:
    return ESSENTIAL_DEFAULTS.get(category, False)
```

- [ ] **Step 4: 통과 확인**

Run: `cd apps/api && uv run pytest tests/categorization/test_essential.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/categorization/essential.py apps/api/tests/categorization/test_essential.py
git commit -m "feat(api): category essential defaults map"
```

---

## Phase 2 — transactions: effective_essential + 토글

### Task 3: TransactionOut에 effective_essential 노출

**Files:**
- Modify: `apps/api/app/transactions/schemas.py:22-40` (TransactionOut)
- Modify: `apps/api/app/transactions/routes.py:118-135` (SELECT)
- Test: `apps/api/tests/transactions/test_filter_query.py` (신규 assert 추가) — 또는 신규 `test_effective_essential.py`

- [ ] **Step 1: 실패 테스트 작성** — `apps/api/tests/transactions/test_effective_essential.py`

```python
from uuid import uuid4

import httpx
from httpx import ASGITransport

from app.main import app


async def _client():
    return httpx.AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    )


async def _signup(ac):
    email = f"_w4-ess-{uuid4()}@example.com"
    r = await ac.post("/auth/signup", json={"email": email, "password": "abcd1234"})
    return r.json()["access_token"], email


async def _txn(conn, email, *, category):
    u = await conn.fetchrow("SELECT id FROM users WHERE email = $1", email)
    row = await conn.fetchrow(
        """
        INSERT INTO transactions (user_id, source_type, txn_date, amount, merchant_raw,
          category, dedup_hash, raw_row)
        VALUES ($1,'test',CURRENT_DATE,1000,'M',$2,$3,'{}'::jsonb) RETURNING id
        """,
        u["id"], category, str(uuid4()),
    )
    return row["id"]


async def test_effective_essential_derived_from_category(test_db_pool):
    async with await _client() as ac:
        token, email = await _signup(ac)
        async with test_db_pool.acquire() as conn:
            await _txn(conn, email, category="housing")   # 기본 필수
            await _txn(conn, email, category="coffee")    # 기본 비필수

        r = await ac.get("/transactions", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200, r.text
        by_cat = {t["effective_category"]: t for t in r.json()}
        assert by_cat["housing"]["effective_essential"] is True
        assert by_cat["housing"]["essential_override"] is None
        assert by_cat["coffee"]["effective_essential"] is False
```

- [ ] **Step 2: 실패 확인**

Run: `cd apps/api && uv run pytest tests/transactions/test_effective_essential.py -v`
Expected: FAIL — 응답에 `effective_essential` 키 없음(KeyError) 또는 422.

- [ ] **Step 3: 스키마 수정** — `apps/api/app/transactions/schemas.py`의 TransactionOut에서 `essential`/`essential_reason` 두 줄 제거 후 교체:

```python
    # W3 추가
    auto_category: str
    user_category_override: str | None
    effective_category: str
    # W4 — 필수/비필수 (파생)
    essential_override: bool | None
    effective_essential: bool
```

- [ ] **Step 4: SELECT 수정** — `apps/api/app/transactions/routes.py`의 `fetch` SQL에서 `essential, essential_reason` 줄을 교체. 파일 상단에 import 추가: `from app.categorization.essential import ESSENTIAL_CATEGORIES`. SQL의 SELECT 끝부분:

```sql
                   user_category_override,
                   COALESCE(user_category_override, category) AS effective_category,
                   essential_override,
                   CASE WHEN essential_override IS NOT NULL THEN essential_override
                        ELSE (COALESCE(user_category_override, category) = ANY($7::text[]))
                   END AS effective_essential
```

그리고 `WHERE`/`LIMIT`/`OFFSET` 파라미터 번호를 한 칸씩 밀어 `$7`을 essential 카테고리 배열로 추가. 현재 파라미터는 `user_id, month, categories, search, limit, offset` ($1~$6). `$7`을 추가하되 SQL 본문 내 위치는 SELECT이므로, 호출 인자 끝에 `list(ESSENTIAL_CATEGORIES)`를 추가:

```python
        rows = await conn.fetch(
            """
            SELECT id::text, txn_date, txn_time, amount, merchant_raw, merchant_normalized,
                   approval_no, card_last4, installment_months, is_canceled,
                   category,
                   category AS auto_category,
                   user_category_override,
                   COALESCE(user_category_override, category) AS effective_category,
                   essential_override,
                   CASE WHEN essential_override IS NOT NULL THEN essential_override
                        ELSE (COALESCE(user_category_override, category) = ANY($7::text[]))
                   END AS effective_essential
            FROM transactions
            WHERE user_id = $1
              AND ($2::text IS NULL OR to_char(txn_date, 'YYYY-MM') = $2)
              AND ($3::text[] IS NULL OR COALESCE(user_category_override, category) = ANY($3))
              AND ($4::text IS NULL OR merchant_raw ILIKE '%' || $4 || '%')
            ORDER BY txn_date DESC, txn_time DESC NULLS LAST, created_at DESC
            LIMIT $5 OFFSET $6
            """,
            user_id, month, categories, search, limit, offset,
            list(ESSENTIAL_CATEGORIES),
        )
```

- [ ] **Step 5: 통과 확인 + 회귀**

Run: `cd apps/api && uv run pytest tests/transactions/ -v`
Expected: 신규 테스트 PASS, 기존 transactions 테스트 전부 PASS (effective_essential 추가가 기존 키 안 깨뜨림).

- [ ] **Step 6: Commit**

```bash
git add apps/api/app/transactions/schemas.py apps/api/app/transactions/routes.py apps/api/tests/transactions/test_effective_essential.py
git commit -m "feat(api): expose effective_essential on TransactionOut (derived)"
```

---

### Task 4: PATCH /transactions/{id}/essential 토글

**Files:**
- Modify: `apps/api/app/transactions/service.py` (update_essential 추가)
- Modify: `apps/api/app/transactions/schemas.py` (EssentialPatchRequest 추가)
- Modify: `apps/api/app/transactions/routes.py` (엔드포인트 추가)
- Test: `apps/api/tests/transactions/test_patch_essential.py`

- [ ] **Step 1: 실패 테스트 작성**

```python
from uuid import uuid4

import httpx
from httpx import ASGITransport

from app.main import app


async def _client():
    return httpx.AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    )


async def _signup(ac):
    email = f"_w4-pe-{uuid4()}@example.com"
    r = await ac.post("/auth/signup", json={"email": email, "password": "abcd1234"})
    return r.json()["access_token"], email


async def _txn(conn, email, *, category="coffee"):
    u = await conn.fetchrow("SELECT id FROM users WHERE email = $1", email)
    row = await conn.fetchrow(
        """
        INSERT INTO transactions (user_id, source_type, txn_date, amount, merchant_raw,
          category, dedup_hash, raw_row)
        VALUES ($1,'test',CURRENT_DATE,1000,'M',$2,$3,'{}'::jsonb) RETURNING id
        """,
        u["id"], category, str(uuid4()),
    )
    return row["id"]


async def test_patch_essential_true_overrides_default(test_db_pool):
    async with await _client() as ac:
        token, email = await _signup(ac)
        async with test_db_pool.acquire() as conn:
            tid = await _txn(conn, email, category="coffee")  # 기본 False

        r = await ac.patch(
            f"/transactions/{tid}/essential",
            headers={"Authorization": f"Bearer {token}"},
            json={"essential_override": True},
        )
        assert r.status_code == 204, r.text

        g = await ac.get("/transactions", headers={"Authorization": f"Bearer {token}"})
        row = next(t for t in g.json() if t["id"] == str(tid))
        assert row["essential_override"] is True
        assert row["effective_essential"] is True


async def test_patch_essential_null_resets_to_default(test_db_pool):
    async with await _client() as ac:
        token, email = await _signup(ac)
        async with test_db_pool.acquire() as conn:
            tid = await _txn(conn, email, category="housing")  # 기본 True

        await ac.patch(f"/transactions/{tid}/essential",
                       headers={"Authorization": f"Bearer {token}"},
                       json={"essential_override": False})
        r = await ac.patch(f"/transactions/{tid}/essential",
                           headers={"Authorization": f"Bearer {token}"},
                           json={"essential_override": None})
        assert r.status_code == 204, r.text

        g = await ac.get("/transactions", headers={"Authorization": f"Bearer {token}"})
        row = next(t for t in g.json() if t["id"] == str(tid))
        assert row["essential_override"] is None
        assert row["effective_essential"] is True  # 기본값으로 복귀


async def test_patch_essential_404_unknown_id(test_db_pool):
    async with await _client() as ac:
        token, _ = await _signup(ac)
        r = await ac.patch(f"/transactions/{uuid4()}/essential",
                           headers={"Authorization": f"Bearer {token}"},
                           json={"essential_override": True})
        assert r.status_code == 404
        assert r.json()["detail"] == "NOT_FOUND"
```

- [ ] **Step 2: 실패 확인**

Run: `cd apps/api && uv run pytest tests/transactions/test_patch_essential.py -v`
Expected: FAIL — 404 라우트 없음.

- [ ] **Step 3: service 함수 추가** — `apps/api/app/transactions/service.py` 끝에:

```python
async def update_essential(
    conn: asyncpg.Connection,
    user_id: UUID,
    transaction_id: UUID,
    essential_override: bool | None,
) -> bool:
    """Set essential_override (true/false/null) for one transaction owned by user_id.

    null clears the override → effective_essential falls back to the category default.
    Returns True if updated, False if not found / owned by another user.
    """
    row = await conn.fetchrow(
        """
        UPDATE transactions
        SET essential_override = $3
        WHERE id = $2 AND user_id = $1
        RETURNING id
        """,
        user_id, transaction_id, essential_override,
    )
    return row is not None
```

- [ ] **Step 4: 스키마 추가** — `apps/api/app/transactions/schemas.py` 끝에:

```python
class EssentialPatchRequest(BaseModel):
    essential_override: bool | None
```

- [ ] **Step 5: 라우트 추가** — `apps/api/app/transactions/routes.py`. import에 `EssentialPatchRequest`, service의 `update_essential` 추가 후 PATCH 핸들러 뒤에:

```python
@router.patch("/{transaction_id}/essential", status_code=204)
async def patch_transaction_essential(
    transaction_id: UUID,
    req: EssentialPatchRequest,
    user_id: UUID = Depends(current_user_id),  # noqa: B008
) -> None:
    async with acquire() as conn:
        updated = await update_essential(
            conn, user_id, transaction_id, req.essential_override
        )
    if not updated:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
```

> 주의: `/{transaction_id}/essential`이 기존 `/{transaction_id}`(PATCH)와 충돌하지 않도록 라우트 등록 순서는 FastAPI가 경로 특이성으로 해결하나, 더 구체적인 경로를 먼저 선언해도 무방.

- [ ] **Step 6: 통과 확인**

Run: `cd apps/api && uv run pytest tests/transactions/ -v`
Expected: 신규 3 PASS + 기존 전부 PASS.

- [ ] **Step 7: Commit**

```bash
git add apps/api/app/transactions/service.py apps/api/app/transactions/schemas.py apps/api/app/transactions/routes.py apps/api/tests/transactions/test_patch_essential.py
git commit -m "feat(api): PATCH /transactions/{id}/essential toggle (3-state)"
```

---

## Phase 3 — dashboard: 소득 분석 + 필수/비필수 집계

### Task 5: summary 확장 (income_total / net_savings / savings_rate)

**Files:**
- Modify: `apps/api/app/dashboard/service.py:28-63` (summary)
- Modify: `apps/api/app/dashboard/routes.py:14-21` (SummaryResponse)
- Test: `apps/api/tests/dashboard/test_summary.py` (추가)

- [ ] **Step 1: 실패 테스트 추가** — `apps/api/tests/dashboard/test_summary.py` 끝에:

```python
async def test_summary_income_and_savings_rate(test_db_pool):
    """수입(amount<0, 이체 제외) + 순저축 + 저축률."""
    async with await _client() as ac:
        token, email = await _signup_and_token(ac)
        async with test_db_pool.acquire() as conn:
            user = await conn.fetchrow("SELECT id FROM users WHERE email=$1", email)
            uid = user["id"]
            # 지출 30000
            await conn.execute(
                "INSERT INTO transactions (user_id, source_type, txn_date, amount, merchant_raw, category, dedup_hash, raw_row) "
                "VALUES ($1,'test','2026-05-01',30000,'M','etc',$2,'{}'::jsonb)",
                uid, str(uuid4()))
            # 수입(급여) 100000 — income
            await conn.execute(
                "INSERT INTO transactions (user_id, source_type, txn_date, amount, merchant_raw, category, dedup_hash, raw_row) "
                "VALUES ($1,'test','2026-05-02',-100000,'급여','income',$2,'{}'::jsonb)",
                uid, str(uuid4()))
            # 이체 입금 -50000 — transfer (수입에서 제외돼야 함)
            await conn.execute(
                "INSERT INTO transactions (user_id, source_type, txn_date, amount, merchant_raw, category, dedup_hash, raw_row) "
                "VALUES ($1,'test','2026-05-03',-50000,'이체','transfer',$2,'{}'::jsonb)",
                uid, str(uuid4()))

        r = await ac.get("/dashboard/summary?month=2026-05",
                         headers={"Authorization": f"Bearer {token}"})
        body = r.json()
        assert float(body["total_amount"]) == 30000        # 지출
        assert float(body["income_total"]) == 100000        # 이체 제외
        assert float(body["net_savings"]) == 70000           # 100000 - 30000
        assert round(body["savings_rate"], 1) == 70.0        # 70000/100000*100


async def test_summary_zero_income_savings_rate_null(test_db_pool):
    async with await _client() as ac:
        token, email = await _signup_and_token(ac)
        async with test_db_pool.acquire() as conn:
            await _seed(conn, email, txn_date="2026-05-01", amount=10000)

        r = await ac.get("/dashboard/summary?month=2026-05",
                         headers={"Authorization": f"Bearer {token}"})
        body = r.json()
        assert float(body["income_total"]) == 0
        assert body["savings_rate"] is None
```

(파일 상단 import에 `from uuid import uuid4`가 이미 있음.)

- [ ] **Step 2: 실패 확인**

Run: `cd apps/api && uv run pytest tests/dashboard/test_summary.py -v`
Expected: FAIL — 응답에 income_total 없음.

- [ ] **Step 3: service.summary 수정** — `apps/api/app/dashboard/service.py`의 `summary` 함수 본문에서 현재 출금 쿼리 뒤에 수입 쿼리 추가하고 반환 dict 확장:

```python
async def summary(conn: asyncpg.Connection, user_id: UUID, month: str) -> dict:
    validate_month(month)
    prev = _prev_month(month)

    row = await conn.fetchrow(
        """
        SELECT COALESCE(SUM(amount), 0)::numeric AS total,
               COUNT(*) AS cnt
        FROM transactions
        WHERE user_id = $1 AND to_char(txn_date, 'YYYY-MM') = $2 AND amount > 0
        """,
        user_id, month,
    )
    prev_row = await conn.fetchrow(
        """
        SELECT COALESCE(SUM(amount), 0)::numeric AS total
        FROM transactions
        WHERE user_id = $1 AND to_char(txn_date, 'YYYY-MM') = $2 AND amount > 0
        """,
        user_id, prev,
    )
    income_row = await conn.fetchrow(
        """
        SELECT COALESCE(SUM(-amount), 0)::numeric AS income
        FROM transactions
        WHERE user_id = $1 AND to_char(txn_date, 'YYYY-MM') = $2
          AND amount < 0
          AND COALESCE(user_category_override, category) <> 'transfer'
        """,
        user_id, month,
    )

    cur_total = Decimal(row["total"])
    prev_total = Decimal(prev_row["total"])
    income_total = Decimal(income_row["income"])
    net_savings = income_total - cur_total

    diff_pct: float | None = None
    if prev_total > 0:
        diff_pct = float((cur_total - prev_total) / prev_total * 100)

    savings_rate: float | None = None
    if income_total > 0:
        savings_rate = float(net_savings / income_total * 100)

    return {
        "month": month,
        "total_amount": cur_total,
        "transaction_count": row["cnt"],
        "prev_month": prev,
        "prev_month_total": prev_total,
        "prev_month_diff_pct": diff_pct,
        "income_total": income_total,
        "net_savings": net_savings,
        "savings_rate": savings_rate,
    }
```

- [ ] **Step 4: SummaryResponse 확장** — `apps/api/app/dashboard/routes.py`의 SummaryResponse에 3필드 추가:

```python
class SummaryResponse(BaseModel):
    month: str
    total_amount: Decimal
    transaction_count: int
    prev_month: str
    prev_month_total: Decimal
    prev_month_diff_pct: float | None
    income_total: Decimal
    net_savings: Decimal
    savings_rate: float | None
```

- [ ] **Step 5: 통과 확인**

Run: `cd apps/api && uv run pytest tests/dashboard/test_summary.py -v`
Expected: 기존 4 + 신규 2 = 6 passed.

- [ ] **Step 6: Commit**

```bash
git add apps/api/app/dashboard/service.py apps/api/app/dashboard/routes.py apps/api/tests/dashboard/test_summary.py
git commit -m "feat(api): summary income_total/net_savings/savings_rate (transfer excluded)"
```

---

### Task 6: cashflow-by-month (by-month 대체)

**Files:**
- Modify: `apps/api/app/dashboard/service.py` (by_month → cashflow_by_month)
- Modify: `apps/api/app/dashboard/routes.py` (MonthBucket → CashflowBucket, 라우트 교체)
- Delete tests: `apps/api/tests/dashboard/test_by_month.py` 내용 교체 → `test_cashflow_by_month.py`

- [ ] **Step 1: 실패 테스트 작성** — `apps/api/tests/dashboard/test_cashflow_by_month.py`

```python
import datetime
from uuid import uuid4

import httpx
from httpx import ASGITransport

from app.main import app


async def _client():
    return httpx.AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    )


async def _signup(ac):
    email = f"_w4-cf-{uuid4()}@example.com"
    r = await ac.post("/auth/signup", json={"email": email, "password": "abcd1234"})
    return r.json()["access_token"], email


async def _ins(conn, email, *, d, amount, category="etc"):
    u = await conn.fetchrow("SELECT id FROM users WHERE email=$1", email)
    await conn.execute(
        "INSERT INTO transactions (user_id, source_type, txn_date, amount, merchant_raw, category, dedup_hash, raw_row) "
        "VALUES ($1,'test',$2,$3,'M',$4,$5,'{}'::jsonb)",
        u["id"], datetime.date.fromisoformat(d), amount, category, str(uuid4()))


async def test_cashflow_by_month_splits_expense_income(test_db_pool):
    async with await _client() as ac:
        token, email = await _signup(ac)
        async with test_db_pool.acquire() as conn:
            this_month = datetime.date.today().strftime("%Y-%m")
            d = f"{this_month}-05"
            await _ins(conn, email, d=d, amount=20000, category="etc")     # 지출
            await _ins(conn, email, d=d, amount=-80000, category="income") # 수입
            await _ins(conn, email, d=d, amount=-30000, category="transfer") # 이체 제외

        r = await ac.get("/dashboard/cashflow-by-month?last_n=6",
                         headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200, r.text
        rows = {row["month"]: row for row in r.json()}
        cur = rows[this_month]
        assert float(cur["expense"]) == 20000
        assert float(cur["income"]) == 80000   # 이체 제외


async def test_cashflow_invalid_last_n_400(test_db_pool):
    async with await _client() as ac:
        token, _ = await _signup(ac)
        r = await ac.get("/dashboard/cashflow-by-month?last_n=99",
                         headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 400
```

기존 `apps/api/tests/dashboard/test_by_month.py`는 삭제.

- [ ] **Step 2: 실패 확인**

Run: `cd apps/api && uv run pytest tests/dashboard/test_cashflow_by_month.py -v`
Expected: FAIL — 404 (라우트 없음).

- [ ] **Step 3: service 교체** — `apps/api/app/dashboard/service.py`의 `by_month` 함수를 `cashflow_by_month`로 교체:

```python
async def cashflow_by_month(conn: asyncpg.Connection, user_id: UUID, last_n: int) -> list[dict]:
    if not (1 <= last_n <= 24):
        raise ValueError(f"last_n out of range: {last_n}")
    rows = await conn.fetch(
        """
        SELECT to_char(txn_date, 'YYYY-MM') AS month,
               COALESCE(SUM(amount) FILTER (WHERE amount > 0), 0)::numeric AS expense,
               COALESCE(SUM(-amount) FILTER (
                   WHERE amount < 0 AND COALESCE(user_category_override, category) <> 'transfer'
               ), 0)::numeric AS income
        FROM transactions
        WHERE user_id = $1
          AND txn_date >= date_trunc('month', CURRENT_DATE - ($2 - 1) * INTERVAL '1 month')
        GROUP BY to_char(txn_date, 'YYYY-MM')
        ORDER BY to_char(txn_date, 'YYYY-MM') ASC
        """,
        user_id, last_n,
    )
    return [{"month": r["month"], "expense": r["expense"], "income": r["income"]} for r in rows]
```

- [ ] **Step 4: 라우트 교체** — `apps/api/app/dashboard/routes.py`에서 `MonthBucket` → `CashflowBucket`, `get_by_month` → `get_cashflow_by_month`:

```python
class CashflowBucket(BaseModel):
    month: str
    expense: Decimal
    income: Decimal


@router.get("/cashflow-by-month", response_model=list[CashflowBucket])
async def get_cashflow_by_month(
    last_n: int = 6,
    user_id: UUID = Depends(current_user_id),  # noqa: B008
) -> list[CashflowBucket]:
    try:
        async with acquire() as conn:
            rows = await service.cashflow_by_month(conn, user_id, last_n)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="INVALID_LAST_N") from exc
    return [CashflowBucket(**r) for r in rows]
```

- [ ] **Step 5: 통과 확인 + 회귀**

Run: `cd apps/api && uv run pytest tests/dashboard/ -v`
Expected: 신규 PASS, by-month 테스트 제거됨, 나머지 PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/api/app/dashboard/service.py apps/api/app/dashboard/routes.py apps/api/tests/dashboard/test_cashflow_by_month.py
git rm apps/api/tests/dashboard/test_by_month.py
git commit -m "feat(api): cashflow-by-month (expense+income, replaces by-month)"
```

---

### Task 7: by-essential 집계

**Files:**
- Modify: `apps/api/app/dashboard/service.py` (by_essential 추가)
- Modify: `apps/api/app/dashboard/routes.py` (EssentialBucket + 라우트)
- Test: `apps/api/tests/dashboard/test_by_essential.py`

- [ ] **Step 1: 실패 테스트 작성**

```python
from uuid import uuid4

import httpx
from httpx import ASGITransport

from app.main import app


async def _client():
    return httpx.AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    )


async def _signup(ac):
    email = f"_w4-be-{uuid4()}@example.com"
    r = await ac.post("/auth/signup", json={"email": email, "password": "abcd1234"})
    return r.json()["access_token"], email


async def _ins(conn, email, *, amount, category, override=None):
    u = await conn.fetchrow("SELECT id FROM users WHERE email=$1", email)
    await conn.execute(
        "INSERT INTO transactions (user_id, source_type, txn_date, amount, merchant_raw, category, essential_override, dedup_hash, raw_row) "
        "VALUES ($1,'test','2026-05-10',$2,'M',$3,$4,$5,'{}'::jsonb)",
        u["id"], amount, category, override, str(uuid4()))


async def test_by_essential_default_and_override(test_db_pool):
    async with await _client() as ac:
        token, email = await _signup(ac)
        async with test_db_pool.acquire() as conn:
            await _ins(conn, email, amount=10000, category="housing")             # 기본 필수
            await _ins(conn, email, amount=5000, category="coffee")               # 기본 비필수
            await _ins(conn, email, amount=3000, category="coffee", override=True) # 오버라이드→필수

        r = await ac.get("/dashboard/by-essential?month=2026-05",
                         headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200, r.text
        buckets = {b["essential"]: b for b in r.json()}
        assert float(buckets[True]["amount"]) == 13000   # housing + override coffee
        assert buckets[True]["count"] == 2
        assert float(buckets[False]["amount"]) == 5000    # 기본 coffee


async def test_by_essential_invalid_month_400(test_db_pool):
    async with await _client() as ac:
        token, _ = await _signup(ac)
        r = await ac.get("/dashboard/by-essential?month=bad",
                         headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 400
```

- [ ] **Step 2: 실패 확인**

Run: `cd apps/api && uv run pytest tests/dashboard/test_by_essential.py -v`
Expected: FAIL — 404.

- [ ] **Step 3: service 추가** — `apps/api/app/dashboard/service.py`. 상단 import에 `from app.categorization.essential import ESSENTIAL_CATEGORIES` 추가 후:

```python
async def by_essential(conn: asyncpg.Connection, user_id: UUID, month: str) -> list[dict]:
    validate_month(month)
    rows = await conn.fetch(
        """
        SELECT (CASE WHEN essential_override IS NOT NULL THEN essential_override
                     ELSE (COALESCE(user_category_override, category) = ANY($3::text[]))
                END) AS essential,
               COALESCE(SUM(amount), 0)::numeric AS amount,
               COUNT(*) AS count
        FROM transactions
        WHERE user_id = $1 AND to_char(txn_date, 'YYYY-MM') = $2 AND amount > 0
        GROUP BY essential
        ORDER BY essential DESC
        """,
        user_id, month, list(ESSENTIAL_CATEGORIES),
    )
    return [{"essential": r["essential"], "amount": r["amount"], "count": r["count"]} for r in rows]
```

- [ ] **Step 4: 라우트 추가** — `apps/api/app/dashboard/routes.py`:

```python
class EssentialBucket(BaseModel):
    essential: bool
    amount: Decimal
    count: int


@router.get("/by-essential", response_model=list[EssentialBucket])
async def get_by_essential(
    month: str,
    user_id: UUID = Depends(current_user_id),  # noqa: B008
) -> list[EssentialBucket]:
    try:
        async with acquire() as conn:
            rows = await service.by_essential(conn, user_id, month)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="INVALID_MONTH_FORMAT") from exc
    return [EssentialBucket(**r) for r in rows]
```

- [ ] **Step 5: 통과 확인**

Run: `cd apps/api && uv run pytest tests/dashboard/ -v`
Expected: 전부 PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/api/app/dashboard/service.py apps/api/app/dashboard/routes.py apps/api/tests/dashboard/test_by_essential.py
git commit -m "feat(api): by-essential aggregation (override + category default)"
```

---

## Phase 4 — budget purpose 파라미터

### Task 8: record_usage에 purpose 파라미터

**Files:**
- Modify: `apps/api/app/categorization/budget.py:39-58`
- Test: `apps/api/tests/categorization/test_budget.py` (추가)

- [ ] **Step 1: 실패 테스트 추가** — `apps/api/tests/categorization/test_budget.py` 끝에 (기존 테스트 스타일 확인 후 동일 픽스처 사용):

```python
async def test_record_usage_logs_purpose(test_db_pool):
    from app.categorization import budget
    await budget.record_usage(
        input_tokens=100, output_tokens=20, merchant="x", purpose="insight"
    )
    async with test_db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT purpose FROM llm_usage_log ORDER BY id DESC LIMIT 1"
        )
    assert row["purpose"] == "insight"
```

> 기존 `test_budget.py`가 record_usage를 호출하는 방식(redis/DB 의존)을 확인하고 동일 픽스처(`test_db_pool`, redis reset)를 사용. llm_usage_log의 PK 컬럼명이 `id`가 아니면 `generated`/`created_at` 등 기존 정렬 컬럼으로 교체.

- [ ] **Step 2: 실패 확인**

Run: `cd apps/api && uv run pytest tests/categorization/test_budget.py -v`
Expected: FAIL — `record_usage() got unexpected keyword 'purpose'`.

- [ ] **Step 3: budget.record_usage 수정** — 시그니처에 `purpose` 추가, INSERT의 하드코딩 `'categorize'`를 파라미터화:

```python
async def record_usage(
    *,
    input_tokens: int,
    output_tokens: int,
    merchant: str,
    model: str = HAIKU_MODEL_ID,
    purpose: str = "categorize",
) -> None:
    cost = _cost(input_tokens, output_tokens)
    async with acquire_redis() as r:
        await r.incrbyfloat(_bucket_key(), cost)

    async with acquire() as conn:
        await conn.execute(
            """
            INSERT INTO llm_usage_log
              (model, input_tokens, output_tokens, cost_usd, purpose, merchant_normalized)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            model, input_tokens, output_tokens, cost, purpose, merchant,
        )
```

- [ ] **Step 4: 통과 확인 + 회귀**

Run: `cd apps/api && uv run pytest tests/categorization/test_budget.py tests/categorization/test_service.py -v`
Expected: 신규 PASS + 기존 categorize 경로 PASS(기본값 유지).

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/categorization/budget.py apps/api/tests/categorization/test_budget.py
git commit -m "feat(api): record_usage accepts purpose param (default categorize)"
```

---

## Phase 5 — insights 모듈

### Task 9: insights/llm.py — 구조화 인사이트 생성

**Files:**
- Create: `apps/api/app/insights/__init__.py` (빈 파일)
- Create: `apps/api/app/insights/llm.py`
- Test: `apps/api/tests/insights/__init__.py` (빈), `apps/api/tests/insights/test_llm.py`

- [ ] **Step 1: 실패 테스트 작성** — `apps/api/tests/insights/test_llm.py`

```python
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.insights.llm import InsightError, generate_insight


def _fake_client(text: str, input_tokens=300, output_tokens=120):
    msg = MagicMock()
    msg.content = [MagicMock(text=text)]
    msg.usage = MagicMock(input_tokens=input_tokens, output_tokens=output_tokens)
    client = MagicMock()
    client.messages = MagicMock()
    client.messages.create = AsyncMock(return_value=msg)
    return client


_VALID = (
    '{"summary": "이번 달 지출은 전월 대비 늘었습니다.",'
    ' "highlights": [{"type": "top_growth", "title": "커피 급증",'
    ' "detail": "전월 대비 2배"}]}'
)


async def test_generate_insight_parses_structured(monkeypatch):
    monkeypatch.setattr("app.insights.llm._client", lambda: _fake_client(_VALID))
    result, usage = await generate_insight({"month": "2026-05"})
    assert result["summary"].startswith("이번 달")
    assert result["highlights"][0]["type"] == "top_growth"
    assert usage.input_tokens == 300


async def test_generate_insight_malformed_json_raises(monkeypatch):
    monkeypatch.setattr("app.insights.llm._client", lambda: _fake_client("not json"))
    with pytest.raises(InsightError):
        await generate_insight({"month": "2026-05"})


async def test_generate_insight_missing_keys_raises(monkeypatch):
    monkeypatch.setattr("app.insights.llm._client", lambda: _fake_client('{"summary": "x"}'))
    with pytest.raises(InsightError):
        await generate_insight({"month": "2026-05"})
```

- [ ] **Step 2: 실패 확인**

Run: `cd apps/api && uv run pytest tests/insights/test_llm.py -v`
Expected: FAIL — 모듈 없음.

- [ ] **Step 3: 구현** — `apps/api/app/insights/llm.py` (분류 llm.py의 _client/Usage/JSON 강제 패턴 차용):

```python
"""Claude Haiku 월간 인사이트 생성.

집계 수치를 받아 구조화 JSON(summary + highlights) 반환.
파싱/검증 실패 시 InsightError — 호출자(service)가 502로 변환.
"""
import json
from dataclasses import dataclass

import anthropic

from app.categorization.budget import HAIKU_MODEL_ID
from app.settings import settings


class InsightError(Exception):
    """LLM 호출/파싱/검증 실패."""


@dataclass
class Usage:
    input_tokens: int
    output_tokens: int


_ALLOWED_TYPES = {"top_growth", "anomaly", "saving_tip"}

_SYSTEM = (
    "당신은 한국 가계부의 월간 지출 데이터를 보고 인사이트를 만드는 분석가입니다. "
    "반드시 JSON만 응답하세요. 형식: "
    '{"summary": "<한 문장 요약>", "highlights": [{"type": "top_growth|anomaly|saving_tip", '
    '"title": "<짧은 제목>", "detail": "<구체 설명>"}]}. '
    "highlights는 1~3개. type은 top_growth(가장 늘어난 카테고리), "
    "anomaly(이상 지출), saving_tip(절약 제안) 중 하나. 다른 문자 없이 JSON만."
)


def _client() -> anthropic.AsyncAnthropic:
    """Factory — tests monkeypatch this to inject mock."""
    return anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)


def _validate(parsed: object) -> dict:
    if not isinstance(parsed, dict):
        raise InsightError("expected JSON object")
    if "summary" not in parsed or "highlights" not in parsed:
        raise InsightError("missing summary/highlights")
    if not isinstance(parsed["highlights"], list):
        raise InsightError("highlights must be a list")
    for h in parsed["highlights"]:
        if not isinstance(h, dict) or h.get("type") not in _ALLOWED_TYPES:
            raise InsightError(f"invalid highlight: {h!r}")
        if "title" not in h or "detail" not in h:
            raise InsightError("highlight missing title/detail")
    return parsed


async def generate_insight(aggregates: dict) -> tuple[dict, Usage]:
    client = _client()
    user_content = (
        f"다음은 {aggregates.get('month')} 월 지출 집계입니다(JSON). "
        f"이를 바탕으로 인사이트를 생성하세요.\n{json.dumps(aggregates, ensure_ascii=False, default=str)}"
    )
    msg = await client.messages.create(
        model=HAIKU_MODEL_ID,
        max_tokens=512,
        system=_SYSTEM,
        messages=[{"role": "user", "content": user_content}],
    )
    text = "".join(block.text for block in msg.content if hasattr(block, "text"))
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise InsightError(f"non-JSON response: {text[:200]}") from exc

    validated = _validate(parsed)
    return validated, Usage(
        input_tokens=msg.usage.input_tokens,
        output_tokens=msg.usage.output_tokens,
    )
```

`apps/api/app/insights/__init__.py`와 `apps/api/tests/insights/__init__.py`는 빈 파일로 생성.

- [ ] **Step 4: 통과 확인**

Run: `cd apps/api && uv run pytest tests/insights/test_llm.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/insights/__init__.py apps/api/app/insights/llm.py apps/api/tests/insights/__init__.py apps/api/tests/insights/test_llm.py
git commit -m "feat(api): insights LLM module (structured highlights)"
```

---

### Task 10: insights/service.py — 집계 수집 + 캐시 오케스트레이션

**Files:**
- Create: `apps/api/app/insights/service.py`
- Test: `apps/api/tests/insights/test_service.py`

- [ ] **Step 1: 실패 테스트 작성**

```python
from uuid import uuid4

import pytest

from app.insights import service
from app.insights.llm import InsightError


async def _user(conn):
    row = await conn.fetchrow(
        "INSERT INTO users (email, password_hash) VALUES ($1,'x') RETURNING id",
        f"_w4-isvc-{uuid4()}@example.com",
    )
    return row["id"]


async def test_get_cached_returns_none_when_absent(test_db_pool):
    async with test_db_pool.acquire() as conn:
        uid = await _user(conn)
        result = await service.get_cached(conn, uid, "2026-05")
    assert result is None


async def test_generate_caches_and_get_cached_returns(test_db_pool, monkeypatch):
    # budget room 보장 + LLM mock
    monkeypatch.setattr("app.insights.service.budget.has_room", _async_true)
    monkeypatch.setattr(
        "app.insights.service.llm.generate_insight",
        _fake_generate,
    )
    monkeypatch.setattr("app.insights.service.budget.record_usage", _async_noop)

    async with test_db_pool.acquire() as conn:
        uid = await _user(conn)
        out = await service.generate(conn, uid, "2026-05", force=False)
        assert out["summary"] == "요약"
        cached = await service.get_cached(conn, uid, "2026-05")
        assert cached is not None
        assert cached["month"] == "2026-05"


async def test_generate_budget_exceeded_raises(test_db_pool, monkeypatch):
    monkeypatch.setattr("app.insights.service.budget.has_room", _async_false)
    async with test_db_pool.acquire() as conn:
        uid = await _user(conn)
        with pytest.raises(service.BudgetExceeded):
            await service.generate(conn, uid, "2026-05", force=False)


# --- helpers ---
async def _async_true():
    return True


async def _async_false():
    return False


async def _async_noop(**kwargs):
    return None


async def _fake_generate(aggregates):
    from app.insights.llm import Usage
    return (
        {"summary": "요약", "highlights": [{"type": "saving_tip", "title": "t", "detail": "d"}]},
        Usage(input_tokens=10, output_tokens=5),
    )
```

- [ ] **Step 2: 실패 확인**

Run: `cd apps/api && uv run pytest tests/insights/test_service.py -v`
Expected: FAIL — 모듈/심볼 없음.

- [ ] **Step 3: 구현** — `apps/api/app/insights/service.py`:

```python
"""월간 인사이트 오케스트레이터.

흐름: 캐시 조회 → (force or miss) 예산 체크 → 집계 수집 → LLM → 캐시 UPSERT.
캐시는 monthly_insights(user_id, month) PK. payload는 jsonb.
"""
import json
from uuid import UUID

import asyncpg

from app.categorization import budget
from app.dashboard import service as dash
from app.insights import llm


class BudgetExceeded(Exception):
    """월간 LLM 예산 초과 — 라우터에서 503."""


async def get_cached(conn: asyncpg.Connection, user_id: UUID, month: str) -> dict | None:
    row = await conn.fetchrow(
        "SELECT payload, generated_at FROM monthly_insights WHERE user_id = $1 AND month = $2",
        user_id, month,
    )
    if row is None:
        return None
    payload = row["payload"]
    if isinstance(payload, str):
        payload = json.loads(payload)
    return {
        "month": month,
        "summary": payload["summary"],
        "highlights": payload["highlights"],
        "generated_at": row["generated_at"],
    }


async def _collect_aggregates(conn: asyncpg.Connection, user_id: UUID, month: str) -> dict:
    summary = await dash.summary(conn, user_id, month)
    by_category = await dash.by_category(conn, user_id, month)
    top_merchants = await dash.top_merchants(conn, user_id, month, limit=5)
    by_essential = await dash.by_essential(conn, user_id, month)
    return {
        "month": month,
        "summary": summary,
        "by_category": by_category,
        "top_merchants": top_merchants,
        "by_essential": by_essential,
    }


async def generate(
    conn: asyncpg.Connection, user_id: UUID, month: str, *, force: bool
) -> dict:
    dash.validate_month(month)  # raises ValueError → 라우터 400
    if not force:
        cached = await get_cached(conn, user_id, month)
        if cached is not None:
            return cached

    if not await budget.has_room():
        raise BudgetExceeded()

    aggregates = await _collect_aggregates(conn, user_id, month)
    result, usage = await llm.generate_insight(aggregates)  # InsightError → 라우터 502

    payload = {"summary": result["summary"], "highlights": result["highlights"]}
    row = await conn.fetchrow(
        """
        INSERT INTO monthly_insights (user_id, month, payload)
        VALUES ($1, $2, $3::jsonb)
        ON CONFLICT (user_id, month)
        DO UPDATE SET payload = EXCLUDED.payload, generated_at = now()
        RETURNING generated_at
        """,
        user_id, month, json.dumps(payload, ensure_ascii=False),
    )
    await budget.record_usage(
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        merchant=f"insight:{month}",
        purpose="insight",
    )
    return {
        "month": month,
        "summary": payload["summary"],
        "highlights": payload["highlights"],
        "generated_at": row["generated_at"],
    }
```

- [ ] **Step 4: 통과 확인**

Run: `cd apps/api && uv run pytest tests/insights/test_service.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/insights/service.py apps/api/tests/insights/test_service.py
git commit -m "feat(api): insights service (collect aggregates + cache + budget guard)"
```

---

### Task 11: insights/routes.py + schemas.py + 라우터 등록

**Files:**
- Create: `apps/api/app/insights/schemas.py`
- Create: `apps/api/app/insights/routes.py`
- Modify: `apps/api/app/main.py` (라우터 등록)
- Test: `apps/api/tests/insights/test_routes.py`

- [ ] **Step 1: 실패 테스트 작성**

```python
from uuid import uuid4

import httpx
from httpx import ASGITransport

from app.main import app


async def _client():
    return httpx.AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    )


async def _signup(ac):
    email = f"_w4-iroute-{uuid4()}@example.com"
    r = await ac.post("/auth/signup", json={"email": email, "password": "abcd1234"})
    return r.json()["access_token"], email


def _patch_llm(monkeypatch):
    from app.insights.llm import Usage

    async def fake(aggregates):
        return (
            {"summary": "요약", "highlights": [{"type": "saving_tip", "title": "t", "detail": "d"}]},
            Usage(input_tokens=10, output_tokens=5),
        )

    async def room():
        return True

    async def noop(**kwargs):
        return None

    monkeypatch.setattr("app.insights.service.llm.generate_insight", fake)
    monkeypatch.setattr("app.insights.service.budget.has_room", room)
    monkeypatch.setattr("app.insights.service.budget.record_usage", noop)


async def test_get_insights_returns_null_when_absent(test_db_pool):
    async with await _client() as ac:
        token, _ = await _signup(ac)
        r = await ac.get("/insights?month=2026-05",
                         headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json() is None


async def test_generate_then_get(test_db_pool, monkeypatch):
    _patch_llm(monkeypatch)
    async with await _client() as ac:
        token, _ = await _signup(ac)
        p = await ac.post("/insights/generate", json={"month": "2026-05"},
                          headers={"Authorization": f"Bearer {token}"})
        assert p.status_code == 200, p.text
        assert p.json()["summary"] == "요약"

        g = await ac.get("/insights?month=2026-05",
                         headers={"Authorization": f"Bearer {token}"})
        assert g.json()["highlights"][0]["type"] == "saving_tip"


async def test_generate_budget_exceeded_503(test_db_pool, monkeypatch):
    async def no_room():
        return False
    monkeypatch.setattr("app.insights.service.budget.has_room", no_room)
    async with await _client() as ac:
        token, _ = await _signup(ac)
        r = await ac.post("/insights/generate", json={"month": "2026-05"},
                          headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 503
        assert r.json()["detail"] == "BUDGET_EXCEEDED"


async def test_generate_llm_failure_502(test_db_pool, monkeypatch):
    from app.insights.llm import InsightError

    async def boom(aggregates):
        raise InsightError("bad")
    async def room():
        return True
    monkeypatch.setattr("app.insights.service.llm.generate_insight", boom)
    monkeypatch.setattr("app.insights.service.budget.has_room", room)
    async with await _client() as ac:
        token, _ = await _signup(ac)
        r = await ac.post("/insights/generate", json={"month": "2026-05"},
                          headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 502
        assert r.json()["detail"] == "INSIGHT_GENERATION_FAILED"
```

- [ ] **Step 2: 실패 확인**

Run: `cd apps/api && uv run pytest tests/insights/test_routes.py -v`
Expected: FAIL — 404 (라우터 미등록).

- [ ] **Step 3: schemas 작성** — `apps/api/app/insights/schemas.py`:

```python
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class InsightHighlight(BaseModel):
    type: Literal["top_growth", "anomaly", "saving_tip"]
    title: str
    detail: str


class InsightResponse(BaseModel):
    month: str
    summary: str
    highlights: list[InsightHighlight]
    generated_at: datetime


class InsightGenerateRequest(BaseModel):
    month: str
```

- [ ] **Step 4: routes 작성** — `apps/api/app/insights/routes.py`:

```python
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.auth.deps import current_user_id
from app.db import acquire
from app.insights import service
from app.insights.llm import InsightError
from app.insights.schemas import InsightGenerateRequest, InsightResponse

router = APIRouter(prefix="/insights", tags=["insights"])


@router.get("", response_model=InsightResponse | None)
async def get_insight(
    month: str,
    user_id: UUID = Depends(current_user_id),  # noqa: B008
) -> InsightResponse | None:
    async with acquire() as conn:
        cached = await service.get_cached(conn, user_id, month)
    return InsightResponse(**cached) if cached else None


@router.post("/generate", response_model=InsightResponse)
async def generate_insight_route(
    req: InsightGenerateRequest,
    force: bool = False,
    user_id: UUID = Depends(current_user_id),  # noqa: B008
) -> InsightResponse:
    try:
        async with acquire() as conn:
            data = await service.generate(conn, user_id, req.month, force=force)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="INVALID_MONTH_FORMAT") from exc
    except service.BudgetExceeded as exc:
        raise HTTPException(status_code=503, detail="BUDGET_EXCEEDED") from exc
    except InsightError as exc:
        raise HTTPException(status_code=502, detail="INSIGHT_GENERATION_FAILED") from exc
    return InsightResponse(**data)
```

- [ ] **Step 5: main.py 라우터 등록** — `apps/api/app/main.py`에 import + include:

```python
from app.insights.routes import router as insights_router
...
app.include_router(insights_router)
```

- [ ] **Step 6: 통과 확인 + 전체 백엔드 회귀**

Run: `cd apps/api && uv run pytest -q`
Expected: 신규 insights 4 PASS + 전체 백엔드 PASS.

- [ ] **Step 7: Commit**

```bash
git add apps/api/app/insights/schemas.py apps/api/app/insights/routes.py apps/api/app/main.py apps/api/tests/insights/test_routes.py
git commit -m "feat(api): insights routes (GET cache, POST generate) + register router"
```

---

## Phase 6 — 프론트: API 클라이언트 + B+ 위젯

### Task 12: lib/api.ts — 타입/함수 추가 + TransactionRow essential 필드 교체

**Files:**
- Modify: `apps/web/src/lib/api.ts`
- Test: (이 태스크는 타입/함수만 — 컴포넌트 테스트는 Task 13에서)

- [ ] **Step 1: TransactionRow 필드 교체** — `apps/web/src/lib/api.ts`의 TransactionRow에서 `essential?`/`essential_reason?` 두 줄 제거 후:

```typescript
  essential_override?: boolean | null;
  effective_essential?: boolean;
```

- [ ] **Step 2: SummaryResponse 확장 + 신규 타입/함수 추가** — `MonthBucket`/`fetchByMonth`를 제거하고 cashflow로 교체, essential/insight 추가:

```typescript
export type SummaryResponse = {
  month: string;
  total_amount: string;
  transaction_count: number;
  prev_month: string;
  prev_month_total: string;
  prev_month_diff_pct: number | null;
  income_total: string;
  net_savings: string;
  savings_rate: number | null;
};
export type CategoryBucket = { category: string; amount: string; count: number };
export type CashflowBucket = { month: string; expense: string; income: string };
export type MerchantBucket = { merchant_raw: string; amount: string; count: number };
export type EssentialBucket = { essential: boolean; amount: string; count: number };

export type InsightHighlight = {
  type: "top_growth" | "anomaly" | "saving_tip";
  title: string;
  detail: string;
};
export type InsightResponse = {
  month: string;
  summary: string;
  highlights: InsightHighlight[];
  generated_at: string;
};

export async function fetchCashflowByMonth(lastN: number = 6): Promise<CashflowBucket[]> {
  const { data } = await api.get<CashflowBucket[]>(`/dashboard/cashflow-by-month?last_n=${lastN}`);
  return data;
}
export async function fetchByEssential(month: string): Promise<EssentialBucket[]> {
  const { data } = await api.get<EssentialBucket[]>(`/dashboard/by-essential?month=${month}`);
  return data;
}
export async function fetchInsight(month: string): Promise<InsightResponse | null> {
  const { data } = await api.get<InsightResponse | null>(`/insights?month=${month}`);
  return data;
}
export async function generateInsight(month: string, force = false): Promise<InsightResponse> {
  const { data } = await api.post<InsightResponse>(`/insights/generate?force=${force}`, { month });
  return data;
}
export async function patchEssential(id: string, essentialOverride: boolean | null): Promise<void> {
  await api.patch(`/transactions/${id}/essential`, { essential_override: essentialOverride });
}
```

(기존 `fetchByMonth`/`MonthBucket` 제거. `fetchSummary`/`fetchByCategory`/`fetchTopMerchants`는 유지.)

- [ ] **Step 3: 타입체크**

Run: `cd apps/web && pnpm tsc --noEmit`
Expected: dashboard.tsx가 아직 `fetchByMonth`/`MonthBucket`를 참조하므로 에러 — Task 13에서 해소. (이 단계는 api.ts 자체에 문법 오류 없는지만 확인; 에러가 dashboard.tsx 한정인지 확인.)

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/lib/api.ts
git commit -m "feat(web): api client — cashflow/by-essential/insights + essential fields"
```

---

### Task 13: B+ 위젯 컴포넌트 추출 + dashboard 조립

**Files:**
- Create: `apps/web/src/components/InsightCard.tsx` (+ `.test.tsx`)
- Create: `apps/web/src/components/MetricStrip.tsx` (+ `.test.tsx`)
- Create: `apps/web/src/components/CashflowChart.tsx`
- Create: `apps/web/src/components/EssentialDonut.tsx`
- Modify: `apps/web/src/routes/dashboard.tsx`
- Modify (필요 시): `apps/web/tailwind.config.*` (emerald 색이 safelist에 없으면 추가)

- [ ] **Step 1: MetricStrip 실패 테스트** — `apps/web/src/components/MetricStrip.test.tsx`

```typescript
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MetricStrip } from "./MetricStrip";

const summary = {
  month: "2026-05",
  total_amount: "30000",
  transaction_count: 2,
  prev_month: "2026-04",
  prev_month_total: "20000",
  prev_month_diff_pct: 50,
  income_total: "100000",
  net_savings: "70000",
  savings_rate: 70,
};

describe("MetricStrip", () => {
  it("renders four metrics with savings rate", () => {
    render(<MetricStrip summary={summary as any} />);
    expect(screen.getByText(/지출 총액/)).toBeInTheDocument();
    expect(screen.getByText(/수입 총액/)).toBeInTheDocument();
    expect(screen.getByText(/순저축/)).toBeInTheDocument();
    expect(screen.getByText("70.0%")).toBeInTheDocument();
  });

  it("shows dash when savings_rate is null", () => {
    render(<MetricStrip summary={{ ...summary, savings_rate: null } as any} />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: 실패 확인**

Run: `cd apps/web && pnpm vitest run src/components/MetricStrip.test.tsx`
Expected: FAIL — 모듈 없음.

- [ ] **Step 3: MetricStrip 구현** — `apps/web/src/components/MetricStrip.tsx`:

```typescript
import { Card, Text, Metric } from "@tremor/react";
import type { SummaryResponse } from "../lib/api";

function won(s: string): string {
  return `₩${Number(s).toLocaleString()}`;
}

export function MetricStrip({ summary }: { summary: SummaryResponse }) {
  const diff = summary.prev_month_diff_pct;
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      <Card>
        <Text>지출 총액</Text>
        <Metric>{won(summary.total_amount)}</Metric>
        {diff !== null && (
          <Text className="text-zinc-400 mt-1">
            전월 대비 {diff > 0 ? "+" : ""}{diff.toFixed(1)}%
          </Text>
        )}
      </Card>
      <Card>
        <Text>수입 총액</Text>
        <Metric>{won(summary.income_total)}</Metric>
      </Card>
      <Card>
        <Text>순저축</Text>
        <Metric>{won(summary.net_savings)}</Metric>
      </Card>
      <Card>
        <Text>저축률</Text>
        <Metric>{summary.savings_rate !== null ? `${summary.savings_rate.toFixed(1)}%` : "—"}</Metric>
      </Card>
    </div>
  );
}
```

- [ ] **Step 4: MetricStrip 통과 확인**

Run: `cd apps/web && pnpm vitest run src/components/MetricStrip.test.tsx`
Expected: 2 passed.

- [ ] **Step 5: InsightCard 실패 테스트** — `apps/web/src/components/InsightCard.test.tsx`

```typescript
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

const { fetchMock, genMock } = vi.hoisted(() => ({
  fetchMock: vi.fn(),
  genMock: vi.fn(),
}));
vi.mock("../lib/api", () => ({ fetchInsight: fetchMock, generateInsight: genMock }));

import { InsightCard } from "./InsightCard";

describe("InsightCard", () => {
  beforeEach(() => {
    fetchMock.mockReset();
    genMock.mockReset();
  });

  it("shows generate button when no cached insight", async () => {
    fetchMock.mockResolvedValueOnce(null);
    render(<InsightCard month="2026-05" />);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /인사이트 생성/ })).toBeInTheDocument(),
    );
  });

  it("renders highlights after generate", async () => {
    fetchMock.mockResolvedValueOnce(null);
    genMock.mockResolvedValueOnce({
      month: "2026-05",
      summary: "요약입니다",
      highlights: [{ type: "saving_tip", title: "팁", detail: "내용" }],
      generated_at: "2026-06-10T00:00:00Z",
    });
    render(<InsightCard month="2026-05" />);
    await waitFor(() => screen.getByRole("button", { name: /인사이트 생성/ }));
    fireEvent.click(screen.getByRole("button", { name: /인사이트 생성/ }));
    await waitFor(() => expect(screen.getByText("요약입니다")).toBeInTheDocument());
    expect(screen.getByText("팁")).toBeInTheDocument();
  });

  it("shows budget error on 503", async () => {
    fetchMock.mockResolvedValueOnce(null);
    genMock.mockRejectedValueOnce({ response: { status: 503 } });
    render(<InsightCard month="2026-05" />);
    await waitFor(() => screen.getByRole("button", { name: /인사이트 생성/ }));
    fireEvent.click(screen.getByRole("button", { name: /인사이트 생성/ }));
    await waitFor(() =>
      expect(screen.getByText(/예산/)).toBeInTheDocument(),
    );
  });
});
```

- [ ] **Step 6: 실패 확인**

Run: `cd apps/web && pnpm vitest run src/components/InsightCard.test.tsx`
Expected: FAIL — 모듈 없음.

- [ ] **Step 7: InsightCard 구현** — `apps/web/src/components/InsightCard.tsx`:

```typescript
import { useEffect, useState } from "react";
import { Card, Title, Text } from "@tremor/react";
import { fetchInsight, generateInsight, type InsightResponse } from "../lib/api";

const TYPE_LABEL: Record<string, string> = {
  top_growth: "📈 급증",
  anomaly: "⚠️ 이상",
  saving_tip: "💡 절약 팁",
};

export function InsightCard({ month }: { month: string }) {
  const [insight, setInsight] = useState<InsightResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!month) return;
    setError(null);
    fetchInsight(month).then(setInsight).catch(() => setInsight(null));
  }, [month]);

  async function onGenerate() {
    setLoading(true);
    setError(null);
    try {
      setInsight(await generateInsight(month));
    } catch (e: any) {
      setError(
        e?.response?.status === 503
          ? "이번 달 LLM 예산을 초과했습니다. 나중에 다시 시도하세요."
          : "인사이트 생성에 실패했습니다.",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card>
      <div className="flex items-center justify-between">
        <Title>월간 인사이트</Title>
        <button
          onClick={onGenerate}
          disabled={loading}
          className="bg-blue-700 text-white text-xs px-3 py-1 rounded disabled:opacity-50"
        >
          {loading ? "생성 중…" : insight ? "다시 생성" : "인사이트 생성"}
        </button>
      </div>
      {error && <Text className="text-red-400 mt-2">{error}</Text>}
      {insight && (
        <div className="mt-3 space-y-2">
          <Text className="text-zinc-200">{insight.summary}</Text>
          <ul className="space-y-1">
            {insight.highlights.map((h, i) => (
              <li key={i} className="text-sm text-zinc-300">
                <span className="text-zinc-400">{TYPE_LABEL[h.type] ?? h.type}</span>{" "}
                <b>{h.title}</b> — {h.detail}
              </li>
            ))}
          </ul>
        </div>
      )}
      {!insight && !error && (
        <Text className="text-zinc-500 mt-2">버튼을 눌러 이번 달 지출 인사이트를 생성하세요.</Text>
      )}
    </Card>
  );
}
```

- [ ] **Step 8: InsightCard 통과 확인**

Run: `cd apps/web && pnpm vitest run src/components/InsightCard.test.tsx`
Expected: 3 passed.

- [ ] **Step 9: CashflowChart + EssentialDonut 구현** (단순 표시 컴포넌트 — 스냅샷 테스트 생략, dashboard 통합 시 확인)

`apps/web/src/components/CashflowChart.tsx`:

```typescript
import { Card, Title, LineChart } from "@tremor/react";
import type { CashflowBucket } from "../lib/api";

export function CashflowChart({ data }: { data: CashflowBucket[] }) {
  return (
    <Card>
      <Title>월별 추세 — 지출 vs 수입</Title>
      <LineChart
        data={data.map((d) => ({
          month: d.month,
          지출: Number(d.expense),
          수입: Number(d.income),
        }))}
        index="month"
        categories={["지출", "수입"]}
        valueFormatter={(v) => `₩${v.toLocaleString()}`}
        colors={["cyan", "emerald"]}
      />
    </Card>
  );
}
```

`apps/web/src/components/EssentialDonut.tsx`:

```typescript
import { Card, Title, DonutChart } from "@tremor/react";
import type { EssentialBucket } from "../lib/api";

export function EssentialDonut({ data }: { data: EssentialBucket[] }) {
  return (
    <Card>
      <Title>필수 vs 비필수</Title>
      <DonutChart
        data={data.map((b) => ({
          name: b.essential ? "필수" : "비필수",
          value: Number(b.amount),
        }))}
        category="value"
        index="name"
        valueFormatter={(v) => `₩${v.toLocaleString()}`}
        colors={["emerald", "amber"]}
      />
    </Card>
  );
}
```

> Tremor 색이 W3 tailwind safelist에 없으면(`emerald`) 추가해야 차트가 보임. `apps/web/tailwind.config.*`의 safelist에 W3에서 등록한 색 목록을 확인하고 `emerald`/`amber`/`cyan`이 포함되는지 검증. 누락 시 추가.

- [ ] **Step 10: dashboard.tsx B+ 조립** — `fetchByMonth`→`fetchCashflowByMonth`, `fetchByEssential` 추가, 위젯을 B+ 순서로 재배치:

```typescript
import { useEffect, useState } from "react";
import { Card, DonutChart, Title } from "@tremor/react";
import {
  fetchMonths,
  fetchSummary,
  fetchByCategory,
  fetchCashflowByMonth,
  fetchTopMerchants,
  fetchByEssential,
  type SummaryResponse,
  type CategoryBucket,
  type CashflowBucket,
  type MerchantBucket,
  type EssentialBucket,
} from "../lib/api";
import { InsightCard } from "../components/InsightCard";
import { MetricStrip } from "../components/MetricStrip";
import { CashflowChart } from "../components/CashflowChart";
import { EssentialDonut } from "../components/EssentialDonut";

export function DashboardPage() {
  const [months, setMonths] = useState<string[]>([]);
  const [month, setMonth] = useState<string>("");
  const [summary, setSummary] = useState<SummaryResponse | null>(null);
  const [byCategory, setByCategory] = useState<CategoryBucket[]>([]);
  const [cashflow, setCashflow] = useState<CashflowBucket[]>([]);
  const [topMerchants, setTopMerchants] = useState<MerchantBucket[]>([]);
  const [byEssential, setByEssential] = useState<EssentialBucket[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchMonths()
      .then((ms) => {
        setMonths(ms);
        if (ms.length > 0) setMonth(ms[0]);
        else setLoading(false);
      })
      .catch(() => {
        setError("월 목록을 불러올 수 없습니다.");
        setLoading(false);
      });
  }, []);

  useEffect(() => {
    if (!month) return;
    setLoading(true);
    setError(null);
    Promise.all([
      fetchSummary(month),
      fetchByCategory(month),
      fetchCashflowByMonth(6),
      fetchTopMerchants(month, 5),
      fetchByEssential(month),
    ])
      .then(([s, c, cf, t, e]) => {
        setSummary(s);
        setByCategory(c);
        setCashflow(cf);
        setTopMerchants(t);
        setByEssential(e);
      })
      .catch(() => setError("대시보드 데이터를 불러오는 중 오류가 발생했습니다."))
      .finally(() => setLoading(false));
  }, [month]);

  if (months.length === 0 && !loading) {
    return (
      <div className="p-8 text-zinc-400">
        아직 거래가 없습니다. /app에서 명세서를 업로드하세요.
      </div>
    );
  }

  return (
    <div className="p-6 space-y-4">
      {error && (
        <div role="alert" className="bg-red-900/30 border border-red-700 text-red-200 text-sm rounded p-3">
          {error}
        </div>
      )}
      <div className="flex items-center gap-3">
        <select
          value={month}
          onChange={(e) => setMonth(e.target.value)}
          className="bg-zinc-900 border border-zinc-700 rounded px-2 py-1 text-sm"
          aria-label="월 선택"
        >
          {months.map((m) => (
            <option key={m} value={m}>{m}</option>
          ))}
        </select>
      </div>

      {loading ? (
        <p className="text-zinc-400 text-sm">로딩…</p>
      ) : (
        <div className="space-y-4">
          {month && <InsightCard month={month} />}
          {summary && <MetricStrip summary={summary} />}
          <CashflowChart data={cashflow} />
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Card>
              <Title>카테고리별 지출</Title>
              <DonutChart
                data={byCategory.map((c) => ({ name: c.category, value: Number(c.amount) }))}
                category="value"
                index="name"
                valueFormatter={(v) => `₩${v.toLocaleString()}`}
                colors={[
                  "cyan", "amber", "rose", "lime", "violet",
                  "orange", "blue", "fuchsia", "emerald", "indigo",
                  "yellow", "pink", "teal", "sky", "purple",
                  "green", "red", "slate", "gray",
                ]}
              />
            </Card>
            <EssentialDonut data={byEssential} />
          </div>
          <Card>
            <Title>Top 5 가맹점</Title>
            <ul className="text-sm text-zinc-300 space-y-1 mt-2">
              {topMerchants.length === 0 ? (
                <li className="text-zinc-500">데이터 없음</li>
              ) : (
                topMerchants.map((t, i) => (
                  <li key={t.merchant_raw} className="flex justify-between">
                    <span>{i + 1}. {t.merchant_raw}</span>
                    <span>₩{Number(t.amount).toLocaleString()} ({t.count}건)</span>
                  </li>
                ))
              )}
            </ul>
          </Card>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 11: 타입체크 + 전체 web 테스트**

Run: `cd apps/web && pnpm tsc --noEmit && pnpm vitest run`
Expected: 타입 에러 0, 전체 테스트 PASS.

- [ ] **Step 12: Commit**

```bash
git add apps/web/src/components/InsightCard.tsx apps/web/src/components/InsightCard.test.tsx apps/web/src/components/MetricStrip.tsx apps/web/src/components/MetricStrip.test.tsx apps/web/src/components/CashflowChart.tsx apps/web/src/components/EssentialDonut.tsx apps/web/src/routes/dashboard.tsx
# tailwind.config 수정 시 함께 add
git commit -m "feat(web): B+ dashboard — InsightCard/MetricStrip/CashflowChart/EssentialDonut"
```

---

## Phase 7 — TransactionList 필수/비필수 토글

### Task 14: EssentialToggle 3-state 칩 + TransactionList 통합

**Files:**
- Create: `apps/web/src/components/EssentialToggle.tsx` (+ `.test.tsx`)
- Modify: `apps/web/src/components/TransactionList.tsx`

- [ ] **Step 1: 실패 테스트 작성** — `apps/web/src/components/EssentialToggle.test.tsx`

```typescript
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

const { patchMock } = vi.hoisted(() => ({ patchMock: vi.fn() }));
vi.mock("../lib/api", () => ({ patchEssential: patchMock }));

import { EssentialToggle } from "./EssentialToggle";

describe("EssentialToggle", () => {
  beforeEach(() => patchMock.mockReset());

  it("cycles 자동 → 필수 on click and patches true", async () => {
    patchMock.mockResolvedValueOnce(undefined);
    const onChange = vi.fn();
    render(
      <EssentialToggle
        transactionId="t1"
        override={null}
        effective={false}
        onChange={onChange}
      />,
    );
    fireEvent.click(screen.getByRole("button"));
    expect(onChange).toHaveBeenCalledWith(true);
    await waitFor(() => expect(patchMock).toHaveBeenCalledWith("t1", true));
  });

  it("cycles 필수 → 비필수 → 자동", async () => {
    patchMock.mockResolvedValue(undefined);
    const onChange = vi.fn();
    render(
      <EssentialToggle transactionId="t1" override={true} effective={true} onChange={onChange} />,
    );
    fireEvent.click(screen.getByRole("button"));
    expect(onChange).toHaveBeenCalledWith(false); // true → false
  });

  it("rolls back on failure", async () => {
    patchMock.mockRejectedValueOnce(new Error("net"));
    const onChange = vi.fn();
    render(
      <EssentialToggle transactionId="t1" override={null} effective={false} onChange={onChange} />,
    );
    fireEvent.click(screen.getByRole("button"));
    await waitFor(() => {
      expect(onChange).toHaveBeenNthCalledWith(1, true);
      expect(onChange).toHaveBeenNthCalledWith(2, null); // 롤백
    });
  });
});
```

- [ ] **Step 2: 실패 확인**

Run: `cd apps/web && pnpm vitest run src/components/EssentialToggle.test.tsx`
Expected: FAIL — 모듈 없음.

- [ ] **Step 3: 구현** — `apps/web/src/components/EssentialToggle.tsx`. 3-state 순환: `null`(자동) → `true`(필수) → `false`(비필수) → `null`:

```typescript
import { useState } from "react";
import { patchEssential } from "../lib/api";

type Override = boolean | null;

function next(o: Override): Override {
  if (o === null) return true;
  if (o === true) return false;
  return null;
}

type Props = {
  transactionId: string;
  override: Override;       // essential_override
  effective: boolean;       // effective_essential (자동 상태일 때 표시용)
  onChange: (next: Override) => void;
};

export function EssentialToggle({ transactionId, override, effective, onChange }: Props) {
  const [saving, setSaving] = useState(false);

  const label =
    override === true ? "필수"
    : override === false ? "비필수"
    : `자동(${effective ? "필수" : "비필수"})`;

  const cls =
    override === true ? "bg-emerald-700"
    : override === false ? "bg-amber-700"
    : "bg-zinc-700";

  async function onClick() {
    const target = next(override);
    const prev = override;
    setSaving(true);
    onChange(target); // 낙관적
    try {
      await patchEssential(transactionId, target);
    } catch {
      onChange(prev); // 롤백
    } finally {
      setSaving(false);
    }
  }

  return (
    <button
      onClick={onClick}
      disabled={saving}
      className={`${cls} text-white text-xs px-2 py-0.5 rounded disabled:opacity-50`}
      aria-label={`필수 여부: ${label}`}
    >
      {label}
    </button>
  );
}
```

- [ ] **Step 4: 통과 확인**

Run: `cd apps/web && pnpm vitest run src/components/EssentialToggle.test.tsx`
Expected: 3 passed.

- [ ] **Step 5: TransactionList 통합** — `apps/web/src/components/TransactionList.tsx`에 EssentialToggle를 행에 추가. 각 거래 행에서 CategoryChip 옆에 토글을 두고, 낙관적 상태 갱신은 기존 행 상태 업데이트 핸들러를 따른다(파일의 기존 onChange/상태 패턴 확인 후 `essential_override`/`effective_essential` 갱신). import 추가:

```typescript
import { EssentialToggle } from "./EssentialToggle";
```

행 렌더에 (CategoryChip 인접):

```typescript
<EssentialToggle
  transactionId={t.id}
  override={t.essential_override ?? null}
  effective={t.effective_essential ?? false}
  onChange={(ov) => updateRow(t.id, { essential_override: ov })}
/>
```

> `updateRow`는 TransactionList의 기존 행 갱신 함수명에 맞춰 교체. essential override만 바꾸면 effective는 서버 재조회 전까지 시각적으로 약간 어긋날 수 있으나(자동 표시), MVP 허용 — 다음 월 전환/재페치 시 정합.

- [ ] **Step 6: 타입체크 + 전체 web 테스트**

Run: `cd apps/web && pnpm tsc --noEmit && pnpm vitest run`
Expected: 타입 에러 0, 전체 PASS.

- [ ] **Step 7: Commit**

```bash
git add apps/web/src/components/EssentialToggle.tsx apps/web/src/components/EssentialToggle.test.tsx apps/web/src/components/TransactionList.tsx
git commit -m "feat(web): essential 3-state toggle in TransactionList"
```

---

## Phase 8 — 통합 검수 + 배포 문서

### Task 15: 전체 회귀 + 운영 배포 문서

**Files:**
- Modify/Create: `docs/` (운영 배포 노트, W3 패턴 따름)

- [ ] **Step 1: 전체 백엔드 테스트**

Run: `cd apps/api && uv run pytest -q`
Expected: 전부 PASS (W3 157 + W4 신규).

- [ ] **Step 2: 전체 프론트 테스트 + 타입 + 빌드**

Run: `cd apps/web && pnpm tsc --noEmit && pnpm vitest run && pnpm build`
Expected: 전부 PASS, 빌드 성공.

- [ ] **Step 3: 마이그레이션 운영 적용 확인**

deploy-api 워크플로 entrypoint가 `alembic upgrade head`로 0004를 자동 적용하는지 확인 (W3 0003 자동 적용 패턴). 수동 적용 필요 시 배포 노트에 기재.

- [ ] **Step 4: 로컬 수동 검수 (선택, browse 스킬)**

`/dashboard`에서: 인사이트 생성 버튼 → 하이라이트 표시, MetricStrip 4지표, 지출+수입 결합 라인, 필수/비필수 도넛 / `/app`에서: 거래 행 필수/비필수 토글 3-state 순환. 입금 거래가 있는 사용자(통장 중심)로 검증.

- [ ] **Step 5: 배포 문서 작성** — W3의 `docs/retros/w3.md` Phase 8 docs 패턴을 따라 W4 변경점(신규 엔드포인트, 0004 마이그레이션, 신규 의존성 없음) 기록.

- [ ] **Step 6: Commit**

```bash
git add docs/
git commit -m "chore(infra): W4 분석 고도화 — 배포 문서 + 검수 노트"
```

---

## 알려진 한계 (스펙 §알려진 한계 반영)
- 인사이트가 분류와 예산 버킷 공유 → 대량 생성 시 분류 예산 잠식 가능 (MVP 허용).
- 수입에 income/savings 카테고리 입금 포함(이체만 제외). 정교한 입금 구성 분석은 차후.
- `ESSENTIAL_DEFAULTS` 변경은 코드 배포 필요.
- essential 토글 낙관적 갱신 시 effective 표시가 재페치 전까지 약간 어긋날 수 있음.
