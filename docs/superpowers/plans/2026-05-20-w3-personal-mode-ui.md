# spendLens W3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** spendLens W3 — 본인 모드 UI 완성. 거래 리스트 필터·검색·인라인 카테고리 오버라이드 + 별도 `/dashboard` 페이지 (Tremor 4 위젯) + 카테고리 enum 14→19 확장 + 통장 룰북 보강.

**Architecture:** W2 stack 그대로. backend 인프라(Redis, Postgres, Caddy) 변경 없음. 신규 의존성은 frontend `@tremor/react` 1개. 신규 DB 컬럼 1개(`transactions.user_category_override`) + 신규 백엔드 도메인 모듈 `app/dashboard/`. `effective_category = COALESCE(user_category_override, category)` 패턴으로 자동 분류 결과 보존하면서 사용자 수정값 노출.

**Tech Stack:** FastAPI · asyncpg(raw SQL) · Alembic(raw SQL) · Redis · Anthropic SDK · React 18 + Vite + TypeScript + Tailwind + Zustand + **Tremor (@tremor/react)** · vitest + RTL · pytest + httpx ASGITransport · GitHub Actions → GHCR → Lightsail Docker Compose + Caddy.

**Related docs:**
- W3 spec: `docs/superpowers/specs/2026-05-20-w3-personal-mode-ui-design.md`
- W2 reference plan: `docs/superpowers/plans/2026-05-13-w2-multi-user-llm-categorization.md`
- Conventions: `CLAUDE.md` (root) + `apps/api/CLAUDE.md` if present

---

## Branching policy (W2와 동일)

- 매 Phase = 1 feature 브랜치 + 1 PR. 브랜치명: `feat/w3-phaseN-<slug>` (예: `feat/w3-phase1-patch-override`).
- 머지 방식: **GitHub UI 또는 gh CLI에서 Squash merge** (main에 squash commit 1개).
- 커밋 제목은 Conventional Commits (`feat(api):`, `feat(web):`, `chore(infra):`).
- main에 직접 push 금지 (W2부터 도입된 흐름).

---

## Phase 0: enum 19 + 마이그레이션 0003 + 통장 룰북 + LLM 프롬프트 (12 tasks)

**브랜치:** `feat/w3-phase0-enum-rulebook`
**목표:** categorization 핵심을 확장. 이 phase 머지 후엔 업로드된 거래의 통장 적요가 자동 분류되고(savings/insurance/income/transfer/housing), DB는 `user_category_override` 컬럼을 갖춤.

### Task 00: main 최신화 + Phase 0 브랜치 분기

**Files:** 없음 (git 작업)

- [ ] **Step 1:** main 최신화.

```bash
git checkout main
git pull --ff-only origin main
```

Expected: 최신 commit이 `912a511` (W3 spec docs commit) 또는 그 이후.

- [ ] **Step 2:** Phase 0 브랜치.

```bash
git checkout -b feat/w3-phase0-enum-rulebook
```

### Task 01: `CATEGORIES` 14→19 + 통장 5 룰 추가 (TDD)

**Files:**
- Modify: `apps/api/app/categorization/rulebook.py`
- Modify: `apps/api/tests/categorization/test_rulebook.py`

- [ ] **Step 1:** 현재 `tests/categorization/test_rulebook.py` 파일에 통장 매칭 케이스 추가. `@pytest.mark.parametrize` 안 케이스 목록 끝에 (`"EMART 잠실점", "groceries"` 다음 줄에) 다음 5줄 추가:

```python
        # W3 통장 룰북 추가
        ("[정기적금] 청년도약", "savings"),
        ("[CMS] 하나생02022", "insurance"),
        ("[타행이체] 수임월급", "income"),
        ("[타행이체] 정혜숙", "transfer"),
        ("[CMS] 월세-임대인", "housing"),
```

또한 `test_categories_enum_has_unknown_and_14_total` 테스트의 assertion을 변경:

```python
def test_categories_enum_has_unknown_and_19_total():
    assert "unknown" in CATEGORIES
    assert "savings" in CATEGORIES
    assert "insurance" in CATEGORIES
    assert "income" in CATEGORIES
    assert "transfer" in CATEGORIES
    assert "housing" in CATEGORIES
    assert len(CATEGORIES) == 19
```

(함수명을 `_19_total`로 변경한 것 — 옛 함수명 `_14_total` 삭제 잊지 말 것.)

- [ ] **Step 2:** Run test (expect FAIL — CATEGORIES 14개, 룰 미정의).

```bash
cd apps/api && uv run pytest tests/categorization/test_rulebook.py -v
```

Expected: FAIL — `len(CATEGORIES) == 14`이고 새 케이스 매칭 안 됨.

- [ ] **Step 3:** `apps/api/app/categorization/rulebook.py`의 `CATEGORIES` 튜플 끝에 추가:

```python
CATEGORIES: tuple[str, ...] = (
    "coffee", "lunch", "dinner", "snack_late",
    "groceries", "transport", "telecom",
    "subscription", "entertainment", "health",
    "shopping", "utilities", "etc", "unknown",
    # W3 추가
    "savings", "insurance", "income", "transfer", "housing",
)
```

또한 `_RULES` 리스트의 `shopping` 룰 다음 (마지막)에 5개 신규 룰 추가:

```python
    # W3 통장 룰 추가 (merchant_raw가 '[구분] 적요' 형태로 들어옴)
    (re.compile(r"정기적금|적금|예금", re.I), "savings"),
    (re.compile(r"CMS|보험|손해보험|하나생|화재", re.I), "insurance"),
    (re.compile(r"월급|급여|수익|수당", re.I), "income"),
    (re.compile(r"이체|송금|입금", re.I), "transfer"),
    (re.compile(r"월세|임대|관리비", re.I), "housing"),
```

- [ ] **Step 4:** Run test (expect PASS).

```bash
cd apps/api && uv run pytest tests/categorization/test_rulebook.py -v
```

Expected: 모든 케이스 PASS — 새 5 매칭 + `len == 19`.

### Task 02: LLM 시스템 프롬프트 enum 19개로 갱신

**Files:**
- Modify: `apps/api/app/categorization/llm.py`

- [ ] **Step 1:** `llm.py`를 열어 `_SYSTEM` 변수를 확인. 현재:

```python
_SYSTEM = (
    "당신은 한국 카드 거래의 가맹점명을 보고 카테고리를 정해주는 분류기입니다. "
    "다음 14개 중 정확히 하나를 JSON으로 답하세요: "
    f"{', '.join(CATEGORIES)}. "
    '응답 형식: {"category": "<enum>"}. 다른 문자 없이 JSON만.'
)
```

`f"{', '.join(CATEGORIES)}"`는 `CATEGORIES`가 19개로 늘면 자동 반영됨. 다만 "14개"라는 하드코딩 숫자가 잘못. 다음으로 교체:

```python
_SYSTEM = (
    "당신은 한국 카드 거래의 가맹점명 또는 통장 거래의 적요를 보고 카테고리를 정해주는 분류기입니다. "
    f"다음 {len(CATEGORIES)}개 중 정확히 하나를 JSON으로 답하세요: "
    f"{', '.join(CATEGORIES)}. "
    '응답 형식: {"category": "<enum>"}. 다른 문자 없이 JSON만.'
)
```

(`len(CATEGORIES)`로 자동 계산, 통장 거래 언급 추가.)

- [ ] **Step 2:** `tests/categorization/test_llm.py`가 여전히 통과하는지 확인.

```bash
cd apps/api && uv run pytest tests/categorization/test_llm.py -v
```

Expected: 4/4 PASS (mock 사용이라 _SYSTEM 변경 영향 없음).

### Task 03: 마이그레이션 0003 생성 + 적용

**Files:**
- Create: `apps/api/migrations/versions/0003_add_user_category_override.py`

- [ ] **Step 1:** Alembic skeleton 생성.

```bash
cd apps/api && uv run alembic revision -m "add user category override"
```

생성된 파일을 `0003_add_user_category_override.py`로 rename (파일명 + 안의 `revision` 변수).

- [ ] **Step 2:** 파일 내용을 다음으로 교체:

```python
"""add user category override

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-20
"""
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE transactions ADD COLUMN user_category_override TEXT NULL;")


def downgrade() -> None:
    op.execute("ALTER TABLE transactions DROP COLUMN user_category_override;")
```

- [ ] **Step 3:** Dev DB + test DB 적용.

```bash
cd apps/api
uv run alembic upgrade head
DATABASE_URL=$(grep ^DATABASE_URL tests/.env.test | cut -d= -f2-) uv run alembic upgrade head
```

Expected: 두 DB 모두 `transactions.user_category_override` 컬럼 추가됨.

- [ ] **Step 4:** psql 확인 (선택):

```bash
docker exec spendlens-local-redis-1 echo 'noop'  # docker exec 동작 확인용
psql "$DATABASE_URL" -c "\d transactions" | grep user_category_override
```

Expected: `user_category_override | text` 컬럼 표시.

### Task 04: `TransactionOut` 스키마에 effective_category 등 3 필드 추가 (TDD)

**Files:**
- Modify: `apps/api/app/transactions/schemas.py`
- Modify: `apps/api/tests/parsers/test_samsung_card_integration.py` (effective_category 필드 검증)

- [ ] **Step 1:** 현재 `apps/api/app/transactions/schemas.py`를 읽음.

```bash
cat apps/api/app/transactions/schemas.py
```

`TransactionOut`에는 현재 `category: str` 있음. 3개 필드 추가:

```python
class TransactionOut(BaseModel):
    id: str
    txn_date: date
    txn_time: time | None
    amount: Decimal
    merchant_raw: str
    merchant_normalized: str | None
    approval_no: str | None
    card_last4: str | None
    installment_months: int | None
    is_canceled: bool
    category: str
    # W3 추가
    auto_category: str               # 자동 분류 결과 (category와 동일하지만 명시적)
    user_category_override: str | None
    effective_category: str          # COALESCE(user_category_override, category)
    essential: bool | None
    essential_reason: str | None
```

또한 같은 파일에 신규 클래스 추가 (파일 끝):

```python
from typing import Literal

# 19 categories — keep in sync with app.categorization.rulebook.CATEGORIES
CategoryLiteral = Literal[
    "coffee", "lunch", "dinner", "snack_late",
    "groceries", "transport", "telecom",
    "subscription", "entertainment", "health",
    "shopping", "utilities", "etc", "unknown",
    "savings", "insurance", "income", "transfer", "housing",
]


class TransactionPatchRequest(BaseModel):
    category: CategoryLiteral
```

- [ ] **Step 2:** test `apps/api/tests/transactions/__init__.py` 존재 확인. 없으면 생성 (빈 파일).

```bash
test -f apps/api/tests/transactions/__init__.py || touch apps/api/tests/transactions/__init__.py
```

- [ ] **Step 3:** Create `apps/api/tests/transactions/test_schemas.py`:

```python
import pytest
from pydantic import ValidationError

from app.transactions.schemas import CategoryLiteral, TransactionPatchRequest


def test_patch_request_accepts_valid_category():
    req = TransactionPatchRequest(category="groceries")
    assert req.category == "groceries"


def test_patch_request_accepts_new_w3_categories():
    for cat in ("savings", "insurance", "income", "transfer", "housing"):
        req = TransactionPatchRequest(category=cat)
        assert req.category == cat


def test_patch_request_rejects_invalid_category():
    with pytest.raises(ValidationError):
        TransactionPatchRequest(category="totally_not_a_category")


def test_category_literal_has_19_options():
    import typing
    args = typing.get_args(CategoryLiteral)
    assert len(args) == 19
    assert "unknown" in args
    assert "savings" in args
```

- [ ] **Step 4:** Run.

```bash
cd apps/api && uv run pytest tests/transactions/test_schemas.py -v
```

Expected: 4/4 PASS.

### Task 05: 전체 회귀 + 통장 룰북 + Phase 0 commit + PR

**Files:** 없음 (verification + git)

- [ ] **Step 1:** 전체 테스트 회귀.

```bash
cd apps/api && uv run pytest -x
```

Expected: ALL PASS (116 + 4 신규 schemas = 120 또는 그 이상).

- [ ] **Step 2:** ruff 통과 확인.

```bash
cd apps/api && uv run ruff check
```

Expected: All checks passed!

- [ ] **Step 3:** git status + diff 확인.

```bash
git status --short
```

Expected:
- `M apps/api/app/categorization/rulebook.py`
- `M apps/api/app/categorization/llm.py`
- `M apps/api/app/transactions/schemas.py`
- `A apps/api/migrations/versions/0003_add_user_category_override.py`
- `M apps/api/tests/categorization/test_rulebook.py`
- `A apps/api/tests/transactions/test_schemas.py`
- (또는 `A apps/api/tests/transactions/__init__.py` 새로 만든 경우)

- [ ] **Step 4:** Commit + push + PR.

```bash
git add apps/api/app/categorization/rulebook.py \
        apps/api/app/categorization/llm.py \
        apps/api/app/transactions/schemas.py \
        apps/api/migrations/versions/0003_add_user_category_override.py \
        apps/api/tests/categorization/test_rulebook.py \
        apps/api/tests/transactions/test_schemas.py \
        apps/api/tests/transactions/__init__.py
git commit -m "feat(api): expand categories 14→19 + 통장 룰북 + user_category_override 컬럼

- CATEGORIES enum +5 (savings/insurance/income/transfer/housing)
- 통장 룰북 5 패턴 (정기적금/CMS·보험/월급/이체/월세)
- LLM 시스템 프롬프트가 자동으로 19 enum 사용 (len 동적)
- 마이그레이션 0003: transactions.user_category_override TEXT NULL
- TransactionOut에 auto_category / user_category_override / effective_category
- TransactionPatchRequest with CategoryLiteral (19개 Literal)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
git push -u origin feat/w3-phase0-enum-rulebook
gh pr create --title "feat(api): expand categories 14→19 + 통장 룰북 + override 컬럼" --body-file - <<'EOF'
## Summary
- enum 14 → 19 (savings/insurance/income/transfer/housing 추가)
- 통장 룰북 5 패턴 신규 (정기적금/CMS-보험/월급/이체/월세)
- LLM 시스템 프롬프트가 동적으로 19 enum 반영
- 마이그레이션 0003: `transactions.user_category_override TEXT NULL`
- `TransactionOut`에 auto_category / user_category_override / effective_category 노출
- `TransactionPatchRequest`(category: CategoryLiteral)

## Why
W3 핵심 인프라. 후속 Phase가 모두 이 19 enum과 override 컬럼에 의존.

W3 spec: docs/superpowers/specs/2026-05-20-w3-personal-mode-ui-design.md
W3 plan: Phase 0

## Test plan
- [x] test_rulebook.py — 19 카테고리 + 5 신규 패턴 케이스
- [x] test_schemas.py — TransactionPatchRequest Literal 검증
- [x] `uv run pytest -x` 회귀
- [x] `uv run ruff check` clean
- [x] dev + test DB에 0003 적용 완료
EOF
```

- [ ] **Step 5:** CI 통과 + Squash merge.

```bash
gh pr checks --watch
gh pr merge --squash --delete-branch --subject "feat(api): expand categories 14→19 + 통장 룰북 + override 컬럼 (#?)"
git checkout main && git pull --ff-only origin main
```

---

## Phase 1: `PATCH /transactions/{id}` 백엔드 (6 tasks)

**브랜치:** `feat/w3-phase1-patch-override`

### Task 06: 브랜치 분기 + service.update_category TDD

**Files:**
- Modify: `apps/api/app/transactions/service.py`
- Create: `apps/api/tests/transactions/test_update_category.py`

- [ ] **Step 1:**

```bash
git checkout main && git pull --ff-only origin main
git checkout -b feat/w3-phase1-patch-override
```

- [ ] **Step 2:** Create `apps/api/tests/transactions/test_update_category.py`:

```python
from uuid import UUID, uuid4

import pytest

from app.transactions.service import update_category


async def _insert_user(conn):
    row = await conn.fetchrow(
        "INSERT INTO users (email, password_hash) VALUES ($1, $2) RETURNING id",
        f"u-{uuid4()}@e.com",
        "$argon2id$v=19$m=65536,t=3,p=4$placeholder",
    )
    return row["id"]


async def _insert_txn(conn, user_id, category="unknown"):
    row = await conn.fetchrow(
        """
        INSERT INTO transactions (
          user_id, source_type, txn_date, amount, merchant_raw,
          category, dedup_hash, raw_row
        ) VALUES (
          $1, 'test', CURRENT_DATE, 1000, 'TEST MERCHANT',
          $2, $3, '{}'::jsonb
        ) RETURNING id
        """,
        user_id, category, str(uuid4()),
    )
    return row["id"]


async def test_update_category_sets_override(test_db_pool):
    async with test_db_pool.acquire() as conn:
        user_id = await _insert_user(conn)
        txn_id = await _insert_txn(conn, user_id)

        updated = await update_category(conn, user_id, txn_id, "groceries")
    assert updated is True

    async with test_db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT category, user_category_override FROM transactions WHERE id = $1",
            txn_id,
        )
    assert row["category"] == "unknown"  # auto 결과는 보존
    assert row["user_category_override"] == "groceries"


async def test_update_category_returns_false_for_other_user(test_db_pool):
    async with test_db_pool.acquire() as conn:
        user_a = await _insert_user(conn)
        user_b = await _insert_user(conn)
        txn_id = await _insert_txn(conn, user_a)

        updated = await update_category(conn, user_b, txn_id, "groceries")
    assert updated is False


async def test_update_category_returns_false_for_missing_id(test_db_pool):
    async with test_db_pool.acquire() as conn:
        user_id = await _insert_user(conn)
        updated = await update_category(conn, user_id, uuid4(), "groceries")
    assert updated is False
```

- [ ] **Step 3:** Run (expect FAIL — update_category 없음).

```bash
cd apps/api && uv run pytest tests/transactions/test_update_category.py -v
```

Expected: ImportError or `AttributeError`.

- [ ] **Step 4:** `apps/api/app/transactions/service.py` 파일 끝에 추가:

```python
async def update_category(
    conn: asyncpg.Connection,
    user_id: UUID,
    transaction_id: UUID,
    category: str,
) -> bool:
    """Set user_category_override for one transaction owned by user_id.

    Returns True if updated, False if not found or owned by different user.
    Caller must validate `category` is in CATEGORIES (Pydantic CategoryLiteral does this).
    """
    row = await conn.fetchrow(
        """
        UPDATE transactions
        SET user_category_override = $3
        WHERE id = $2 AND user_id = $1
        RETURNING id
        """,
        user_id, transaction_id, category,
    )
    return row is not None
```

`asyncpg`와 `UUID` import 이미 파일 상단에 있음 (W1부터). 확인 후 없으면 추가.

- [ ] **Step 5:** Run (expect PASS).

```bash
cd apps/api && uv run pytest tests/transactions/test_update_category.py -v
```

Expected: 3 PASS.

### Task 07: `PATCH /transactions/{id}` 라우트 TDD

**Files:**
- Create: `apps/api/tests/transactions/test_patch_override.py`
- Modify: `apps/api/app/transactions/routes.py`

- [ ] **Step 1:** Create `apps/api/tests/transactions/test_patch_override.py`:

```python
import httpx
from httpx import ASGITransport
from uuid import uuid4

from app.main import app


async def _client():
    return httpx.AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    )


async def _signup_and_token(ac):
    email = f"_w3-patch-{uuid4()}@example.com"
    r = await ac.post(
        "/auth/signup",
        json={"email": email, "password": "abcd1234"},
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


async def _create_txn(conn, user_email):
    row = await conn.fetchrow(
        "SELECT id FROM users WHERE email = $1", user_email
    )
    user_id = row["id"]
    txn_row = await conn.fetchrow(
        """
        INSERT INTO transactions (
          user_id, source_type, txn_date, amount, merchant_raw,
          category, dedup_hash, raw_row
        ) VALUES (
          $1, 'test', CURRENT_DATE, 1000, 'TEST',
          'unknown', $2, '{}'::jsonb
        ) RETURNING id
        """,
        user_id, str(uuid4()),
    )
    return txn_row["id"]


async def test_patch_updates_category(test_db_pool):
    async with await _client() as ac:
        token = await _signup_and_token(ac)
        async with test_db_pool.acquire() as conn:
            # signup 시 생성된 user의 이메일을 다시 가져오기 위해
            # token payload에서 user_id를 추출하는 것보다 직접 DB 조회
            users = await conn.fetch(
                "SELECT email FROM users ORDER BY created_at DESC LIMIT 1"
            )
            email = users[0]["email"]
            txn_id = await _create_txn(conn, email)

        r = await ac.patch(
            f"/transactions/{txn_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"category": "groceries"},
        )
    assert r.status_code == 204, r.text

    async with test_db_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT user_category_override FROM transactions WHERE id = $1",
            txn_id,
        )
    assert row["user_category_override"] == "groceries"


async def test_patch_rejects_invalid_category(test_db_pool):
    async with await _client() as ac:
        token = await _signup_and_token(ac)
        async with test_db_pool.acquire() as conn:
            users = await conn.fetch(
                "SELECT email FROM users ORDER BY created_at DESC LIMIT 1"
            )
            email = users[0]["email"]
            txn_id = await _create_txn(conn, email)

        r = await ac.patch(
            f"/transactions/{txn_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"category": "not_a_real_category"},
        )
    assert r.status_code == 422


async def test_patch_404_for_other_user_txn(test_db_pool):
    async with await _client() as ac:
        token_a = await _signup_and_token(ac)
        # 다른 사용자 transaction 생성
        async with test_db_pool.acquire() as conn:
            users = await conn.fetch(
                "SELECT email FROM users ORDER BY created_at DESC LIMIT 1"
            )
            email_a = users[0]["email"]
        # token_b 새 사용자
        token_b = await _signup_and_token(ac)
        async with test_db_pool.acquire() as conn:
            # user_a의 거래
            txn_id = await _create_txn(conn, email_a)

        # user_b로 user_a의 거래 PATCH 시도
        r = await ac.patch(
            f"/transactions/{txn_id}",
            headers={"Authorization": f"Bearer {token_b}"},
            json={"category": "coffee"},
        )
    assert r.status_code == 404
    assert r.json()["detail"] == "NOT_FOUND"


async def test_patch_404_for_unknown_id(test_db_pool):
    async with await _client() as ac:
        token = await _signup_and_token(ac)
        r = await ac.patch(
            f"/transactions/{uuid4()}",
            headers={"Authorization": f"Bearer {token}"},
            json={"category": "coffee"},
        )
    assert r.status_code == 404
```

- [ ] **Step 2:** Run (expect FAIL — route 없음).

```bash
cd apps/api && uv run pytest tests/transactions/test_patch_override.py -v
```

Expected: 405 Method Not Allowed 또는 404.

- [ ] **Step 3:** `apps/api/app/transactions/routes.py` 상단 imports에 추가:

```python
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.auth.deps import current_user_id
from app.db import acquire
from app.parsers import ParseError, detect
from app.transactions.schemas import (
    TransactionOut,
    TransactionPatchRequest,
    UploadResponse,
)
from app.transactions.service import insert_transactions, update_category
```

(기존 import에 `update_category`와 `TransactionPatchRequest` 추가.)

- [ ] **Step 4:** 파일 끝(`list_transactions` 함수 다음)에 PATCH 라우트 추가:

```python
@router.patch("/{transaction_id}", status_code=204)
async def patch_transaction(
    transaction_id: UUID,
    req: TransactionPatchRequest,
    user_id: UUID = Depends(current_user_id),  # noqa: B008
) -> None:
    async with acquire() as conn:
        updated = await update_category(conn, user_id, transaction_id, req.category)
    if not updated:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
```

- [ ] **Step 5:** Run (expect PASS).

```bash
cd apps/api && uv run pytest tests/transactions/test_patch_override.py -v
```

Expected: 4/4 PASS.

### Task 08: Phase 1 회귀 + Commit + PR

- [ ] **Step 1:**

```bash
cd apps/api && uv run pytest -x && uv run ruff check
```

Expected: ALL PASS.

- [ ] **Step 2:**

```bash
cd ../..
git add apps/api/app/transactions/service.py apps/api/app/transactions/routes.py apps/api/tests/transactions/test_update_category.py apps/api/tests/transactions/test_patch_override.py
git commit -m "feat(api): PATCH /transactions/{id} for user category override

- service.update_category(conn, user_id, transaction_id, category) — UPDATE WHERE user_id+id
- PATCH /transactions/{id} route — 204 No Content / 404 NOT_FOUND / 422 invalid enum
- TransactionPatchRequest(category: CategoryLiteral) — Pydantic v2 Literal로 19 enum 강제

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
git push -u origin feat/w3-phase1-patch-override
gh pr create --title "feat(api): PATCH /transactions/{id} for user category override" --body-file - <<'EOF'
## Summary
- `PATCH /transactions/{id}` body `{category}` — user_category_override 저장
- 19 enum 외 값 → 422 (Pydantic CategoryLiteral)
- 다른 사용자 거래 또는 미존재 id → 404 NOT_FOUND
- service.update_category 단위 테스트 3 + route 통합 테스트 4

## Test plan
- [x] test_update_category.py (3)
- [x] test_patch_override.py (4)
- [x] pytest -x 회귀
EOF
gh pr checks --watch
gh pr merge --squash --delete-branch --subject "feat(api): PATCH /transactions/{id} for user category override (#?)"
git checkout main && git pull --ff-only origin main
```

---

## Phase 2: `GET /transactions` 필터/검색/페이지네이션 + `/transactions/months` (8 tasks)

**브랜치:** `feat/w3-phase2-filter-search`

### Task 09: 브랜치 + FilterQuery 스키마 + months 라우트 TDD

**Files:**
- Create: `apps/api/tests/transactions/test_filter_query.py`
- Modify: `apps/api/app/transactions/schemas.py`
- Modify: `apps/api/app/transactions/routes.py`

- [ ] **Step 1:**

```bash
git checkout -b feat/w3-phase2-filter-search
```

- [ ] **Step 2:** `apps/api/app/transactions/schemas.py` 끝에 추가:

```python
from datetime import date as _date_cls


class TransactionFilter(BaseModel):
    """Query parameters for GET /transactions."""
    month: str | None = None       # 'YYYY-MM'
    category: str | None = None    # CSV: 'coffee,lunch'
    search: str | None = None      # ILIKE substring
    limit: int = 50
    offset: int = 0
```

(Pydantic v2 query model. limit ≤ 200 검증은 route에서.)

- [ ] **Step 3:** Create `apps/api/tests/transactions/test_filter_query.py`:

```python
import httpx
from httpx import ASGITransport
from uuid import uuid4

from app.main import app


async def _client():
    return httpx.AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    )


async def _signup_and_token(ac):
    email = f"_w3-filter-{uuid4()}@example.com"
    r = await ac.post("/auth/signup", json={"email": email, "password": "abcd1234"})
    assert r.status_code == 200
    return r.json()["access_token"], email


async def _seed_txn(conn, email, *, txn_date, amount, merchant, category="unknown"):
    user = await conn.fetchrow("SELECT id FROM users WHERE email = $1", email)
    user_id = user["id"]
    await conn.execute(
        """
        INSERT INTO transactions (
          user_id, source_type, txn_date, amount, merchant_raw,
          category, dedup_hash, raw_row
        ) VALUES ($1, 'test', $2, $3, $4, $5, $6, '{}'::jsonb)
        """,
        user_id, txn_date, amount, merchant, category, str(uuid4()),
    )


async def test_filter_by_month(test_db_pool):
    async with await _client() as ac:
        token, email = await _signup_and_token(ac)
        async with test_db_pool.acquire() as conn:
            await _seed_txn(conn, email, txn_date="2026-05-01", amount=1000, merchant="A")
            await _seed_txn(conn, email, txn_date="2026-04-15", amount=2000, merchant="B")

        r = await ac.get(
            "/transactions?month=2026-05",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["merchant_raw"] == "A"


async def test_filter_by_category(test_db_pool):
    async with await _client() as ac:
        token, email = await _signup_and_token(ac)
        async with test_db_pool.acquire() as conn:
            await _seed_txn(conn, email, txn_date="2026-05-01", amount=1000, merchant="X", category="coffee")
            await _seed_txn(conn, email, txn_date="2026-05-02", amount=2000, merchant="Y", category="lunch")
            await _seed_txn(conn, email, txn_date="2026-05-03", amount=3000, merchant="Z", category="shopping")

        r = await ac.get(
            "/transactions?category=coffee,lunch",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 200
    body = r.json()
    assert {t["merchant_raw"] for t in body} == {"X", "Y"}


async def test_filter_by_category_uses_effective_override(test_db_pool):
    """user_category_override 값으로 필터링되는지."""
    async with await _client() as ac:
        token, email = await _signup_and_token(ac)
        async with test_db_pool.acquire() as conn:
            user = await conn.fetchrow("SELECT id FROM users WHERE email = $1", email)
            user_id = user["id"]
            await conn.execute(
                """
                INSERT INTO transactions (
                  user_id, source_type, txn_date, amount, merchant_raw,
                  category, user_category_override, dedup_hash, raw_row
                ) VALUES ($1, 'test', '2026-05-10', 1000, 'OVERRIDDEN',
                          'unknown', 'groceries', $2, '{}'::jsonb)
                """,
                user_id, str(uuid4()),
            )

        # filter by override value
        r = await ac.get(
            "/transactions?category=groceries",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["effective_category"] == "groceries"
    assert body[0]["auto_category"] == "unknown"
    assert body[0]["user_category_override"] == "groceries"


async def test_filter_by_search(test_db_pool):
    async with await _client() as ac:
        token, email = await _signup_and_token(ac)
        async with test_db_pool.acquire() as conn:
            await _seed_txn(conn, email, txn_date="2026-05-01", amount=1, merchant="스타벅스 강남")
            await _seed_txn(conn, email, txn_date="2026-05-02", amount=2, merchant="이마트")

        r = await ac.get(
            "/transactions?search=스타벅스",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 200
    assert len(r.json()) == 1


async def test_pagination(test_db_pool):
    async with await _client() as ac:
        token, email = await _signup_and_token(ac)
        async with test_db_pool.acquire() as conn:
            for i in range(10):
                await _seed_txn(conn, email, txn_date="2026-05-01", amount=i, merchant=f"M{i}")

        r1 = await ac.get(
            "/transactions?limit=3&offset=0",
            headers={"Authorization": f"Bearer {token}"},
        )
        r2 = await ac.get(
            "/transactions?limit=3&offset=3",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert len(r1.json()) == 3
    assert len(r2.json()) == 3
    # No overlap
    ids_1 = {t["id"] for t in r1.json()}
    ids_2 = {t["id"] for t in r2.json()}
    assert ids_1.isdisjoint(ids_2)


async def test_months_endpoint(test_db_pool):
    async with await _client() as ac:
        token, email = await _signup_and_token(ac)
        async with test_db_pool.acquire() as conn:
            await _seed_txn(conn, email, txn_date="2026-03-15", amount=1, merchant="A")
            await _seed_txn(conn, email, txn_date="2026-05-10", amount=2, merchant="B")
            await _seed_txn(conn, email, txn_date="2026-05-01", amount=3, merchant="C")

        r = await ac.get(
            "/transactions/months",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body == ["2026-05", "2026-03"]


async def test_months_empty_when_no_transactions(test_db_pool):
    async with await _client() as ac:
        token, _ = await _signup_and_token(ac)
        r = await ac.get(
            "/transactions/months",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 200
    assert r.json() == []


async def test_invalid_month_format_returns_400(test_db_pool):
    async with await _client() as ac:
        token, _ = await _signup_and_token(ac)
        r = await ac.get(
            "/transactions?month=05-2026",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 400
    assert r.json()["detail"] == "INVALID_MONTH_FORMAT"


async def test_invalid_limit_returns_400(test_db_pool):
    async with await _client() as ac:
        token, _ = await _signup_and_token(ac)
        r = await ac.get(
            "/transactions?limit=999",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 400
    assert r.json()["detail"] == "INVALID_LIMIT"
```

- [ ] **Step 4:** Run (expect FAIL on months endpoint + filter behavior).

```bash
cd apps/api && uv run pytest tests/transactions/test_filter_query.py -v
```

### Task 10: `list_transactions` 라우트에 필터 + months 라우트 구현

**Files:**
- Modify: `apps/api/app/transactions/routes.py`

- [ ] **Step 1:** 기존 `list_transactions` 라우트 (`@router.get("")`)를 다음으로 교체:

```python
import re

_MONTH_RE = re.compile(r"^\d{4}-\d{2}$")


@router.get("", response_model=list[TransactionOut], summary="사용자별 거래 목록")
async def list_transactions(
    month: str | None = None,
    category: str | None = None,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
    user_id: UUID = Depends(current_user_id),  # noqa: B008
) -> list[TransactionOut]:
    if month is not None and not _MONTH_RE.match(month):
        raise HTTPException(status_code=400, detail="INVALID_MONTH_FORMAT")
    if not (1 <= limit <= 200):
        raise HTTPException(status_code=400, detail="INVALID_LIMIT")
    if offset < 0:
        raise HTTPException(status_code=400, detail="INVALID_LIMIT")

    categories = (
        [c.strip() for c in category.split(",") if c.strip()] if category else None
    )

    async with acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id::text, txn_date, txn_time, amount, merchant_raw, merchant_normalized,
                   approval_no, card_last4, installment_months, is_canceled,
                   category,
                   category AS auto_category,
                   user_category_override,
                   COALESCE(user_category_override, category) AS effective_category,
                   essential, essential_reason
            FROM transactions
            WHERE user_id = $1
              AND ($2::text IS NULL OR to_char(txn_date, 'YYYY-MM') = $2)
              AND ($3::text[] IS NULL OR COALESCE(user_category_override, category) = ANY($3))
              AND ($4::text IS NULL OR merchant_raw ILIKE '%' || $4 || '%')
            ORDER BY txn_date DESC, txn_time DESC NULLS LAST, created_at DESC
            LIMIT $5 OFFSET $6
            """,
            user_id, month, categories, search, limit, offset,
        )
    return [TransactionOut(**dict(r)) for r in rows]
```

- [ ] **Step 2:** `/transactions/months` 라우트 추가 (list_transactions 위에 — FastAPI route 매칭 우선순위):

```python
@router.get("/months", response_model=list[str])
async def list_months(
    user_id: UUID = Depends(current_user_id),  # noqa: B008
) -> list[str]:
    async with acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT DISTINCT to_char(txn_date, 'YYYY-MM') AS month
            FROM transactions
            WHERE user_id = $1
            ORDER BY month DESC
            """,
            user_id,
        )
    return [r["month"] for r in rows]
```

- [ ] **Step 3:** Run.

```bash
cd apps/api && uv run pytest tests/transactions/test_filter_query.py -v
```

Expected: 9/9 PASS.

### Task 11: Phase 2 회귀 + Commit + PR

- [ ] **Step 1:**

```bash
cd apps/api && uv run pytest -x && uv run ruff check
```

- [ ] **Step 2:**

```bash
cd ../..
git add apps/api/app/transactions/routes.py apps/api/app/transactions/schemas.py apps/api/tests/transactions/test_filter_query.py
git commit -m "feat(api): GET /transactions filter/search/pagination + /transactions/months

- GET /transactions에 month/category/search/limit/offset 쿼리 파라미터
  - month: YYYY-MM (정규식 검증)
  - category: CSV multi-value, effective_category(=COALESCE(override, category))로 필터
  - search: merchant_raw ILIKE substring
  - limit 1-200, offset >= 0
- GET /transactions/months — DISTINCT YYYY-MM 정렬 DESC
- 400 INVALID_MONTH_FORMAT / INVALID_LIMIT 에러 코드
- TransactionOut에 auto_category, user_category_override, effective_category 노출

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
git push -u origin feat/w3-phase2-filter-search
gh pr create --title "feat(api): GET /transactions filter/search/pagination + /transactions/months" --body-file - <<'EOF'
## Summary
- GET /transactions 쿼리 파라미터 (month/category/search/limit/offset) — effective_category 사용
- GET /transactions/months — month dropdown 옵션
- TransactionOut에 effective_category + auto_category + user_category_override 노출

## Test plan
- [x] test_filter_query.py (9 cases)
EOF
gh pr checks --watch
gh pr merge --squash --delete-branch --subject "feat(api): GET /transactions filter/search/pagination + /transactions/months (#?)"
git checkout main && git pull --ff-only origin main
```

---

## Phase 3: 4 Dashboard aggregate API (10 tasks)

**브랜치:** `feat/w3-phase3-dashboard-api`

### Task 12: 브랜치 + dashboard 모듈 skeleton

**Files:**
- Create: `apps/api/app/dashboard/__init__.py`
- Create: `apps/api/app/dashboard/routes.py`
- Create: `apps/api/app/dashboard/service.py`
- Modify: `apps/api/app/main.py`

- [ ] **Step 1:**

```bash
git checkout -b feat/w3-phase3-dashboard-api
```

- [ ] **Step 2:** Create `apps/api/app/dashboard/__init__.py` (empty).

- [ ] **Step 3:** Create `apps/api/app/dashboard/service.py`:

```python
"""Dashboard aggregate queries — raw SQL on transactions.

모든 집계는 amount > 0 (출금) 기준. 입금/소득은 W4 이후 분석.
effective_category = COALESCE(user_category_override, category).
"""
import re
from datetime import date
from decimal import Decimal
from uuid import UUID

import asyncpg

_MONTH_RE = re.compile(r"^\d{4}-\d{2}$")


def validate_month(s: str) -> None:
    if not _MONTH_RE.match(s):
        raise ValueError(f"invalid month format: {s!r}")


def _prev_month(month: str) -> str:
    """2026-05 → 2026-04, 2026-01 → 2025-12."""
    y, m = int(month[:4]), int(month[5:7])
    if m == 1:
        return f"{y - 1:04d}-12"
    return f"{y:04d}-{m - 1:02d}"


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

    cur_total = Decimal(row["total"])
    prev_total = Decimal(prev_row["total"])
    diff_pct: float | None = None
    if prev_total > 0:
        diff_pct = float((cur_total - prev_total) / prev_total * 100)

    return {
        "month": month,
        "total_amount": cur_total,
        "transaction_count": row["cnt"],
        "prev_month": prev,
        "prev_month_total": prev_total,
        "prev_month_diff_pct": diff_pct,
    }


async def by_category(conn: asyncpg.Connection, user_id: UUID, month: str) -> list[dict]:
    validate_month(month)
    rows = await conn.fetch(
        """
        SELECT COALESCE(user_category_override, category) AS category,
               COALESCE(SUM(amount), 0)::numeric AS amount,
               COUNT(*) AS count
        FROM transactions
        WHERE user_id = $1 AND to_char(txn_date, 'YYYY-MM') = $2 AND amount > 0
        GROUP BY COALESCE(user_category_override, category)
        ORDER BY amount DESC
        """,
        user_id, month,
    )
    return [{"category": r["category"], "amount": r["amount"], "count": r["count"]} for r in rows]


async def by_month(conn: asyncpg.Connection, user_id: UUID, last_n: int) -> list[dict]:
    if not (1 <= last_n <= 24):
        raise ValueError(f"last_n out of range: {last_n}")
    rows = await conn.fetch(
        """
        SELECT to_char(txn_date, 'YYYY-MM') AS month,
               COALESCE(SUM(amount), 0)::numeric AS amount
        FROM transactions
        WHERE user_id = $1
          AND txn_date >= date_trunc('month', CURRENT_DATE - ($2 - 1) * INTERVAL '1 month')
          AND amount > 0
        GROUP BY month
        ORDER BY month ASC
        """,
        user_id, last_n,
    )
    return [{"month": r["month"], "amount": r["amount"]} for r in rows]


async def top_merchants(
    conn: asyncpg.Connection, user_id: UUID, month: str, limit: int,
) -> list[dict]:
    validate_month(month)
    if not (1 <= limit <= 20):
        raise ValueError(f"limit out of range: {limit}")
    rows = await conn.fetch(
        """
        SELECT merchant_raw,
               COALESCE(SUM(amount), 0)::numeric AS amount,
               COUNT(*) AS count
        FROM transactions
        WHERE user_id = $1 AND to_char(txn_date, 'YYYY-MM') = $2 AND amount > 0
        GROUP BY merchant_raw
        ORDER BY amount DESC
        LIMIT $3
        """,
        user_id, month, limit,
    )
    return [
        {"merchant_raw": r["merchant_raw"], "amount": r["amount"], "count": r["count"]}
        for r in rows
    ]
```

- [ ] **Step 4:** Create `apps/api/app/dashboard/routes.py`:

```python
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth.deps import current_user_id
from app.dashboard import service
from app.db import acquire

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class SummaryResponse(BaseModel):
    month: str
    total_amount: Decimal
    transaction_count: int
    prev_month: str
    prev_month_total: Decimal
    prev_month_diff_pct: float | None


class CategoryBucket(BaseModel):
    category: str
    amount: Decimal
    count: int


class MonthBucket(BaseModel):
    month: str
    amount: Decimal


class MerchantBucket(BaseModel):
    merchant_raw: str
    amount: Decimal
    count: int


@router.get("/summary", response_model=SummaryResponse)
async def get_summary(
    month: str,
    user_id: UUID = Depends(current_user_id),  # noqa: B008
) -> SummaryResponse:
    try:
        async with acquire() as conn:
            data = await service.summary(conn, user_id, month)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="INVALID_MONTH_FORMAT") from exc
    return SummaryResponse(**data)


@router.get("/by-category", response_model=list[CategoryBucket])
async def get_by_category(
    month: str,
    user_id: UUID = Depends(current_user_id),  # noqa: B008
) -> list[CategoryBucket]:
    try:
        async with acquire() as conn:
            rows = await service.by_category(conn, user_id, month)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="INVALID_MONTH_FORMAT") from exc
    return [CategoryBucket(**r) for r in rows]


@router.get("/by-month", response_model=list[MonthBucket])
async def get_by_month(
    last_n: int = 6,
    user_id: UUID = Depends(current_user_id),  # noqa: B008
) -> list[MonthBucket]:
    try:
        async with acquire() as conn:
            rows = await service.by_month(conn, user_id, last_n)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="INVALID_LAST_N") from exc
    return [MonthBucket(**r) for r in rows]


@router.get("/top-merchants", response_model=list[MerchantBucket])
async def get_top_merchants(
    month: str,
    limit: int = 5,
    user_id: UUID = Depends(current_user_id),  # noqa: B008
) -> list[MerchantBucket]:
    try:
        async with acquire() as conn:
            rows = await service.top_merchants(conn, user_id, month, limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="INVALID_PARAMETER") from exc
    return [MerchantBucket(**r) for r in rows]
```

- [ ] **Step 5:** `apps/api/app/main.py` 수정 — import + router 등록:

```python
from app.dashboard.routes import router as dashboard_router
```

(다른 router import 다음 줄에)

그리고 `app.include_router(...)` 블록에 추가:

```python
app.include_router(dashboard_router)
```

### Task 13: dashboard test 디렉토리 + summary 테스트 TDD

**Files:**
- Create: `apps/api/tests/dashboard/__init__.py`
- Create: `apps/api/tests/dashboard/test_summary.py`

- [ ] **Step 1:** Create empty `apps/api/tests/dashboard/__init__.py`.

- [ ] **Step 2:** Create `apps/api/tests/dashboard/test_summary.py`:

```python
import httpx
from httpx import ASGITransport
from uuid import uuid4

from app.main import app


async def _client():
    return httpx.AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    )


async def _signup_and_token(ac):
    email = f"_w3-dash-{uuid4()}@example.com"
    r = await ac.post("/auth/signup", json={"email": email, "password": "abcd1234"})
    return r.json()["access_token"], email


async def _seed(conn, email, *, txn_date, amount):
    user = await conn.fetchrow("SELECT id FROM users WHERE email = $1", email)
    await conn.execute(
        """
        INSERT INTO transactions (
          user_id, source_type, txn_date, amount, merchant_raw,
          category, dedup_hash, raw_row
        ) VALUES ($1, 'test', $2, $3, 'M', 'unknown', $4, '{}'::jsonb)
        """,
        user["id"], txn_date, amount, str(uuid4()),
    )


async def test_summary_basic(test_db_pool):
    async with await _client() as ac:
        token, email = await _signup_and_token(ac)
        async with test_db_pool.acquire() as conn:
            await _seed(conn, email, txn_date="2026-05-01", amount=10000)
            await _seed(conn, email, txn_date="2026-05-15", amount=20000)
            await _seed(conn, email, txn_date="2026-04-20", amount=15000)

        r = await ac.get(
            "/dashboard/summary?month=2026-05",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["month"] == "2026-05"
    assert float(body["total_amount"]) == 30000
    assert body["transaction_count"] == 2
    assert body["prev_month"] == "2026-04"
    assert float(body["prev_month_total"]) == 15000
    assert body["prev_month_diff_pct"] == 100.0  # 15000 → 30000 = +100%


async def test_summary_no_prev_month_returns_null_diff(test_db_pool):
    async with await _client() as ac:
        token, email = await _signup_and_token(ac)
        async with test_db_pool.acquire() as conn:
            await _seed(conn, email, txn_date="2026-05-01", amount=10000)

        r = await ac.get(
            "/dashboard/summary?month=2026-05",
            headers={"Authorization": f"Bearer {token}"},
        )
    body = r.json()
    assert body["prev_month_diff_pct"] is None


async def test_summary_excludes_negative_amount(test_db_pool):
    """입금(amount < 0)은 출금 집계에서 제외."""
    async with await _client() as ac:
        token, email = await _signup_and_token(ac)
        async with test_db_pool.acquire() as conn:
            await _seed(conn, email, txn_date="2026-05-01", amount=10000)
            await _seed(conn, email, txn_date="2026-05-02", amount=-50000)  # 입금

        r = await ac.get(
            "/dashboard/summary?month=2026-05",
            headers={"Authorization": f"Bearer {token}"},
        )
    body = r.json()
    assert float(body["total_amount"]) == 10000  # 입금 제외
    assert body["transaction_count"] == 1


async def test_summary_invalid_month_400(test_db_pool):
    async with await _client() as ac:
        token, _ = await _signup_and_token(ac)
        r = await ac.get(
            "/dashboard/summary?month=05-2026",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 400
```

- [ ] **Step 3:** Run.

```bash
cd apps/api && uv run pytest tests/dashboard/test_summary.py -v
```

Expected: 4/4 PASS.

### Task 14: by-category 테스트 TDD

**Files:**
- Create: `apps/api/tests/dashboard/test_by_category.py`

- [ ] **Step 1:** Create test file:

```python
import httpx
from httpx import ASGITransport
from uuid import uuid4

from app.main import app


async def _client():
    return httpx.AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    )


async def _signup_and_token(ac):
    email = f"_w3-cat-{uuid4()}@example.com"
    r = await ac.post("/auth/signup", json={"email": email, "password": "abcd1234"})
    return r.json()["access_token"], email


async def _seed(conn, email, *, txn_date, amount, category, override=None):
    user = await conn.fetchrow("SELECT id FROM users WHERE email = $1", email)
    await conn.execute(
        """
        INSERT INTO transactions (
          user_id, source_type, txn_date, amount, merchant_raw,
          category, user_category_override, dedup_hash, raw_row
        ) VALUES ($1, 'test', $2, $3, 'M', $4, $5, $6, '{}'::jsonb)
        """,
        user["id"], txn_date, amount, category, override, str(uuid4()),
    )


async def test_by_category_groups_correctly(test_db_pool):
    async with await _client() as ac:
        token, email = await _signup_and_token(ac)
        async with test_db_pool.acquire() as conn:
            await _seed(conn, email, txn_date="2026-05-01", amount=5000, category="coffee")
            await _seed(conn, email, txn_date="2026-05-02", amount=3000, category="coffee")
            await _seed(conn, email, txn_date="2026-05-03", amount=10000, category="groceries")

        r = await ac.get(
            "/dashboard/by-category?month=2026-05",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 200
    body = r.json()
    # ORDER BY amount DESC
    assert body[0]["category"] == "groceries"
    assert float(body[0]["amount"]) == 10000
    assert body[0]["count"] == 1
    assert body[1]["category"] == "coffee"
    assert float(body[1]["amount"]) == 8000
    assert body[1]["count"] == 2


async def test_by_category_uses_effective_override(test_db_pool):
    async with await _client() as ac:
        token, email = await _signup_and_token(ac)
        async with test_db_pool.acquire() as conn:
            # auto=unknown, override=groceries → effective=groceries
            await _seed(conn, email, txn_date="2026-05-01", amount=5000,
                        category="unknown", override="groceries")
            await _seed(conn, email, txn_date="2026-05-02", amount=3000,
                        category="groceries")

        r = await ac.get(
            "/dashboard/by-category?month=2026-05",
            headers={"Authorization": f"Bearer {token}"},
        )
    body = r.json()
    assert len(body) == 1
    assert body[0]["category"] == "groceries"
    assert float(body[0]["amount"]) == 8000  # 5000 + 3000 합쳐짐
    assert body[0]["count"] == 2


async def test_by_category_empty(test_db_pool):
    async with await _client() as ac:
        token, _ = await _signup_and_token(ac)
        r = await ac.get(
            "/dashboard/by-category?month=2026-05",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.json() == []
```

- [ ] **Step 2:** Run.

```bash
cd apps/api && uv run pytest tests/dashboard/test_by_category.py -v
```

Expected: 3/3 PASS.

### Task 15: by-month 테스트 TDD

**Files:**
- Create: `apps/api/tests/dashboard/test_by_month.py`

- [ ] **Step 1:** Create:

```python
import httpx
from httpx import ASGITransport
from datetime import date, timedelta
from uuid import uuid4

from app.main import app


async def _client():
    return httpx.AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    )


async def _signup_and_token(ac):
    email = f"_w3-bym-{uuid4()}@example.com"
    r = await ac.post("/auth/signup", json={"email": email, "password": "abcd1234"})
    return r.json()["access_token"], email


async def _seed(conn, email, *, txn_date, amount):
    user = await conn.fetchrow("SELECT id FROM users WHERE email = $1", email)
    await conn.execute(
        """
        INSERT INTO transactions (
          user_id, source_type, txn_date, amount, merchant_raw,
          category, dedup_hash, raw_row
        ) VALUES ($1, 'test', $2, $3, 'M', 'unknown', $4, '{}'::jsonb)
        """,
        user["id"], txn_date, amount, str(uuid4()),
    )


async def test_by_month_returns_last_n_months(test_db_pool):
    """last_n=6 → 최근 6개월 (오늘 포함)."""
    today = date.today()

    async with await _client() as ac:
        token, email = await _signup_and_token(ac)
        async with test_db_pool.acquire() as conn:
            # 최근 6달 중 3개월에 거래 삽입
            await _seed(conn, email, txn_date=today.replace(day=1), amount=10000)
            three_mo_ago = today.replace(day=1) - timedelta(days=70)
            await _seed(conn, email, txn_date=three_mo_ago, amount=5000)

        r = await ac.get(
            "/dashboard/by-month?last_n=6",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 200
    body = r.json()
    # 거래 있는 달만 반환 (GROUP BY)
    assert len(body) == 2
    months = [b["month"] for b in body]
    # ORDER BY ASC
    assert months == sorted(months)


async def test_by_month_excludes_deposits(test_db_pool):
    today = date.today()
    async with await _client() as ac:
        token, email = await _signup_and_token(ac)
        async with test_db_pool.acquire() as conn:
            await _seed(conn, email, txn_date=today.replace(day=1), amount=10000)
            await _seed(conn, email, txn_date=today.replace(day=2), amount=-50000)

        r = await ac.get(
            "/dashboard/by-month?last_n=3",
            headers={"Authorization": f"Bearer {token}"},
        )
    body = r.json()
    assert len(body) == 1
    assert float(body[0]["amount"]) == 10000


async def test_by_month_invalid_last_n_400(test_db_pool):
    async with await _client() as ac:
        token, _ = await _signup_and_token(ac)
        r = await ac.get(
            "/dashboard/by-month?last_n=999",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 400
```

- [ ] **Step 2:** Run.

Expected: 3/3 PASS.

### Task 16: top-merchants 테스트 TDD

**Files:**
- Create: `apps/api/tests/dashboard/test_top_merchants.py`

- [ ] **Step 1:** Create:

```python
import httpx
from httpx import ASGITransport
from uuid import uuid4

from app.main import app


async def _client():
    return httpx.AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    )


async def _signup_and_token(ac):
    email = f"_w3-top-{uuid4()}@example.com"
    r = await ac.post("/auth/signup", json={"email": email, "password": "abcd1234"})
    return r.json()["access_token"], email


async def _seed(conn, email, *, merchant, amount, txn_date="2026-05-15"):
    user = await conn.fetchrow("SELECT id FROM users WHERE email = $1", email)
    await conn.execute(
        """
        INSERT INTO transactions (
          user_id, source_type, txn_date, amount, merchant_raw,
          category, dedup_hash, raw_row
        ) VALUES ($1, 'test', $2, $3, $4, 'unknown', $5, '{}'::jsonb)
        """,
        user["id"], txn_date, amount, merchant, str(uuid4()),
    )


async def test_top_merchants_groups_and_sums(test_db_pool):
    async with await _client() as ac:
        token, email = await _signup_and_token(ac)
        async with test_db_pool.acquire() as conn:
            await _seed(conn, email, merchant="홈플러스", amount=50000)
            await _seed(conn, email, merchant="홈플러스", amount=30000)
            await _seed(conn, email, merchant="스타벅스", amount=5000)
            await _seed(conn, email, merchant="이마트", amount=20000)

        r = await ac.get(
            "/dashboard/top-merchants?month=2026-05&limit=5",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body[0]["merchant_raw"] == "홈플러스"
    assert float(body[0]["amount"]) == 80000
    assert body[0]["count"] == 2
    assert [b["merchant_raw"] for b in body] == ["홈플러스", "이마트", "스타벅스"]


async def test_top_merchants_limit_applied(test_db_pool):
    async with await _client() as ac:
        token, email = await _signup_and_token(ac)
        async with test_db_pool.acquire() as conn:
            for i in range(10):
                await _seed(conn, email, merchant=f"M{i}", amount=1000 + i)

        r = await ac.get(
            "/dashboard/top-merchants?month=2026-05&limit=3",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert len(r.json()) == 3


async def test_top_merchants_default_limit_5(test_db_pool):
    async with await _client() as ac:
        token, email = await _signup_and_token(ac)
        async with test_db_pool.acquire() as conn:
            for i in range(10):
                await _seed(conn, email, merchant=f"M{i}", amount=1000 + i)

        r = await ac.get(
            "/dashboard/top-merchants?month=2026-05",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert len(r.json()) == 5
```

- [ ] **Step 2:** Run.

Expected: 3/3 PASS.

### Task 17: 전체 회귀 + Commit + PR

```bash
cd apps/api && uv run pytest -x && uv run ruff check
cd ../..
git add apps/api/app/dashboard apps/api/app/main.py apps/api/tests/dashboard
git commit -m "feat(api): dashboard aggregate APIs (summary/by-category/by-month/top-merchants)

- app/dashboard/{__init__,service,routes}.py
- 4 endpoints, 모두 amount > 0 (출금) 기준
- summary: 전월 대비 % 계산 (전월 0이면 null)
- by-category: COALESCE(override, category) 그룹화
- by-month: last_n 1-24, ORDER BY month ASC
- top-merchants: limit 1-20, default 5
- 400 INVALID_MONTH_FORMAT / INVALID_LAST_N / INVALID_PARAMETER

13 신규 테스트 (summary 4, by-category 3, by-month 3, top-merchants 3).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
git push -u origin feat/w3-phase3-dashboard-api
gh pr create --title "feat(api): dashboard aggregate APIs" --body-file - <<'EOF'
## Summary
- GET /dashboard/summary?month=YYYY-MM
- GET /dashboard/by-category?month=YYYY-MM
- GET /dashboard/by-month?last_n=N
- GET /dashboard/top-merchants?month=YYYY-MM&limit=N
- 모두 amount > 0 (출금) 기준, COALESCE(override, category) 사용

## Test plan
- [x] 13 신규 테스트
EOF
gh pr checks --watch
gh pr merge --squash --delete-branch --subject "feat(api): dashboard aggregate APIs (#?)"
git checkout main && git pull --ff-only origin main
```

---

## Phase 4: Nav 컴포넌트 + Router (4 tasks)

**브랜치:** `feat/w3-phase4-nav-router`

### Task 18: 브랜치 + Nav 컴포넌트 + 테스트

**Files:**
- Create: `apps/web/src/components/Nav.tsx`
- Create: `apps/web/src/components/Nav.test.tsx`
- Modify: `apps/web/src/App.tsx`

- [ ] **Step 1:**

```bash
git checkout -b feat/w3-phase4-nav-router
```

- [ ] **Step 2:** Create `apps/web/src/components/Nav.tsx`:

```tsx
import { Link, useLocation, useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth } from "../stores/auth";

export function Nav() {
  const isAuthed = useAuth((s) => !!s.accessToken);
  const setAccess = useAuth((s) => s.setAccess);
  const loc = useLocation();
  const nav = useNavigate();

  if (!isAuthed) return null;

  const linkCls = (path: string) =>
    `px-3 py-1 rounded ${loc.pathname === path ? "bg-zinc-800 text-white" : "text-zinc-400 hover:text-white"}`;

  async function logout() {
    try {
      await api.post("/auth/logout");
    } catch {
      /* ignore */
    }
    setAccess(null);
    nav("/login");
  }

  return (
    <nav className="flex items-center gap-2 px-4 py-3 border-b border-zinc-800 bg-zinc-950">
      <span className="font-bold text-white mr-4">spendLens</span>
      <Link to="/app" className={linkCls("/app")}>거래내역</Link>
      <Link to="/dashboard" className={linkCls("/dashboard")}>대시보드</Link>
      <div className="flex-1" />
      <button onClick={logout} className="text-sm text-zinc-400 hover:text-white">로그아웃</button>
    </nav>
  );
}
```

- [ ] **Step 3:** Create `apps/web/src/components/Nav.test.tsx`:

```tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { Nav } from "./Nav";
import { useAuth } from "../stores/auth";

vi.mock("../lib/api", () => ({ api: { post: vi.fn() } }));

describe("Nav", () => {
  it("renders nothing when not authed", () => {
    useAuth.setState({ accessToken: null });
    const { container } = render(<MemoryRouter><Nav /></MemoryRouter>);
    expect(container.firstChild).toBeNull();
  });

  it("renders links when authed", () => {
    useAuth.setState({ accessToken: "fake" });
    render(<MemoryRouter><Nav /></MemoryRouter>);
    expect(screen.getByText("거래내역")).toBeInTheDocument();
    expect(screen.getByText("대시보드")).toBeInTheDocument();
    expect(screen.getByText("로그아웃")).toBeInTheDocument();
  });
});
```

- [ ] **Step 4:** Run.

```bash
pnpm -C apps/web test src/components/Nav.test.tsx
```

Expected: 2 PASS.

### Task 19: `/dashboard` 라우트 + Nav 전역 배치

**Files:**
- Modify: `apps/web/src/App.tsx`
- Create: `apps/web/src/routes/dashboard.tsx` (placeholder)

- [ ] **Step 1:** Create placeholder `apps/web/src/routes/dashboard.tsx` (Phase 6에서 본 구현):

```tsx
export function DashboardPage() {
  return (
    <div className="p-8">
      <h2 className="text-xl">대시보드 (Phase 6에서 본구현)</h2>
    </div>
  );
}
```

- [ ] **Step 2:** Modify `apps/web/src/App.tsx`:

```tsx
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { LandingPage } from "./routes";
import { GuestPage } from "./routes/guest";
import { LoginPage } from "./routes/login";
import { SignupPage } from "./routes/signup";
import { AppPage } from "./routes/app";
import { DashboardPage } from "./routes/dashboard";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { Nav } from "./components/Nav";

export function App() {
  return (
    <BrowserRouter>
      <Nav />
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/guest" element={<GuestPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/signup" element={<SignupPage />} />
        <Route path="/app" element={<ProtectedRoute><AppPage /></ProtectedRoute>} />
        <Route path="/dashboard" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />
      </Routes>
    </BrowserRouter>
  );
}
```

- [ ] **Step 3:** Build/test 회귀.

```bash
pnpm -C apps/web test
pnpm -C apps/web build
```

Expected: all PASS, build clean.

### Task 20: Phase 4 Commit + PR

```bash
git add apps/web/src/components/Nav.tsx apps/web/src/components/Nav.test.tsx apps/web/src/App.tsx apps/web/src/routes/dashboard.tsx
git commit -m "feat(web): Nav 컴포넌트 + /dashboard 라우트 (Phase 6 placeholder)

- components/Nav.tsx: 로그인 사용자 헤더 (거래내역/대시보드/로그아웃)
- 비로그인 시 null 반환
- App.tsx에 /dashboard 라우트 + ProtectedRoute + Nav 전역 배치

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
git push -u origin feat/w3-phase4-nav-router
gh pr create --title "feat(web): Nav + /dashboard router" --body-file - <<'EOF'
## Summary
- components/Nav.tsx: 헤더 nav (거래내역/대시보드/로그아웃)
- /dashboard 라우트 등록 (placeholder, Phase 6에서 본구현)

## Test plan
- [x] Nav.test.tsx (2)
- [x] pnpm build clean
EOF
gh pr checks --watch
gh pr merge --squash --delete-branch --subject "feat(web): Nav + /dashboard router (#?)"
git checkout main && git pull --ff-only origin main
```

---

## Phase 5: CategoryChip + FilterBar + /app 통합 (10 tasks)

**브랜치:** `feat/w3-phase5-app-filter`

### Task 21: 브랜치 + lib/api.ts에 PATCH/months 함수

**Files:**
- Modify: `apps/web/src/lib/api.ts`

- [ ] **Step 1:**

```bash
git checkout -b feat/w3-phase5-app-filter
```

- [ ] **Step 2:** `apps/web/src/lib/api.ts` 파일 끝에 wrapper 함수 추가 (api는 이미 export):

```typescript
export type TransactionRow = {
  id: string;
  txn_date: string;
  txn_time: string | null;
  amount: string;
  merchant_raw: string;
  category: string;
  auto_category: string;
  user_category_override: string | null;
  effective_category: string;
};

export async function fetchTransactions(params: {
  month?: string;
  category?: string[];
  search?: string;
  limit?: number;
  offset?: number;
}): Promise<TransactionRow[]> {
  const q = new URLSearchParams();
  if (params.month) q.set("month", params.month);
  if (params.category && params.category.length) q.set("category", params.category.join(","));
  if (params.search) q.set("search", params.search);
  q.set("limit", String(params.limit ?? 50));
  q.set("offset", String(params.offset ?? 0));
  const { data } = await api.get<TransactionRow[]>(`/transactions?${q}`);
  return data;
}

export async function fetchMonths(): Promise<string[]> {
  const { data } = await api.get<string[]>("/transactions/months");
  return data;
}

export async function patchCategory(id: string, category: string): Promise<void> {
  await api.patch(`/transactions/${id}`, { category });
}
```

### Task 22: CategoryChip 컴포넌트 + 테스트

**Files:**
- Create: `apps/web/src/components/CategoryChip.tsx`
- Create: `apps/web/src/components/CategoryChip.test.tsx`

- [ ] **Step 1:** Create `apps/web/src/components/CategoryChip.tsx`:

```tsx
import { useState, useRef, useEffect } from "react";
import { patchCategory } from "../lib/api";

const CATEGORIES = [
  "coffee", "lunch", "dinner", "snack_late",
  "groceries", "transport", "telecom",
  "subscription", "entertainment", "health",
  "shopping", "utilities", "etc", "unknown",
  "savings", "insurance", "income", "transfer", "housing",
] as const;

type Props = {
  transactionId: string;
  effective: string;
  isOverridden: boolean;
  onChange: (newCategory: string) => void;
};

export function CategoryChip({ transactionId, effective, isOverridden, onChange }: Props) {
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    if (open) document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, [open]);

  async function pick(cat: string) {
    if (cat === effective) {
      setOpen(false);
      return;
    }
    setSaving(true);
    onChange(cat); // 낙관적 업데이트
    try {
      await patchCategory(transactionId, cat);
      setOpen(false);
    } catch {
      onChange(effective); // 롤백
    } finally {
      setSaving(false);
    }
  }

  const bg = effective === "unknown" ? "bg-zinc-700" : "bg-blue-700";
  const overrideDot = isOverridden ? "•" : "";

  return (
    <div ref={ref} className="relative inline-block">
      <button
        onClick={() => setOpen((v) => !v)}
        disabled={saving}
        className={`${bg} text-white text-xs px-2 py-0.5 rounded disabled:opacity-50`}
        aria-label={`카테고리: ${effective}`}
      >
        {effective}{overrideDot} ▾
      </button>
      {open && (
        <div className="absolute top-full left-0 mt-1 bg-zinc-900 border border-zinc-700 rounded shadow-lg z-10 max-h-60 overflow-y-auto">
          {CATEGORIES.map((c) => (
            <button
              key={c}
              onClick={() => pick(c)}
              className={`block w-full text-left px-3 py-1 text-xs hover:bg-zinc-800 ${c === effective ? "text-blue-400" : "text-zinc-200"}`}
            >
              {c === effective ? "✓ " : "  "}{c}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2:** Create `apps/web/src/components/CategoryChip.test.tsx`:

```tsx
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

const patchMock = vi.fn();
vi.mock("../lib/api", () => ({ patchCategory: patchMock }));

import { CategoryChip } from "./CategoryChip";

describe("CategoryChip", () => {
  beforeEach(() => patchMock.mockReset());

  it("displays effective category", () => {
    render(<CategoryChip transactionId="t1" effective="coffee" isOverridden={false} onChange={() => {}} />);
    expect(screen.getByText(/coffee/)).toBeInTheDocument();
  });

  it("shows override dot when overridden", () => {
    render(<CategoryChip transactionId="t1" effective="groceries" isOverridden={true} onChange={() => {}} />);
    expect(screen.getByText(/groceries•/)).toBeInTheDocument();
  });

  it("opens dropdown on click and calls patch on selection", async () => {
    patchMock.mockResolvedValueOnce(undefined);
    const onChange = vi.fn();
    render(<CategoryChip transactionId="t1" effective="unknown" isOverridden={false} onChange={onChange} />);

    fireEvent.click(screen.getByRole("button", { name: /unknown/ }));
    fireEvent.click(screen.getByText(/groceries/));

    expect(onChange).toHaveBeenCalledWith("groceries");
    await waitFor(() => expect(patchMock).toHaveBeenCalledWith("t1", "groceries"));
  });

  it("rolls back onChange on patch failure", async () => {
    patchMock.mockRejectedValueOnce(new Error("network"));
    const onChange = vi.fn();
    render(<CategoryChip transactionId="t1" effective="unknown" isOverridden={false} onChange={onChange} />);

    fireEvent.click(screen.getByRole("button", { name: /unknown/ }));
    fireEvent.click(screen.getByText(/groceries/));

    await waitFor(() => {
      expect(onChange).toHaveBeenNthCalledWith(1, "groceries");
      expect(onChange).toHaveBeenNthCalledWith(2, "unknown"); // 롤백
    });
  });
});
```

- [ ] **Step 3:** Run.

```bash
pnpm -C apps/web test src/components/CategoryChip.test.tsx
```

Expected: 4 PASS.

### Task 23: FilterBar 컴포넌트 + 테스트

**Files:**
- Create: `apps/web/src/components/FilterBar.tsx`
- Create: `apps/web/src/components/FilterBar.test.tsx`

- [ ] **Step 1:** Create `apps/web/src/components/FilterBar.tsx`:

```tsx
import { useEffect, useState } from "react";
import { fetchMonths } from "../lib/api";

const CATEGORY_OPTIONS = [
  "coffee", "lunch", "dinner", "snack_late",
  "groceries", "transport", "telecom",
  "subscription", "entertainment", "health",
  "shopping", "utilities", "etc", "unknown",
  "savings", "insurance", "income", "transfer", "housing",
];

type Props = {
  month: string | null;
  setMonth: (m: string | null) => void;
  categories: string[];
  setCategories: (cs: string[]) => void;
  search: string;
  setSearch: (s: string) => void;
};

export function FilterBar({ month, setMonth, categories, setCategories, search, setSearch }: Props) {
  const [availableMonths, setAvailableMonths] = useState<string[]>([]);

  useEffect(() => {
    fetchMonths().then(setAvailableMonths).catch(() => setAvailableMonths([]));
  }, []);

  function toggleCategory(c: string) {
    if (categories.includes(c)) {
      setCategories(categories.filter((x) => x !== c));
    } else {
      setCategories([...categories, c]);
    }
  }

  return (
    <div className="flex flex-wrap gap-2 p-4 border-b border-zinc-800 items-center">
      <select
        value={month ?? ""}
        onChange={(e) => setMonth(e.target.value || null)}
        className="bg-zinc-900 border border-zinc-700 rounded px-2 py-1 text-sm"
        aria-label="월 선택"
      >
        <option value="">전체 기간</option>
        {availableMonths.map((m) => (
          <option key={m} value={m}>{m}</option>
        ))}
      </select>

      <input
        type="text"
        placeholder="가맹점 검색"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="bg-zinc-900 border border-zinc-700 rounded px-2 py-1 text-sm flex-1 min-w-[120px]"
        aria-label="검색"
      />

      <details className="relative">
        <summary className="cursor-pointer text-sm text-zinc-400 px-2 py-1 border border-zinc-700 rounded">
          카테고리 ({categories.length})
        </summary>
        <div className="absolute top-full right-0 mt-1 bg-zinc-900 border border-zinc-700 rounded p-2 z-10 max-h-72 overflow-y-auto">
          {CATEGORY_OPTIONS.map((c) => (
            <label key={c} className="block text-xs text-zinc-200 hover:bg-zinc-800 px-2 py-1">
              <input
                type="checkbox"
                checked={categories.includes(c)}
                onChange={() => toggleCategory(c)}
                className="mr-2"
              />
              {c}
            </label>
          ))}
        </div>
      </details>

      {categories.length > 0 && (
        <button onClick={() => setCategories([])} className="text-xs text-zinc-500 hover:text-white">
          ✕ 카테고리 초기화
        </button>
      )}
    </div>
  );
}
```

- [ ] **Step 2:** Create `apps/web/src/components/FilterBar.test.tsx`:

```tsx
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

const fetchMock = vi.fn().mockResolvedValue(["2026-05", "2026-04"]);
vi.mock("../lib/api", () => ({ fetchMonths: fetchMock }));

import { FilterBar } from "./FilterBar";

describe("FilterBar", () => {
  beforeEach(() => fetchMock.mockClear());

  it("renders month options from fetchMonths", async () => {
    render(<FilterBar month={null} setMonth={() => {}} categories={[]} setCategories={() => {}} search="" setSearch={() => {}} />);
    await screen.findByText("2026-05");
    expect(screen.getByText("2026-04")).toBeInTheDocument();
  });

  it("calls setMonth on selection", async () => {
    const setMonth = vi.fn();
    render(<FilterBar month={null} setMonth={setMonth} categories={[]} setCategories={() => {}} search="" setSearch={() => {}} />);
    await screen.findByText("2026-05");
    fireEvent.change(screen.getByLabelText("월 선택"), { target: { value: "2026-05" } });
    expect(setMonth).toHaveBeenCalledWith("2026-05");
  });

  it("calls setSearch on input", () => {
    const setSearch = vi.fn();
    render(<FilterBar month={null} setMonth={() => {}} categories={[]} setCategories={() => {}} search="" setSearch={setSearch} />);
    fireEvent.change(screen.getByLabelText("검색"), { target: { value: "스타벅스" } });
    expect(setSearch).toHaveBeenCalledWith("스타벅스");
  });

  it("toggles categories", () => {
    const setCategories = vi.fn();
    render(<FilterBar month={null} setMonth={() => {}} categories={["coffee"]} setCategories={setCategories} search="" setSearch={() => {}} />);
    fireEvent.click(screen.getByText(/카테고리 \(1\)/));
    const checkbox = screen.getByLabelText("lunch");
    fireEvent.click(checkbox);
    expect(setCategories).toHaveBeenCalledWith(["coffee", "lunch"]);
  });
});
```

- [ ] **Step 3:** Run.

Expected: 4 PASS.

### Task 24: `/app` 페이지에 FilterBar + CategoryChip 통합

**Files:**
- Modify: `apps/web/src/routes/app.tsx`
- Modify: `apps/web/src/components/TransactionList.tsx`

- [ ] **Step 1:** 먼저 현재 `apps/web/src/routes/app.tsx`와 `TransactionList.tsx` 읽기:

```bash
cat apps/web/src/routes/app.tsx apps/web/src/components/TransactionList.tsx
```

- [ ] **Step 2:** `TransactionList.tsx` props 시그니처 갱신. 기존 prop이 `transactions: Transaction[]` 같은 형태라면, `onCategoryChange?: (id: string, newCategory: string) => void` 추가하고 각 행의 카테고리 표시 부분을 `<CategoryChip>`으로 교체.

(현재 코드를 봐야 정확히 알 수 있으므로 실 코드에 맞게 minor edit. 핵심:)

```tsx
import { CategoryChip } from "./CategoryChip";
import type { TransactionRow } from "../lib/api";

type Props = {
  transactions: TransactionRow[];
  onCategoryChange: (id: string, newCategory: string) => void;
};

// 각 행에:
//   <CategoryChip
//     transactionId={t.id}
//     effective={t.effective_category}
//     isOverridden={t.user_category_override != null}
//     onChange={(c) => onCategoryChange(t.id, c)}
//   />
```

- [ ] **Step 3:** `apps/web/src/routes/app.tsx`를 다음으로 재작성 (기존 업로드 + 거래 리스트 흐름 유지하면서 FilterBar 통합):

```tsx
import { useEffect, useState } from "react";
import { fetchTransactions, type TransactionRow } from "../lib/api";
import { FilterBar } from "../components/FilterBar";
import { TransactionList } from "../components/TransactionList";
import { UploadDropzone } from "../components/UploadDropzone";

export function AppPage() {
  const [month, setMonth] = useState<string | null>(null);
  const [categories, setCategories] = useState<string[]>([]);
  const [search, setSearch] = useState("");
  const [transactions, setTransactions] = useState<TransactionRow[]>([]);
  const [loading, setLoading] = useState(false);

  async function reload() {
    setLoading(true);
    try {
      const data = await fetchTransactions({
        month: month ?? undefined,
        category: categories.length ? categories : undefined,
        search: search || undefined,
        limit: 200,
      });
      setTransactions(data);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    reload();
  }, [month, categories, search]);

  function onCategoryChange(id: string, newCategory: string) {
    setTransactions((prev) =>
      prev.map((t) =>
        t.id === id
          ? { ...t, user_category_override: newCategory, effective_category: newCategory }
          : t,
      ),
    );
  }

  return (
    <div className="min-h-screen">
      <UploadDropzone onUploaded={reload} />
      <FilterBar
        month={month}
        setMonth={setMonth}
        categories={categories}
        setCategories={setCategories}
        search={search}
        setSearch={setSearch}
      />
      {loading ? (
        <p className="p-4 text-zinc-400 text-sm">로딩…</p>
      ) : (
        <TransactionList transactions={transactions} onCategoryChange={onCategoryChange} />
      )}
    </div>
  );
}
```

- [ ] **Step 4:** Build + 기존 테스트 회귀.

```bash
pnpm -C apps/web test
pnpm -C apps/web build
```

Expected: all PASS (TransactionList 기존 테스트가 깨질 수 있음 — props 변경 반영 후 통과).

### Task 25: Phase 5 Commit + PR

```bash
git add apps/web/src/lib/api.ts apps/web/src/components/CategoryChip.tsx apps/web/src/components/CategoryChip.test.tsx apps/web/src/components/FilterBar.tsx apps/web/src/components/FilterBar.test.tsx apps/web/src/components/TransactionList.tsx apps/web/src/routes/app.tsx
git commit -m "feat(web): /app 필터바 + CategoryChip 인라인 드롭다운

- lib/api.ts: fetchTransactions/fetchMonths/patchCategory + TransactionRow 타입
- CategoryChip: 19 enum 인라인 드롭다운, 낙관적 업데이트 + 실패 시 롤백
  - 오버라이드 표시 점(•)
  - unknown은 회색, 분류된 건 파란색
- FilterBar: 월 dropdown + 카테고리 multi-select + 가맹점 검색
- /app 페이지: FilterBar + UploadDropzone + TransactionList 통합 (effect로 자동 reload)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
git push -u origin feat/w3-phase5-app-filter
gh pr create --title "feat(web): /app 필터바 + CategoryChip 인라인 드롭다운" --body-file - <<'EOF'
## Summary
- 카테고리 인라인 드롭다운 (1클릭 변경, 낙관적 업데이트)
- FilterBar (월 / 카테고리 multi / 검색)
- /app 페이지 통합 — 필터 변경 시 자동 refetch

## Test plan
- [x] CategoryChip.test.tsx (4)
- [x] FilterBar.test.tsx (4)
- [x] pnpm build clean
EOF
gh pr checks --watch
gh pr merge --squash --delete-branch --subject "feat(web): /app 필터바 + CategoryChip 인라인 드롭다운 (#?)"
git checkout main && git pull --ff-only origin main
```

---

## Phase 6: `/dashboard` Tremor 4 위젯 (7 tasks)

**브랜치:** `feat/w3-phase6-dashboard-tremor`

### Task 26: 브랜치 + @tremor/react 의존성 추가

**Files:**
- Modify: `apps/web/package.json` + `pnpm-lock.yaml`

- [ ] **Step 1:**

```bash
git checkout -b feat/w3-phase6-dashboard-tremor
pnpm -C apps/web add @tremor/react
```

- [ ] **Step 2:** Tailwind config 확인 — Tremor가 자체 클래스 사용하므로 `tailwind.config.js`에 `@tremor/**/*.{js,ts,jsx,tsx}` content path 추가 필요:

```bash
cat apps/web/tailwind.config.js
```

content array 끝에 추가:

```js
content: [
  "./index.html",
  "./src/**/*.{js,ts,jsx,tsx}",
  "./node_modules/@tremor/**/*.{js,ts,jsx,tsx}",  // ← W3 추가
],
```

- [ ] **Step 3:** Build 검증 (Tremor import만 됐는지).

```bash
pnpm -C apps/web build
```

Expected: clean build.

### Task 27: dashboard API fetch 함수 추가

**Files:**
- Modify: `apps/web/src/lib/api.ts`

- [ ] **Step 1:** 파일 끝에 추가:

```typescript
export type SummaryResponse = {
  month: string;
  total_amount: string;
  transaction_count: number;
  prev_month: string;
  prev_month_total: string;
  prev_month_diff_pct: number | null;
};
export type CategoryBucket = { category: string; amount: string; count: number };
export type MonthBucket = { month: string; amount: string };
export type MerchantBucket = { merchant_raw: string; amount: string; count: number };

export async function fetchSummary(month: string): Promise<SummaryResponse> {
  const { data } = await api.get<SummaryResponse>(`/dashboard/summary?month=${month}`);
  return data;
}
export async function fetchByCategory(month: string): Promise<CategoryBucket[]> {
  const { data } = await api.get<CategoryBucket[]>(`/dashboard/by-category?month=${month}`);
  return data;
}
export async function fetchByMonth(lastN: number = 6): Promise<MonthBucket[]> {
  const { data } = await api.get<MonthBucket[]>(`/dashboard/by-month?last_n=${lastN}`);
  return data;
}
export async function fetchTopMerchants(month: string, limit: number = 5): Promise<MerchantBucket[]> {
  const { data } = await api.get<MerchantBucket[]>(`/dashboard/top-merchants?month=${month}&limit=${limit}`);
  return data;
}
```

### Task 28: `/dashboard` 페이지 본 구현 (Tremor 4 위젯)

**Files:**
- Modify: `apps/web/src/routes/dashboard.tsx`

- [ ] **Step 1:** placeholder를 전체 replace:

```tsx
import { useEffect, useState } from "react";
import { Card, DonutChart, BarChart, Title, Text, Metric } from "@tremor/react";
import {
  fetchMonths,
  fetchSummary,
  fetchByCategory,
  fetchByMonth,
  fetchTopMerchants,
  type SummaryResponse,
  type CategoryBucket,
  type MonthBucket,
  type MerchantBucket,
} from "../lib/api";

export function DashboardPage() {
  const [months, setMonths] = useState<string[]>([]);
  const [month, setMonth] = useState<string>("");
  const [summary, setSummary] = useState<SummaryResponse | null>(null);
  const [byCategory, setByCategory] = useState<CategoryBucket[]>([]);
  const [byMonth, setByMonth] = useState<MonthBucket[]>([]);
  const [topMerchants, setTopMerchants] = useState<MerchantBucket[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchMonths().then((ms) => {
      setMonths(ms);
      if (ms.length > 0 && !month) setMonth(ms[0]);
    });
  }, []);

  useEffect(() => {
    if (!month) return;
    setLoading(true);
    Promise.all([
      fetchSummary(month),
      fetchByCategory(month),
      fetchByMonth(6),
      fetchTopMerchants(month, 5),
    ])
      .then(([s, c, m, t]) => {
        setSummary(s);
        setByCategory(c);
        setByMonth(m);
        setTopMerchants(t);
      })
      .finally(() => setLoading(false));
  }, [month]);

  if (months.length === 0) {
    return <div className="p-8 text-zinc-400">아직 거래가 없습니다. /app에서 명세서를 업로드하세요.</div>;
  }

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center gap-3">
        <select
          value={month}
          onChange={(e) => setMonth(e.target.value)}
          className="bg-zinc-900 border border-zinc-700 rounded px-2 py-1 text-sm"
        >
          {months.map((m) => (
            <option key={m} value={m}>{m}</option>
          ))}
        </select>
        {summary && (
          <Text className="text-zinc-400">
            {summary.transaction_count}건 거래 · 합계 ₩{Number(summary.total_amount).toLocaleString()}
          </Text>
        )}
      </div>

      {loading ? (
        <p className="text-zinc-400 text-sm">로딩…</p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Card>
            <Title>카테고리별 지출</Title>
            <DonutChart
              data={byCategory.map((c) => ({ name: c.category, value: Number(c.amount) }))}
              category="value"
              index="name"
              valueFormatter={(v) => `₩${v.toLocaleString()}`}
            />
          </Card>

          <Card>
            <Title>월별 추이 (최근 6개월)</Title>
            <BarChart
              data={byMonth.map((m) => ({ month: m.month, amount: Number(m.amount) }))}
              index="month"
              categories={["amount"]}
              valueFormatter={(v) => `₩${v.toLocaleString()}`}
            />
          </Card>

          <Card>
            <Title>Top 5 가맹점</Title>
            <ul className="text-sm text-zinc-300 space-y-1 mt-2">
              {topMerchants.map((t, i) => (
                <li key={t.merchant_raw} className="flex justify-between">
                  <span>{i + 1}. {t.merchant_raw}</span>
                  <span>₩{Number(t.amount).toLocaleString()} ({t.count}건)</span>
                </li>
              ))}
            </ul>
          </Card>

          <Card>
            <Title>전월 대비</Title>
            <Metric>
              {summary && summary.prev_month_diff_pct !== null
                ? `${summary.prev_month_diff_pct > 0 ? "+" : ""}${summary.prev_month_diff_pct.toFixed(1)}%`
                : "전월 데이터 없음"}
            </Metric>
            {summary && summary.prev_month_diff_pct !== null && (
              <Text className="text-zinc-400">
                전월 ₩{Number(summary.prev_month_total).toLocaleString()} → 이번달 ₩{Number(summary.total_amount).toLocaleString()}
              </Text>
            )}
          </Card>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2:** 빌드 + dev 서버 띄워 시각 확인 (선택).

```bash
pnpm -C apps/web build
pnpm -C apps/web dev
```

브라우저에서 http://localhost:5173/dashboard 접속 (로그인 후) → 4 위젯 보이는지.

### Task 29: Phase 6 Commit + PR

```bash
git add apps/web/package.json apps/web/pnpm-lock.yaml apps/web/tailwind.config.js apps/web/src/lib/api.ts apps/web/src/routes/dashboard.tsx
git commit -m "feat(web): /dashboard with Tremor 4 위젯

- @tremor/react 의존성 추가, tailwind content path 추가
- lib/api.ts에 4 dashboard fetch 함수 + 타입
- /dashboard 페이지: 월 dropdown + 4 위젯 (도넛/막대/Top 5/전월 대비)
- 거래 없으면 빈 상태 메시지

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
git push -u origin feat/w3-phase6-dashboard-tremor
gh pr create --title "feat(web): /dashboard Tremor 4 위젯" --body-file - <<'EOF'
## Summary
- Tremor DonutChart / BarChart / Card / Metric 4 위젯
- 월 dropdown으로 4 API 동시 refetch

## Test plan
- [x] pnpm build clean
- [ ] dev 서버 + 본인 데이터로 시각 확인 (Phase 8 검수)
EOF
gh pr checks --watch
gh pr merge --squash --delete-branch --subject "feat(web): /dashboard Tremor 4 위젯 (#?)"
git checkout main && git pull --ff-only origin main
```

---

## Phase 7: 통장 룰북 회귀 검수 (3 tasks)

**브랜치:** `chore/w3-phase7-rulebook-rerun`

### Task 30: 본인 명세서 재분류 측정

**Files:** 없음 (운영 측정)

- [ ] **Step 1:** Phase 0~6 머지 후, Lightsail 운영 DB에서 W2 unknown 거래에 대해 새 룰북 재분류 측정.

```bash
ssh -i ~/.ssh/lightsail.pem ec2-user@$LIGHTSAIL_HOST
sudo docker compose -f /opt/spendlens/docker-compose.prod.yml exec postgres \
  psql -U postgres -d spendlens -c "SELECT category, COUNT(*) FROM transactions GROUP BY category ORDER BY 2 DESC;"
```

W2 측정값 (89 unknown / 17 매칭)과 비교. 19 enum 통장 거래는 직접 룰북에 추가됐으므로 즉시 매칭 — 다만 **기존 거래는 업로드 시점의 분류가 박혀있음**. 재분류하려면:

```sql
-- 옵션 A: 사용자가 본인 명세서 재업로드 (dedup으로 행은 그대로, category만 새로 채워질지 확인 필요)
-- 또는
-- 옵션 B: 운영 DB에서 unknown 거래만 manual 재분류 SQL (가맹점명 매칭)
```

**옵션 B (간단)** — 통장 거래만 직접 update:

```sql
UPDATE transactions SET category = 'savings'
  WHERE category = 'unknown' AND merchant_raw ~* '정기적금|적금|예금';

UPDATE transactions SET category = 'insurance'
  WHERE category = 'unknown' AND merchant_raw ~* 'CMS|보험|손해보험|하나생|화재';

UPDATE transactions SET category = 'income'
  WHERE category = 'unknown' AND merchant_raw ~* '월급|급여|수익|수당';

UPDATE transactions SET category = 'transfer'
  WHERE category = 'unknown' AND merchant_raw ~* '이체|송금|입금';

UPDATE transactions SET category = 'housing'
  WHERE category = 'unknown' AND merchant_raw ~* '월세|임대|관리비';
```

(주의: `~*`는 Postgres ILIKE 정규식. CHECK 제약 없으므로 안전.)

- [ ] **Step 2:** 분포 재측정:

```sql
SELECT category, COUNT(*) FROM transactions GROUP BY category ORDER BY 2 DESC;
```

Expected: unknown 50% 이하 (W2의 89 → 약 25~40으로 감소 예상).

### Task 31: 회귀 측정 결과를 회고에 기록

**Files:** (Phase 8에서 docs/retros/w3.md에 포함)

- [ ] **Step 1:** Phase 30의 측정값을 메모 (사용자 본인 데이터). Phase 8 회고 문서 작성 시 사용.

### Task 32: Phase 7 — PR 없음 (운영 측정만)

Phase 7은 운영 SQL UPDATE라 코드 변경 없음. PR 없이 Phase 8로 이어진다. (필요시 운영 측정 결과를 추후 commit message에 포함.)

---

## Phase 8: 운영 배포 + README/CHANGELOG/회고 (7 tasks)

**브랜치:** `chore/w3-phase8-deploy-docs`

### Task 33: 브랜치 + docker-compose.prod.yml 점검 (변경 없음 예상)

**Files:** none (검증만)

- [ ] **Step 1:**

```bash
git checkout -b chore/w3-phase8-deploy-docs
```

- [ ] **Step 2:** docker-compose.prod.yml은 W2에서 redis 추가했고 W3에선 변경 없음. 확인만:

```bash
cat infra/docker-compose.prod.yml
```

Expected: postgres / redis / api / caddy 4 서비스. 변경 불필요.

### Task 34: README 갱신

**Files:**
- Modify: `README.md`

- [ ] **Step 1:** Status 라인 + 지원 명세서 + Tech Stack 갱신:

```markdown
## Status
**W3 complete** — 본인 모드 UI 완성: 거래 필터/검색·인라인 카테고리 오버라이드·`/dashboard` (Tremor 4 위젯)·enum 14→19·통장 룰북 보강. Live:
- **Web:** https://spendlens.suim-app.store
- **Signup:** https://spendlens.suim-app.store/signup
- **App (login required):** https://spendlens.suim-app.store/app
- **Dashboard (login required):** https://spendlens.suim-app.store/dashboard
- **API healthz:** https://api.spendlens.suim-app.store/healthz
```

Tech Stack에 추가:
```markdown
- Charts: Tremor (Tailwind 기반 dashboard components)
```

지원 명세서 섹션 갱신 — 통장 적요도 자동 분류된다는 메모:
```markdown
- 하나은행 통장 XLSX — 정기적금/CMS/이체/월급/월세 자동 분류 (W3 룰북)
```

### Task 35: CHANGELOG W3 entry

**Files:**
- Modify: `CHANGELOG.md`

- [ ] **Step 1:** 최상단에 W3 섹션 추가 (W2 위에):

```markdown
## W3 — 2026-06-XX

### Added
- 카테고리 인라인 드롭다운 오버라이드 (`PATCH /transactions/{id}`)
- 거래 리스트 필터/검색 (`GET /transactions?month=&category=&search=&limit=&offset=`)
- 월 dropdown (`GET /transactions/months`)
- `/dashboard` 페이지: Tremor 4 위젯 (도넛 / 월별 추이 / Top 5 가맹점 / 전월 대비)
- 4 aggregate API (summary, by-category, by-month, top-merchants)
- enum 14 → 19 (savings/insurance/income/transfer/housing)
- 통장 룰북 5 패턴 (정기적금/CMS·보험/월급/이체/월세)
- 헤더 Nav 컴포넌트 (거래내역 / 대시보드 / 로그아웃)

### Changed
- `TransactionOut`에 `auto_category`, `user_category_override`, `effective_category` 추가
- `GET /transactions` 응답은 `COALESCE(override, category)` 기준
- 모든 dashboard 집계는 `amount > 0` (출금)만 (입금 분석은 W4+)

### Migrations
- `0003_add_user_category_override`

### Dependencies
- Frontend: `@tremor/react` 추가

```

### Task 36: 회고 문서 작성

**Files:**
- Create: `docs/retros/w3.md`

- [ ] **Step 1:** Create skeleton:

```markdown
# W3 Retro

기간: 2026-05-20 ~ 2026-06-XX

## Shipped (PR 8건+ squash merged to main)

| PR | 제목 |
|---|---|
| #N | feat(api): expand categories 14→19 + 통장 룰북 + override 컬럼 |
| #N | feat(api): PATCH /transactions/{id} for user category override |
| #N | feat(api): GET /transactions filter/search/pagination + months |
| #N | feat(api): dashboard aggregate APIs |
| #N | feat(web): Nav + /dashboard router |
| #N | feat(web): /app 필터바 + CategoryChip 인라인 드롭다운 |
| #N | feat(web): /dashboard Tremor 4 위젯 |
| #N | chore(infra): W3 production rollout + docs |

## What worked
- ...

## What hurt
- ...

## Numbers
- PR count:
- Test count delta:
- W2 unknown 89 → W3 unknown N (재분류율 (89-N)/89 = ...%)
- 신규 의존성: @tremor/react

## Carry into W4
- 월간 LLM 인사이트 리포트
- 필수/비필수 토글 (master plan P5)
- 비밀번호 재설정 / 이메일 인증 (SMTP)
- TanStack Query 도입 (서버 상태 캐시)
- 가맹점 정규화 (씨유 구로JNK점 vs 구로원룸점)
- 추가 카드사 (현대, 신한, 국민)
```

### Task 37: 운영 적용 + 검수 시나리오 12건

**Files:** 없음 (운영)

- [ ] **Step 1:** PR 8건 머지 후 자동으로 deploy-api 트리거. 컨테이너 entrypoint가 `alembic upgrade head`로 마이그레이션 0003 자동 적용.

```bash
ssh -i ~/.ssh/lightsail.pem ec2-user@$LIGHTSAIL_HOST
sudo docker compose -f /opt/spendlens/docker-compose.prod.yml ps
# api, postgres, redis, caddy 모두 healthy
sudo docker compose -f /opt/spendlens/docker-compose.prod.yml exec postgres \
  psql -U postgres -d spendlens -c "\d transactions" | grep user_category_override
# user_category_override 컬럼 보임
```

- [ ] **Step 2:** spec §13 검수 시나리오 12건 수동 실행 (브라우저):
  1. /login → 헤더에 거래내역/대시보드/로그아웃
  2. /app — 필터바 + 거래 리스트
  3. 월 dropdown
  4. 카테고리 multi-select
  5. 검색 input
  6. unknown 칩 클릭 → drop → groceries 선택 → 즉시 변경
  7. 새로고침 → 유지
  8. 재업로드 → user_category_override 보존
  9. /dashboard — 4 위젯
  10. /dashboard 월 변경 → 4 위젯 갱신
  11. W2 unknown 통장 거래가 19 enum + 룰북 5 패턴으로 분류된 비율 확인 (Phase 7 측정값)
  12. 19 외 PATCH → 422

### Task 38: Phase 8 commit + PR

```bash
git add README.md CHANGELOG.md docs/retros/w3.md
git commit -m "chore(infra): W3 production rollout — README/CHANGELOG/회고

- README: W3 complete, /app + /dashboard 라이브 URL, Tech Stack에 Tremor
- CHANGELOG W3 entry (Added/Changed/Migrations/Dependencies)
- docs/retros/w3.md 회고 (PR 목록, what worked/hurt, W4 carry-overs)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
git push -u origin chore/w3-phase8-deploy-docs
gh pr create --title "chore(infra): W3 production rollout — docs" --body-file - <<'EOF'
## Summary
- README Status → W3 complete + /dashboard URL
- CHANGELOG W3 entry
- 회고 (PR 목록 / numbers / W4 carry)

## Test plan
- [x] Lightsail compose ps healthy
- [x] /app 필터 + 인라인 드롭다운 검수
- [x] /dashboard 4 위젯 검수
- [x] W2 unknown 89 → W3 N 재분류율 측정
EOF
gh pr merge --squash --delete-branch --subject "chore(infra): W3 production rollout (#?)"
git checkout main && git pull --ff-only origin main
```

---

## Self-Review

### 1. Spec coverage

| Spec Done 항목 | 구현 Task |
|---|---|
| §2 #1 (마이그레이션 0003) | Task 03 |
| §2 #2 (enum 14→19) | Task 01 |
| §2 #3 (통장 룰북 5 패턴) | Task 01 |
| §2 #4 (LLM 프롬프트 19 enum) | Task 02 |
| §2 #5 (PATCH /transactions/{id}) | Task 06, 07 |
| §2 #6 (GET /transactions 쿼리) | Task 09, 10 |
| §2 #7 (4 dashboard aggregate API) | Task 12-17 |
| §2 #8 (/app 필터바 + CategoryChip) | Task 21-25 |
| §2 #9 (/dashboard 4 위젯) | Task 26-29 |
| §2 #10 (Nav 컴포넌트) | Task 18, 19 |
| §2 #11 (unknown 50% 이하 감소) | Task 30 |
| §2 #12 (PR 8건+ main 머지) | 매 Phase 끝 |
| §2 #13 (README/CHANGELOG/회고) | Task 34-36 |

### 2. Placeholder scan
- 모든 코드 step에 완전한 코드. "TBD"/"TODO" 없음.
- 한 가지 주의: Task 24의 `TransactionList.tsx` 수정은 "기존 코드를 봐야 정확히 알 수 있으므로 실 코드에 맞게 minor edit"이라고 명시 — 이는 실행 시점에 구체화될 부분. 패턴은 명시했음 (props 추가 + CategoryChip 사용).

### 3. Type consistency
- `TransactionOut`의 신규 3 필드 (`auto_category`/`user_category_override`/`effective_category`)가 backend (Task 04) → frontend `TransactionRow` (Task 21) → CategoryChip props (Task 22)에서 일관 사용.
- `CategoryLiteral` 19 enum이 backend (Task 04) → CategoryChip의 `CATEGORIES` array (Task 22) → FilterBar의 `CATEGORY_OPTIONS` (Task 23)에서 일관.
- dashboard API 4 응답 타입 (Task 12 routes.py)이 frontend `SummaryResponse`/`CategoryBucket`/`MonthBucket`/`MerchantBucket` (Task 27)에서 일치.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-20-w3-personal-mode-ui.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — Phase별 fresh subagent + 두 단계 review. W2와 동일 흐름.
2. **Inline Execution** — 이 세션에서 직접. 컨텍스트 누적 빠름.

W3는 9 Phase × 평균 4-5 task = **약 38 task**. W2(60 task)보다 가볍지만 frontend 비중 높음 — Tremor 통합/CategoryChip/FilterBar 등 시각 확인 필요한 작업 다수.

Which approach?
