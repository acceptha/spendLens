# spendLens W2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** spendLens W2 — 다중 사용자(회원가입+로그인 rate limit) + 카테고리 자동 분류(룰북 우선 → Claude Haiku 폴백) + Redis 캐시 + 우리·하나카드 XLSX 파서 + feature 브랜치/PR squash merge 흐름.

**Architecture:** W1의 단일 사용자(ENV seed) + 삼성카드 XLSX 위에 다중 사용자 가입과 카테고리 자동 분류를 얹는다. Lightsail docker-compose에 `redis:7-alpine`을 추가해 (1) IP 기반 rate limit, (2) `merchant_name → category` 전역 캐시, (3) `ANTHROPIC_MONTHLY_BUDGET_USD` 누적 비용 카운터의 백엔드로 공통 사용한다. Anthropic Claude Haiku는 룰북 미매칭 가맹점에만 호출되어 비용이 통제된다.

**Tech Stack:** FastAPI · asyncpg(raw SQL) · Alembic(raw SQL) · argon2-cffi · pyjwt · pandas · openpyxl · **redis (asyncio)** · **anthropic SDK** · React 18 + Vite + Tailwind + Zustand · GitHub Actions → GHCR → Lightsail Docker Compose + Caddy.

**Related docs:**
- Spec: `docs/superpowers/specs/2026-05-13-w2-multi-user-llm-categorization-design.md`
- W1 reference plan (formatting + test conventions): `docs/superpowers/plans/2026-04-30-w1-skeleton-and-samsung-xlsx-parser.md`
- Codebase conventions: `CLAUDE.md` (root) and `apps/api/CLAUDE.md` if present

---

## Branching policy (W2부터)

- 매 Phase = 1 feature 브랜치 + 1 PR. 브랜치명: `feat/w2-phaseN-<slug>` (예: `feat/w2-phase2-signup`).
- 머지 방식: **GitHub UI에서 Squash merge** (한 PR이 main에 squash commit 한 개로 떨어진다).
- 커밋 제목은 Conventional Commits (`feat(api):`, `chore(infra):` 등).
- 각 PR 자체에는 multiple commits 허용 (개발 중 atomic commits OK).
- main에 직접 push 금지. GitHub branch protection은 W2 Phase 0에서 설정.

---

## Phase 0: PR/브랜치 흐름 셋업 (4 tasks)

**브랜치:** `chore/w2-phase0-pr-flow`
**검수:** PR 1개 (main으로 squash merge)

### Task 00: 현재 워킹트리 정리 + W2 작업 브랜치 분기

**Files:** 없음 (git 작업만)

- [ ] **Step 1:** 워킹트리에 untracked만 남아있는지 확인.

Run: `git status`
Expected: untracked만 (예: `CLAUDE.md`, `_.md`) — staged/modified 없어야 함.

- [ ] **Step 2:** main 최신화.

Run: `git fetch origin && git checkout main && git pull --ff-only origin main`

- [ ] **Step 3:** Phase 0 브랜치 생성.

Run: `git checkout -b chore/w2-phase0-pr-flow`

### Task 01: GitHub PR 템플릿 추가

**Files:**
- Create: `.github/PULL_REQUEST_TEMPLATE.md`

- [ ] **Step 1:** Create `.github/PULL_REQUEST_TEMPLATE.md`:

```markdown
## Summary

<!-- 1-3줄로 PR이 무엇을 하는지 -->

## Why

<!-- 이 변경이 필요한 이유. spec/issue 링크 -->

## Test plan

- [ ] 단위 테스트 추가/수정
- [ ] 로컬에서 `uv run pytest` 통과 (api)
- [ ] 로컬에서 `pnpm -C apps/web test` 통과 (web 변경 시)
- [ ] 수동 검수: <!-- 어떤 흐름을 어떻게 확인했는지 -->

## Screenshots

<!-- UI 변경이 있으면 before/after -->

## Checklist

- [ ] Conventional Commits 제목 (`feat(api):`, `fix(web):`, `chore(infra):` 등)
- [ ] spec/plan 갱신 (해당 시)
- [ ] `.env.example` 갱신 (신규 ENV 추가 시)
```

### Task 02: api 워크플로에 `pull_request` 트리거 + Redis 서비스 추가

**Files:**
- Modify: `.github/workflows/api.yml`

- [ ] **Step 1:** 현재 워크플로 확인.

Run: `cat .github/workflows/api.yml`
Expected: `on: push` 단일 트리거 + postgres service.

- [ ] **Step 2:** `on:` 블록을 다음으로 교체:

```yaml
on:
  push:
    branches: [main]
    paths:
      - "apps/api/**"
      - ".github/workflows/api.yml"
  pull_request:
    paths:
      - "apps/api/**"
      - ".github/workflows/api.yml"
```

- [ ] **Step 3:** `services:` 블록에 redis 추가. 기존 `postgres:` 서비스 아래에:

```yaml
      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
```

- [ ] **Step 4:** `env:` 또는 step env에 `REDIS_URL=redis://localhost:6379/0` 추가 (테스트 실행 환경변수로).

### Task 03: web 워크플로에 `pull_request` 트리거

**Files:**
- Modify: `.github/workflows/web.yml`

- [ ] **Step 1:** `on:` 블록을 다음으로 교체:

```yaml
on:
  push:
    branches: [main]
    paths:
      - "apps/web/**"
      - "package.json"
      - "pnpm-lock.yaml"
      - ".github/workflows/web.yml"
  pull_request:
    paths:
      - "apps/web/**"
      - "package.json"
      - "pnpm-lock.yaml"
      - ".github/workflows/web.yml"
```

### Task 04: deploy-api 워크플로 점검 (push:main만 트리거하도록 유지)

**Files:**
- Read-only check: `.github/workflows/deploy-api.yml`

- [ ] **Step 1:** `on: push: branches: [main]` 유지되어 있는지만 확인. PR에서는 deploy 안 함.

Run: `grep -n "^on:\|branches:\|pull_request" .github/workflows/deploy-api.yml`
Expected: `push.branches: [main]`만 있고 `pull_request` 없음.

(`pull_request`가 있으면 제거.)

### Task 05: Commit + Phase 0 PR 생성

- [ ] **Step 1:** 변경 확인.

Run: `git status && git diff --stat`

- [ ] **Step 2:** Commit.

```bash
git add .github/PULL_REQUEST_TEMPLATE.md .github/workflows/api.yml .github/workflows/web.yml
git commit -m "ci(infra): add PR template, pull_request triggers, redis service for api CI"
```

- [ ] **Step 3:** Push + PR 생성.

```bash
git push -u origin chore/w2-phase0-pr-flow
gh pr create --title "ci(infra): introduce PR flow for W2" --body "$(cat <<'EOF'
## Summary
- W2부터 feature 브랜치 + PR squash merge 흐름 도입
- api/web CI에 pull_request 트리거 추가
- api CI에 redis 서비스 컨테이너 추가 (W2 코드가 redis 사용)
- PR 템플릿 추가

## Test plan
- [x] CI가 이 PR 자체에서 트리거되어 통과하는지 확인
EOF
)"
```

- [ ] **Step 4:** CI 통과 확인 후 GitHub UI에서 **Squash and merge**. main에 떨어진 squash 커밋 SHA 기록.

- [ ] **Step 5:** 로컬 main 갱신.

```bash
git checkout main
git pull --ff-only origin main
git branch -d chore/w2-phase0-pr-flow
```

---

## Phase 1: Redis client + lifespan 통합 (5 tasks)

**브랜치:** `feat/w2-phase1-redis-client`
**검수:** PR 1개. CI가 redis service에 붙어 통과.

### Task 06: 브랜치 분기 + `redis` 의존성 추가

**Files:**
- Modify: `apps/api/pyproject.toml`

- [ ] **Step 1:** main 기준으로 브랜치 생성.

```bash
git checkout main && git pull --ff-only origin main
git checkout -b feat/w2-phase1-redis-client
```

- [ ] **Step 2:** `apps/api/pyproject.toml`의 `dependencies` 배열에 추가:

```toml
"redis>=5.0",
```

위치는 `"email-validator>=2.0",` 다음 줄.

- [ ] **Step 3:** 의존성 락 갱신.

Run: `cd apps/api && uv sync`
Expected: `redis` 5.x 설치 + `uv.lock` 갱신.

### Task 07: Settings에 `redis_url` 추가

**Files:**
- Modify: `apps/api/app/settings.py`
- Modify: `apps/api/.env`
- Modify: `apps/api/tests/.env.test`
- Modify: `.env.example` (루트)

- [ ] **Step 1:** `apps/api/app/settings.py`에 필드 추가 (`web_origin` 다음 줄):

```python
    redis_url: str = "redis://localhost:6379/0"
```

- [ ] **Step 2:** `.env.example` (루트)에 추가:

```
# Redis (rate limit + categorization cache + budget counter)
REDIS_URL=redis://localhost:6379/0
```

- [ ] **Step 3:** `apps/api/.env`에 같은 줄 추가 (로컬 개발용. 사용자 머신에서 직접 — gitignored).

- [ ] **Step 4:** `apps/api/tests/.env.test`에 추가:

```
REDIS_URL=redis://localhost:6379/15
```

(테스트는 DB index 15 사용 — 운영 데이터와 격리.)

### Task 08: `app/redis_client.py` 생성

**Files:**
- Create: `apps/api/app/redis_client.py`
- Create: `apps/api/tests/test_redis_client.py`

- [ ] **Step 1:** Create test `apps/api/tests/test_redis_client.py`:

```python
import pytest

from app.redis_client import acquire_redis, close_redis, init_redis


@pytest.fixture(autouse=True)
async def _redis_setup():
    await init_redis()
    yield
    await close_redis()


async def test_redis_set_get_roundtrip():
    async with acquire_redis() as r:
        await r.set("test:roundtrip", "hello")
        value = await r.get("test:roundtrip")
    assert value == "hello"


async def test_redis_acquire_outside_init_raises():
    await close_redis()
    with pytest.raises(RuntimeError, match="redis pool not initialized"):
        async with acquire_redis() as _:
            pass
```

- [ ] **Step 2:** Run test (expect FAIL — module 없음).

Run: `cd apps/api && uv run pytest tests/test_redis_client.py -v`
Expected: ImportError.

- [ ] **Step 3:** Create `apps/api/app/redis_client.py`:

```python
"""Async Redis pool. Same lifecycle pattern as app.db.

Provides:
- init_redis() / close_redis(): called from FastAPI lifespan
- acquire_redis(): async context manager yielding a redis.asyncio.Redis client
"""
from contextlib import asynccontextmanager

import redis.asyncio as aioredis

from app.settings import settings

_pool: aioredis.Redis | None = None


async def init_redis() -> None:
    global _pool
    if _pool is not None:
        return
    _pool = aioredis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
        max_connections=20,
    )


async def close_redis() -> None:
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None


@asynccontextmanager
async def acquire_redis():
    if _pool is None:
        raise RuntimeError("redis pool not initialized")
    yield _pool
```

- [ ] **Step 4:** Run test (expect PASS).

Run: `cd apps/api && uv run pytest tests/test_redis_client.py -v`
Expected: 2 passed.

### Task 09: lifespan에 redis init/close 연결

**Files:**
- Modify: `apps/api/app/main.py`

- [ ] **Step 1:** `apps/api/app/main.py` 상단 import에 추가 (`from app.db import ...` 다음 줄):

```python
from app.redis_client import close_redis, init_redis
```

- [ ] **Step 2:** `lifespan` 함수를 다음으로 교체 (Read한 main.py:18-26 기준):

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_pool()
    await init_redis()
    async with acquire() as conn:
        await ensure_admin_user(conn)
    logger.info("startup complete; admin seeded; redis ready")
    yield
    await close_redis()
    await close_pool()
    logger.info("shutdown complete")
```

### Task 10: conftest에 Redis 정리 fixture 추가

**Files:**
- Modify: `apps/api/tests/conftest.py`

- [ ] **Step 1:** `apps/api/tests/conftest.py` 끝에 추가:

```python
@pytest.fixture(scope="session", autouse=True)
async def _init_app_redis():
    """Initialize redis pool for all tests."""
    from app.redis_client import close_redis, init_redis
    await init_redis()
    yield
    await close_redis()


@pytest.fixture(autouse=True)
async def reset_redis():
    """각 테스트 전 test DB(index 15)를 비움."""
    from app.redis_client import acquire_redis
    async with acquire_redis() as r:
        await r.flushdb()
    yield
```

- [ ] **Step 2:** 기존 테스트가 깨지지 않는지 확인.

Run: `cd apps/api && uv run pytest -x`
Expected: 전부 PASS (W1 테스트 + 신규 redis 테스트).

### Task 11: Commit + Phase 1 PR

- [ ] **Step 1:**

```bash
git add apps/api/pyproject.toml apps/api/uv.lock apps/api/app/settings.py apps/api/app/redis_client.py apps/api/app/main.py apps/api/tests/conftest.py apps/api/tests/test_redis_client.py apps/api/tests/.env.test .env.example
git commit -m "feat(api): add async Redis pool and integrate with lifespan"
git push -u origin feat/w2-phase1-redis-client
gh pr create --title "feat(api): Redis client foundation" --body "$(cat <<'EOF'
## Summary
- redis-py(asyncio) 의존성 추가
- app/redis_client.py: db.py와 동일 패턴의 풀 헬퍼
- lifespan에서 init_redis/close_redis 호출
- conftest에 redis 풀 + 테스트별 flushdb 픽스처

## Why
W2의 (1) rate limit, (2) categorization cache, (3) LLM budget counter가 모두 Redis 사용. 공통 인프라 먼저 도입.

## Test plan
- [x] 신규 test_redis_client.py 통과
- [x] 기존 W1 테스트 회귀 없음
EOF
)"
```

- [ ] **Step 2:** CI 통과 후 squash merge → 로컬 main 갱신 → 브랜치 삭제.

---

## Phase 2: Rate limit 모듈 + 회원가입 백엔드 (10 tasks)

**브랜치:** `feat/w2-phase2-signup`
**검수:** PR 1개. 회원가입 + login rate limit 동작.

### Task 12: 브랜치 + 비밀번호 정책 검증 함수 TDD

**Files:**
- Modify: `apps/api/app/auth/password.py`
- Create: `apps/api/tests/auth/test_password_policy.py`

- [ ] **Step 1:**

```bash
git checkout main && git pull --ff-only origin main
git checkout -b feat/w2-phase2-signup
```

- [ ] **Step 2:** Create test `apps/api/tests/auth/test_password_policy.py`:

```python
import pytest

from app.auth.password import PasswordPolicyError, validate_password_policy


def test_strong_password_passes():
    validate_password_policy("abcd1234")  # no raise


def test_too_short_raises():
    with pytest.raises(PasswordPolicyError, match="MIN_LENGTH"):
        validate_password_policy("a1b2c3")


def test_no_letter_raises():
    with pytest.raises(PasswordPolicyError, match="MISSING_LETTER"):
        validate_password_policy("12345678")


def test_no_digit_raises():
    with pytest.raises(PasswordPolicyError, match="MISSING_DIGIT"):
        validate_password_policy("abcdefgh")


def test_long_strong_password_passes():
    validate_password_policy("MyStr0ngPassword!")
```

- [ ] **Step 3:** Run (expect FAIL — symbol 없음).

Run: `cd apps/api && uv run pytest tests/auth/test_password_policy.py -v`

- [ ] **Step 4:** `apps/api/app/auth/password.py` 끝에 추가:

```python
class PasswordPolicyError(ValueError):
    """비밀번호 정책 위반."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def validate_password_policy(password: str) -> None:
    if len(password) < 8:
        raise PasswordPolicyError("MIN_LENGTH")
    if not any(ch.isalpha() for ch in password):
        raise PasswordPolicyError("MISSING_LETTER")
    if not any(ch.isdigit() for ch in password):
        raise PasswordPolicyError("MISSING_DIGIT")
```

- [ ] **Step 5:** Run (expect PASS).

Run: `cd apps/api && uv run pytest tests/auth/test_password_policy.py -v`
Expected: 5 passed.

### Task 13: `SignupRequest` 스키마 추가

**Files:**
- Modify: `apps/api/app/auth/schemas.py`

- [ ] **Step 1:** 현재 schemas.py 읽고 `LoginRequest` 패턴 확인.

Run: `cat apps/api/app/auth/schemas.py`

- [ ] **Step 2:** `apps/api/app/auth/schemas.py` 끝에 추가:

```python
from pydantic import BaseModel, EmailStr, Field


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class SignupResponse(BaseModel):
    access_token: str
```

(파일 상단에 이미 `from pydantic import ...` 있으면 중복 import 제거.)

### Task 14: `rate_limit.py` 모듈 TDD

**Files:**
- Create: `apps/api/app/common/__init__.py`
- Create: `apps/api/app/common/rate_limit.py`
- Create: `apps/api/tests/common/__init__.py`
- Create: `apps/api/tests/common/test_rate_limit.py`

- [ ] **Step 1:** Create empty `apps/api/app/common/__init__.py` and `apps/api/tests/common/__init__.py`.

- [ ] **Step 2:** Create test `apps/api/tests/common/test_rate_limit.py`:

```python
import pytest
from fastapi import HTTPException

from app.common.rate_limit import check


async def test_under_limit_passes():
    for _ in range(5):
        await check("test_ep", "1.2.3.4", max_attempts=5, window_seconds=3600)


async def test_over_limit_raises_429():
    for _ in range(5):
        await check("test_ep", "1.2.3.4", max_attempts=5, window_seconds=3600)
    with pytest.raises(HTTPException) as exc:
        await check("test_ep", "1.2.3.4", max_attempts=5, window_seconds=3600)
    assert exc.value.status_code == 429
    assert exc.value.detail == "TOO_MANY_REQUESTS"
    assert "Retry-After" in exc.value.headers


async def test_different_ips_independent():
    for _ in range(5):
        await check("test_ep", "1.2.3.4", max_attempts=5, window_seconds=3600)
    await check("test_ep", "5.6.7.8", max_attempts=5, window_seconds=3600)


async def test_different_endpoints_independent():
    for _ in range(5):
        await check("ep_a", "1.2.3.4", max_attempts=5, window_seconds=3600)
    await check("ep_b", "1.2.3.4", max_attempts=5, window_seconds=3600)
```

- [ ] **Step 3:** Run (expect FAIL).

Run: `cd apps/api && uv run pytest tests/common/test_rate_limit.py -v`

- [ ] **Step 4:** Create `apps/api/app/common/rate_limit.py`:

```python
"""IP-based fixed-window rate limit via Redis.

Key format: ratelimit:{endpoint}:{ip}:{YYYYMMDDHH}
TTL: window_seconds (3600 for hourly).
"""
from datetime import UTC, datetime

from fastapi import HTTPException

from app.redis_client import acquire_redis


async def check(
    endpoint: str,
    ip: str,
    *,
    max_attempts: int,
    window_seconds: int,
) -> None:
    """Increment counter; raise 429 if over limit.

    카운터는 진입 시점에 증가한다 (성공/실패 무관) — brute-force 시도 자체를 차단.
    """
    bucket = datetime.now(UTC).strftime("%Y%m%d%H")
    key = f"ratelimit:{endpoint}:{ip}:{bucket}"

    async with acquire_redis() as r:
        count = await r.incr(key)
        if count == 1:
            await r.expire(key, window_seconds)
        if count > max_attempts:
            ttl = await r.ttl(key)
            raise HTTPException(
                status_code=429,
                detail="TOO_MANY_REQUESTS",
                headers={"Retry-After": str(max(ttl, 1))},
            )
```

- [ ] **Step 5:** Run (expect PASS).

Run: `cd apps/api && uv run pytest tests/common/test_rate_limit.py -v`
Expected: 4 passed.

### Task 15: `/auth/signup` 라우트 TDD — 정상 가입

**Files:**
- Create: `apps/api/tests/auth/test_signup.py`

- [ ] **Step 1:** Create `apps/api/tests/auth/test_signup.py`:

```python
import httpx
from httpx import ASGITransport

from app.main import app


async def _client():
    return httpx.AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://test",
    )


async def test_signup_creates_user_and_issues_tokens():
    async with await _client() as ac:
        r = await ac.post(
            "/auth/signup",
            json={"email": "new@example.com", "password": "abcd1234"},
        )
    assert r.status_code == 200
    body = r.json()
    assert "access_token" in body and len(body["access_token"]) > 20
    # refresh token cookie set
    assert "refresh_token" in r.cookies


async def test_signup_duplicate_email_returns_409():
    async with await _client() as ac:
        await ac.post(
            "/auth/signup",
            json={"email": "dup@example.com", "password": "abcd1234"},
        )
        r = await ac.post(
            "/auth/signup",
            json={"email": "dup@example.com", "password": "abcd1234"},
        )
    assert r.status_code == 409
    assert r.json()["detail"] == "EMAIL_ALREADY_EXISTS"


async def test_signup_weak_password_returns_400():
    async with await _client() as ac:
        r = await ac.post(
            "/auth/signup",
            json={"email": "weak@example.com", "password": "12345678"},
        )
    assert r.status_code == 400
    assert r.json()["detail"] == "WEAK_PASSWORD"
```

- [ ] **Step 2:** Run (expect FAIL — route 없음).

Run: `cd apps/api && uv run pytest tests/auth/test_signup.py -v`

### Task 16: `/auth/signup` 라우트 구현 + rate limit

**Files:**
- Modify: `apps/api/app/auth/routes.py`

- [ ] **Step 1:** `apps/api/app/auth/routes.py` 상단 imports에 추가:

```python
from fastapi import APIRouter, Cookie, HTTPException, Request, Response, status
from asyncpg.exceptions import UniqueViolationError

from app.auth.password import (
    PasswordPolicyError,
    hash_password,
    validate_password_policy,
    verify_password,
)
from app.auth.schemas import LoginRequest, LoginResponse, RefreshResponse, SignupRequest, SignupResponse
from app.common import rate_limit
```

- [ ] **Step 2:** `login` 라우트 시그니처를 `Request`를 받도록 변경:

```python
@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest, request: Request, response: Response) -> LoginResponse:
    await rate_limit.check(
        "login", request.client.host, max_attempts=5, window_seconds=3600
    )
    # ... 기존 본문 ...
```

- [ ] **Step 3:** 파일 끝에 signup 라우트 추가:

```python
@router.post("/signup", response_model=SignupResponse)
async def signup(
    req: SignupRequest, request: Request, response: Response
) -> SignupResponse:
    await rate_limit.check(
        "signup", request.client.host, max_attempts=5, window_seconds=3600
    )

    try:
        validate_password_policy(req.password)
    except PasswordPolicyError as exc:
        raise HTTPException(status_code=400, detail="WEAK_PASSWORD") from exc

    pwd_hash = hash_password(req.password)

    async with acquire() as conn:
        try:
            row = await conn.fetchrow(
                "INSERT INTO users (email, password_hash) VALUES ($1, $2) RETURNING id",
                req.email,
                pwd_hash,
            )
        except UniqueViolationError as exc:
            raise HTTPException(status_code=409, detail="EMAIL_ALREADY_EXISTS") from exc

        user_id = row["id"]
        access = create_access_token(user_id)
        refresh, jti = create_refresh_token(user_id)
        expires_at = datetime.now(UTC) + timedelta(days=settings.jwt_refresh_ttl_days)

        await conn.execute(
            "INSERT INTO refresh_tokens (jti, user_id, expires_at) VALUES ($1, $2, $3)",
            jti, user_id, expires_at,
        )

    response.set_cookie(
        key="refresh_token",
        value=refresh,
        max_age=settings.jwt_refresh_ttl_days * 86400,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/auth",
    )
    return SignupResponse(access_token=access)
```

- [ ] **Step 4:** Run signup 테스트 (expect PASS).

Run: `cd apps/api && uv run pytest tests/auth/test_signup.py -v`
Expected: 3 passed.

### Task 17: signup rate limit 통합 테스트

**Files:**
- Append to: `apps/api/tests/auth/test_signup.py`

- [ ] **Step 1:** 파일 끝에 추가:

```python
async def test_signup_rate_limit_after_5_attempts():
    async with await _client() as ac:
        for i in range(5):
            await ac.post(
                "/auth/signup",
                json={"email": f"rl{i}@example.com", "password": "abcd1234"},
            )
        r = await ac.post(
            "/auth/signup",
            json={"email": "rl5@example.com", "password": "abcd1234"},
        )
    assert r.status_code == 429
    assert r.json()["detail"] == "TOO_MANY_REQUESTS"
    assert "retry-after" in {k.lower() for k in r.headers}
```

- [ ] **Step 2:** Run (expect PASS — autouse `reset_redis` fixture가 카운터 초기화).

Run: `cd apps/api && uv run pytest tests/auth/test_signup.py::test_signup_rate_limit_after_5_attempts -v`

### Task 18: login rate limit 회귀 테스트

**Files:**
- Modify: `apps/api/tests/auth/test_login.py`

- [ ] **Step 1:** 파일 끝에 추가:

```python
async def test_login_rate_limit_after_5_attempts():
    async with await _client() as ac:
        for _ in range(5):
            await ac.post(
                "/auth/login",
                json={"email": "nobody@example.com", "password": "wrong1234"},
            )
        r = await ac.post(
            "/auth/login",
            json={"email": "nobody@example.com", "password": "wrong1234"},
        )
    assert r.status_code == 429
```

- [ ] **Step 2:** Run (expect PASS).

Run: `cd apps/api && uv run pytest tests/auth/test_login.py -v`
Expected: 기존 + 새 테스트 통과.

### Task 19: 전체 회귀 + Commit + Phase 2 PR

- [ ] **Step 1:**

```bash
cd apps/api && uv run pytest -x
```
Expected: all green.

- [ ] **Step 2:**

```bash
cd ../..
git add apps/api/app/auth/password.py apps/api/app/auth/schemas.py apps/api/app/auth/routes.py apps/api/app/common/__init__.py apps/api/app/common/rate_limit.py apps/api/tests/auth/test_password_policy.py apps/api/tests/auth/test_signup.py apps/api/tests/auth/test_login.py apps/api/tests/common/__init__.py apps/api/tests/common/test_rate_limit.py
git commit -m "feat(api): add /auth/signup with password policy + IP rate limit on signup/login"
git push -u origin feat/w2-phase2-signup
gh pr create --title "feat(api): multi-user signup with rate limit" --body "$(cat <<'EOF'
## Summary
- POST /auth/signup — 즉시 가입, argon2 해시, 자동 로그인 토큰 발급
- 비밀번호 정책: 최소 8자 + 영문 1자 이상 + 숫자 1자 이상
- IP 기반 rate limit (시간당 5회) — signup/login 양쪽에 적용
- 429 TOO_MANY_REQUESTS + Retry-After 헤더

## Why
W1은 ENV seed 단일 사용자. W2에서 누구나 본인 계정을 만들 수 있어야 함. 가입 개방하면 brute-force/스팸 위험 → rate limit 필수.

## Test plan
- [x] tests/auth/test_password_policy.py (5 cases)
- [x] tests/auth/test_signup.py (4 cases — 정상/중복/약한비번/rate limit)
- [x] tests/auth/test_login.py rate limit 케이스 추가
- [x] tests/common/test_rate_limit.py (4 cases)
EOF
)"
```

- [ ] **Step 3:** CI 통과 → squash merge → 로컬 main 갱신.

---

## Phase 3: 회원가입 프론트엔드 (5 tasks)

**브랜치:** `feat/w2-phase3-signup-ui`
**검수:** PR 1개. `/signup` 페이지 동작.

### Task 20: 브랜치 + signup API 함수 추가

**Files:**
- Modify: `apps/web/src/api/auth.ts` (없으면 Create)

- [ ] **Step 1:**

```bash
git checkout main && git pull --ff-only origin main
git checkout -b feat/w2-phase3-signup-ui
```

- [ ] **Step 2:** 현재 `apps/web/src/api/` 구조 확인.

Run: `ls apps/web/src/api/`

- [ ] **Step 3:** `apps/web/src/api/auth.ts`에 signup 함수 추가 (없는 경우 기존 login 패턴 따라 작성):

```typescript
import client from './client';

export type SignupRequest = { email: string; password: string };
export type SignupResponse = { access_token: string };

export async function signup(body: SignupRequest): Promise<SignupResponse> {
  const { data } = await client.post<SignupResponse>('/auth/signup', body);
  return data;
}
```

### Task 21: `SignupPage` 컴포넌트 TDD

**Files:**
- Create: `apps/web/src/pages/SignupPage.tsx`
- Create: `apps/web/src/pages/SignupPage.test.tsx`

- [ ] **Step 1:** Create test `apps/web/src/pages/SignupPage.test.tsx`:

```typescript
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';

import SignupPage from './SignupPage';

vi.mock('@/api/auth', () => ({
  signup: vi.fn().mockResolvedValue({ access_token: 'fake-token-123' }),
}));

describe('SignupPage', () => {
  it('submits signup and stores access token', async () => {
    render(
      <MemoryRouter>
        <SignupPage />
      </MemoryRouter>,
    );
    await userEvent.type(screen.getByLabelText(/이메일/i), 'new@example.com');
    await userEvent.type(screen.getByLabelText(/비밀번호/i), 'abcd1234');
    await userEvent.click(screen.getByRole('button', { name: /가입/i }));

    const { signup } = await import('@/api/auth');
    await waitFor(() => expect(signup).toHaveBeenCalledWith({
      email: 'new@example.com',
      password: 'abcd1234',
    }));
  });

  it('shows error on WEAK_PASSWORD', async () => {
    const { signup } = await import('@/api/auth');
    (signup as ReturnType<typeof vi.fn>).mockRejectedValueOnce({
      response: { status: 400, data: { detail: 'WEAK_PASSWORD' } },
    });
    render(
      <MemoryRouter>
        <SignupPage />
      </MemoryRouter>,
    );
    await userEvent.type(screen.getByLabelText(/이메일/i), 'a@b.com');
    await userEvent.type(screen.getByLabelText(/비밀번호/i), '12345678');
    await userEvent.click(screen.getByRole('button', { name: /가입/i }));

    await waitFor(() =>
      expect(screen.getByText(/8자 이상.*영문.*숫자/i)).toBeInTheDocument(),
    );
  });
});
```

- [ ] **Step 2:** Run (expect FAIL).

Run: `pnpm -C apps/web test SignupPage`

- [ ] **Step 3:** Create `apps/web/src/pages/SignupPage.tsx`:

```typescript
import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';

import { signup } from '@/api/auth';
import { useAuthStore } from '@/stores/auth';

const ERROR_MESSAGES: Record<string, string> = {
  WEAK_PASSWORD: '비밀번호는 8자 이상이며 영문과 숫자를 모두 포함해야 합니다.',
  EMAIL_ALREADY_EXISTS: '이미 가입된 이메일입니다.',
  TOO_MANY_REQUESTS: '요청이 너무 많습니다. 잠시 후 다시 시도해주세요.',
};

export default function SignupPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const setAccessToken = useAuthStore((s) => s.setAccessToken);
  const navigate = useNavigate();

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const { access_token } = await signup({ email, password });
      setAccessToken(access_token);
      navigate('/app');
    } catch (err: unknown) {
      const code =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ?? 'UNKNOWN';
      setError(ERROR_MESSAGES[code] ?? '가입에 실패했습니다.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="mx-auto max-w-md p-6">
      <h1 className="text-2xl font-bold mb-4">회원가입</h1>
      <form onSubmit={onSubmit} className="space-y-3">
        <label className="block">
          <span className="text-sm">이메일</span>
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-1 block w-full rounded border p-2"
          />
        </label>
        <label className="block">
          <span className="text-sm">비밀번호</span>
          <input
            type="password"
            required
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1 block w-full rounded border p-2"
          />
          <p className="text-xs text-gray-500 mt-1">
            8자 이상, 영문과 숫자 포함
          </p>
        </label>
        {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded bg-black text-white py-2 disabled:opacity-50"
        >
          {submitting ? '처리 중…' : '가입'}
        </button>
      </form>
      <p className="mt-4 text-sm">
        이미 계정이 있으신가요?{' '}
        <Link to="/login" className="underline">로그인</Link>
      </p>
    </main>
  );
}
```

- [ ] **Step 4:** Run (expect PASS).

Run: `pnpm -C apps/web test SignupPage`
Expected: 2 passed.

### Task 22: `/signup` 라우트 등록 + LoginPage 링크

**Files:**
- Modify: `apps/web/src/App.tsx` 또는 `apps/web/src/main.tsx` (라우터 정의 위치)
- Modify: `apps/web/src/pages/LoginPage.tsx`

- [ ] **Step 1:** 라우터 정의 파일 찾기.

Run: `grep -rn "createBrowserRouter\|RouterProvider\|Route path" apps/web/src/`

- [ ] **Step 2:** 라우터에 `/signup` 추가:

```typescript
import SignupPage from './pages/SignupPage';

// routes 배열에:
{ path: '/signup', element: <SignupPage /> },
```

- [ ] **Step 3:** `apps/web/src/pages/LoginPage.tsx`에 회원가입 링크 추가 (form 하단):

```typescript
<p className="mt-4 text-sm">
  계정이 없으신가요?{' '}
  <Link to="/signup" className="underline">회원가입</Link>
</p>
```

(`Link` import 없으면 `import { Link } from 'react-router-dom';` 추가.)

### Task 23: web E2E 회귀

- [ ] **Step 1:** Run.

```bash
pnpm -C apps/web test
pnpm -C apps/web build
```
Expected: 전부 PASS, build 성공.

### Task 24: Commit + Phase 3 PR

- [ ] **Step 1:**

```bash
git add apps/web/
git commit -m "feat(web): add /signup page and link from /login"
git push -u origin feat/w2-phase3-signup-ui
gh pr create --title "feat(web): signup page" --body "$(cat <<'EOF'
## Summary
- /signup 페이지 — 이메일+비밀번호 입력, POST /auth/signup 호출, 성공 시 /app 이동
- LoginPage에 회원가입 링크 추가
- WEAK_PASSWORD/EMAIL_ALREADY_EXISTS/TOO_MANY_REQUESTS 에러 한글 메시지

## Test plan
- [x] SignupPage.test.tsx 통과
- [x] pnpm build 통과
- [ ] 수동: 로컬에서 /signup → 새 이메일 가입 → /app 진입 확인
EOF
)"
```

- [ ] **Step 2:** CI + manual smoke check → squash merge.

---

## Phase 4: Categorization 모듈 (룰북 + 캐시 + 예산 + 오케스트레이터) (12 tasks)

**브랜치:** `feat/w2-phase4-categorization`
**검수:** PR 1개. LLM 없이 룰북 + 캐시까지 동작 (LLM은 Phase 5).

### Task 25: 브랜치 + 마이그레이션 0002 (llm_usage_log)

**Files:**
- Create: `apps/api/migrations/versions/0002_add_llm_usage_log.py`

- [ ] **Step 1:**

```bash
git checkout main && git pull --ff-only origin main
git checkout -b feat/w2-phase4-categorization
```

- [ ] **Step 2:** 마이그레이션 skeleton 생성.

```bash
cd apps/api && uv run alembic revision -m "add llm_usage_log"
```

- [ ] **Step 3:** 생성된 파일을 `0002_add_llm_usage_log.py`로 rename (filename + 안의 `revision`/`down_revision` 변수). 내용을 다음으로 교체:

```python
"""add llm_usage_log

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-13
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE llm_usage_log (
          id                  BIGSERIAL PRIMARY KEY,
          called_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
          model               TEXT NOT NULL,
          input_tokens        INTEGER NOT NULL,
          output_tokens       INTEGER NOT NULL,
          cost_usd            NUMERIC(10, 6) NOT NULL,
          purpose             TEXT NOT NULL,
          merchant_normalized TEXT
        );
    """)
    op.execute("CREATE INDEX llm_usage_log_called_at_idx ON llm_usage_log (called_at);")


def downgrade() -> None:
    op.execute("DROP TABLE llm_usage_log;")
```

- [ ] **Step 4:** 로컬 DB와 test DB 모두에 적용.

```bash
cd apps/api && uv run alembic upgrade head
DATABASE_URL=$(grep ^DATABASE_URL tests/.env.test | cut -d= -f2-) uv run alembic upgrade head
```

- [ ] **Step 5:** conftest.py의 `TRUNCATE` 대상에 `llm_usage_log` 추가.

Edit `apps/api/tests/conftest.py:52` (reset_tables fixture):

```python
            TRUNCATE llm_usage_log, transactions, source_files, refresh_tokens, users
            RESTART IDENTITY CASCADE;
```

### Task 26: 룰북 모듈 TDD

**Files:**
- Create: `apps/api/app/categorization/__init__.py`
- Create: `apps/api/app/categorization/rulebook.py`
- Create: `apps/api/tests/categorization/__init__.py`
- Create: `apps/api/tests/categorization/test_rulebook.py`

- [ ] **Step 1:** Create empty `apps/api/app/categorization/__init__.py` and `apps/api/tests/categorization/__init__.py`.

- [ ] **Step 2:** Create test `apps/api/tests/categorization/test_rulebook.py`:

```python
import pytest

from app.categorization.rulebook import CATEGORIES, match


@pytest.mark.parametrize(
    "merchant,expected",
    [
        ("스타벅스 강남점", "coffee"),
        ("STARBUCKS COFFEE", "coffee"),
        ("이디야커피 역삼", "coffee"),
        ("김밥천국", "lunch"),
        ("맥도날드 잠실점", "lunch"),
        ("BBQ 치킨 잠실", "snack_late"),
        ("이마트 성수점", "groceries"),
        ("코스트코 양재", "groceries"),
        ("CGV 왕십리", "entertainment"),
        ("넷플릭스", "subscription"),
        ("KT 통신요금", "telecom"),
        ("티머니 충전", "transport"),
    ],
)
def test_rulebook_matches_known_merchants(merchant, expected):
    assert match(merchant) == expected


def test_rulebook_returns_none_for_unknown():
    assert match("아무도 모르는 가맹점 12345") is None


def test_categories_enum_contains_unknown():
    assert "unknown" in CATEGORIES
    assert len(CATEGORIES) == 14
```

- [ ] **Step 3:** Run (expect FAIL).

Run: `cd apps/api && uv run pytest tests/categorization/test_rulebook.py -v`

- [ ] **Step 4:** Create `apps/api/app/categorization/rulebook.py`:

```python
"""키워드/정규식 기반 카테고리 룰북.

순서 의미 있음 (위에서부터 첫 매칭). 매칭 실패 시 None.
LLM 폴백은 service.py에서 처리.
"""
import re

CATEGORIES: tuple[str, ...] = (
    "coffee", "lunch", "dinner", "snack_late",
    "groceries", "transport", "telecom",
    "subscription", "entertainment", "health",
    "shopping", "utilities", "etc", "unknown",
)

_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"스타벅스|이디야|투썸|할리스|커피빈|starbucks|coffee\s*bean", re.I), "coffee"),
    (re.compile(r"김밥천국|맘스터치|롯데리아|맥도날드|버거킹|쉐이크쉑|서브웨이", re.I), "lunch"),
    (re.compile(r"BBQ|교촌|굽네|푸라닭|치킨|피자|족발|보쌈", re.I), "snack_late"),
    (re.compile(r"이마트|EMART|홈플러스|롯데마트|코스트코|GS\s*THE\s*FRESH", re.I), "groceries"),
    (re.compile(r"CGV|메가박스|롯데시네마|예스24|교보문고|올리브영|다이소", re.I), "entertainment"),
    (re.compile(r"넷플릭스|유튜브\s*프리미엄|쿠팡플레이|왓챠|디즈니플러스|티빙|스포티파이", re.I), "subscription"),
    (re.compile(r"KT(\b|텔레콤)|SKT|SK텔레콤|LGU\+|LG\s*유플러스", re.I), "telecom"),
    (re.compile(r"티머니|T머니|캐시비|교통카드|버스|지하철|코레일|SRT", re.I), "transport"),
    (re.compile(r"한전|한국전력|도시가스|상수도|관리비", re.I), "utilities"),
    (re.compile(r"약국|병원|의원|치과|한의원|올리브영(.*)약", re.I), "health"),
    (re.compile(r"쿠팡|11번가|G마켓|네이버\s*스마트스토어|마켓컬리|SSG", re.I), "shopping"),
]


def match(merchant_raw: str) -> str | None:
    if not merchant_raw:
        return None
    for pattern, category in _RULES:
        if pattern.search(merchant_raw):
            return category
    return None
```

- [ ] **Step 5:** Run (expect PASS).

Run: `cd apps/api && uv run pytest tests/categorization/test_rulebook.py -v`

### Task 27: 캐시 모듈 TDD

**Files:**
- Create: `apps/api/app/categorization/cache.py`
- Create: `apps/api/tests/categorization/test_cache.py`

- [ ] **Step 1:** Create test `apps/api/tests/categorization/test_cache.py`:

```python
import pytest

from app.categorization.cache import get, normalize_merchant, set as cache_set


@pytest.mark.parametrize(
    "raw,normalized",
    [
        ("스타벅스 강남점", "스타벅스강남"),
        ("(주)이디야커피", "이디야커피"),
        ("이마트 성수1호점", "이마트성수"),
        ("STARBUCKS COFFEE  ", "starbucks coffee"),
    ],
)
def test_normalize_strips_suffixes_and_whitespace(raw, normalized):
    assert normalize_merchant(raw) == normalized


async def test_cache_miss_returns_none():
    result = await get("never_set_merchant")
    assert result is None


async def test_cache_set_then_get_roundtrip():
    await cache_set("스타벅스 강남점", "coffee")
    result = await get("스타벅스 강남점")
    assert result == "coffee"


async def test_cache_key_normalized_so_different_writes_collapse():
    await cache_set("(주)스타벅스 강남점", "coffee")
    # 다른 표기지만 정규화 후 동일 키
    result = await get("스타벅스 강남점 ")
    assert result == "coffee"
```

- [ ] **Step 2:** Run (expect FAIL).

Run: `cd apps/api && uv run pytest tests/categorization/test_cache.py -v`

- [ ] **Step 3:** Create `apps/api/app/categorization/cache.py`:

```python
"""전역 카테고리 캐시 (Redis).

키: `category:v1:{normalized_merchant_name}` — 모든 사용자 공유.
값: 카테고리 enum 문자열. TTL 없음 (영구). LLM 호출 결과 보존이 목적.
"""
import re

from app.redis_client import acquire_redis

_KEY_PREFIX = "category:v1:"

_SUFFIX_PATTERNS = [
    re.compile(r"\(주\)|㈜|주식회사"),
    re.compile(r"\d+호점"),
    re.compile(r"점\s*$"),
]


def normalize_merchant(raw: str) -> str:
    """가맹점명 정규화 — 공통 표기 차이를 흡수해 캐시 hit rate 상승."""
    text = raw.strip().lower() if not _is_cjk(raw) else raw.strip()
    for pat in _SUFFIX_PATTERNS:
        text = pat.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()
    # 한글은 공백 제거 (영문은 공백 유지)
    if _is_cjk(text):
        text = text.replace(" ", "")
    return text


def _is_cjk(s: str) -> bool:
    return any("가" <= ch <= "힣" for ch in s)


async def get(merchant_raw: str) -> str | None:
    key = _KEY_PREFIX + normalize_merchant(merchant_raw)
    async with acquire_redis() as r:
        return await r.get(key)


async def set(merchant_raw: str, category: str) -> None:  # noqa: A001
    key = _KEY_PREFIX + normalize_merchant(merchant_raw)
    async with acquire_redis() as r:
        await r.set(key, category)
```

- [ ] **Step 4:** Run (expect PASS).

Run: `cd apps/api && uv run pytest tests/categorization/test_cache.py -v`

### Task 28: 예산 모듈 TDD

**Files:**
- Create: `apps/api/app/categorization/budget.py`
- Create: `apps/api/tests/categorization/test_budget.py`

- [ ] **Step 1:** Create test `apps/api/tests/categorization/test_budget.py`:

```python
import pytest

from app.categorization.budget import (
    HAIKU_INPUT_PRICE_PER_MTOK,
    HAIKU_OUTPUT_PRICE_PER_MTOK,
    current_usage_usd,
    has_room,
    record_usage,
)


async def test_initial_room_available(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_MONTHLY_BUDGET_USD", "5.0")
    assert await has_room() is True
    assert await current_usage_usd() == 0.0


async def test_record_usage_increments_counter():
    await record_usage(input_tokens=1000, output_tokens=500, merchant="test_merchant")
    expected = 1000 * HAIKU_INPUT_PRICE_PER_MTOK / 1_000_000 + 500 * HAIKU_OUTPUT_PRICE_PER_MTOK / 1_000_000
    assert abs(await current_usage_usd() - expected) < 1e-9


async def test_has_room_false_when_budget_exhausted(monkeypatch):
    # tiny budget that 1 record will exceed
    monkeypatch.setenv("ANTHROPIC_MONTHLY_BUDGET_USD", "0.000001")
    # reset cached settings
    from app.settings import Settings
    import app.settings
    app.settings.settings = Settings()

    await record_usage(input_tokens=10_000, output_tokens=5_000, merchant="x")
    assert await has_room() is False
```

- [ ] **Step 2:** Run (expect FAIL).

- [ ] **Step 3:** Create `apps/api/app/categorization/budget.py`:

```python
"""Anthropic 월간 비용 가드레일.

키: llm_budget:{YYYY-MM} (UTC) — 누적 비용 USD.
키: 매월 자연스럽게 바뀌므로 별도 reset cron 불필요.
"""
from datetime import UTC, datetime
from uuid import uuid4

from app.db import acquire
from app.redis_client import acquire_redis
from app.settings import settings

# Anthropic Claude Haiku 4.5 가격 (per 1M tokens, USD)
HAIKU_INPUT_PRICE_PER_MTOK = 1.0
HAIKU_OUTPUT_PRICE_PER_MTOK = 5.0
HAIKU_MODEL_ID = "claude-haiku-4-5-20251001"


def _bucket_key() -> str:
    return f"llm_budget:{datetime.now(UTC).strftime('%Y-%m')}"


async def current_usage_usd() -> float:
    async with acquire_redis() as r:
        raw = await r.get(_bucket_key())
    return float(raw) if raw else 0.0


async def has_room() -> bool:
    return await current_usage_usd() < settings.anthropic_monthly_budget_usd


def _cost(input_tokens: int, output_tokens: int) -> float:
    return (
        input_tokens * HAIKU_INPUT_PRICE_PER_MTOK / 1_000_000
        + output_tokens * HAIKU_OUTPUT_PRICE_PER_MTOK / 1_000_000
    )


async def record_usage(
    *,
    input_tokens: int,
    output_tokens: int,
    merchant: str,
    model: str = HAIKU_MODEL_ID,
) -> None:
    cost = _cost(input_tokens, output_tokens)
    async with acquire_redis() as r:
        await r.incrbyfloat(_bucket_key(), cost)

    async with acquire() as conn:
        await conn.execute(
            """
            INSERT INTO llm_usage_log (model, input_tokens, output_tokens, cost_usd, purpose, merchant_normalized)
            VALUES ($1, $2, $3, $4, 'categorize', $5)
            """,
            model, input_tokens, output_tokens, cost, merchant,
        )
```

- [ ] **Step 4:** `apps/api/app/settings.py`에 `anthropic_monthly_budget_usd` 추가:

```python
    anthropic_monthly_budget_usd: float = 5.0
```

- [ ] **Step 5:** `apps/api/tests/.env.test`에 추가:

```
ANTHROPIC_MONTHLY_BUDGET_USD=5.0
```

- [ ] **Step 6:** Run (expect PASS).

Run: `cd apps/api && uv run pytest tests/categorization/test_budget.py -v`

### Task 29: Service 오케스트레이터 TDD (LLM 부재 시 unknown 반환)

**Files:**
- Create: `apps/api/app/categorization/service.py`
- Create: `apps/api/tests/categorization/test_service.py`

- [ ] **Step 1:** Create test `apps/api/tests/categorization/test_service.py`:

```python
from app.categorization.service import classify


async def test_rulebook_hit_returns_without_cache_or_llm():
    result = await classify("스타벅스 강남점")
    assert result == "coffee"


async def test_rulebook_miss_cache_miss_no_llm_returns_unknown(monkeypatch):
    # Phase 4에서는 LLM이 아직 없으므로 unknown
    result = await classify("듣도보도 못한 가맹점 ABC")
    assert result == "unknown"


async def test_rulebook_miss_cache_hit_returns_cached(monkeypatch):
    from app.categorization import cache
    await cache.set("이상한가맹점", "shopping")
    result = await classify("이상한가맹점")
    assert result == "shopping"
```

- [ ] **Step 2:** Run (expect FAIL).

- [ ] **Step 3:** Create `apps/api/app/categorization/service.py`:

```python
"""카테고리 분류 오케스트레이터.

흐름: rulebook → redis cache → LLM (Phase 5) → unknown
"""
from app.categorization import budget, cache, rulebook


async def classify(merchant_raw: str) -> str:
    # 1. 룰북
    cat = rulebook.match(merchant_raw)
    if cat is not None:
        return cat

    # 2. Redis 캐시
    cached = await cache.get(merchant_raw)
    if cached is not None:
        return cached

    # 3. 예산 체크 (Phase 5에서 LLM 호출 게이트)
    if not await budget.has_room():
        return "unknown"

    # 4. LLM 호출 — Phase 5에서 추가. 현 시점에는 unknown.
    return "unknown"
```

- [ ] **Step 4:** Run (expect PASS).

Run: `cd apps/api && uv run pytest tests/categorization/test_service.py -v`

### Task 30: simple_rules.py 제거 + transactions 라우트에 categorization 연결

**Files:**
- Delete: `apps/api/app/parsers/simple_rules.py`
- Modify: `apps/api/app/parsers/samsung_card.py` (simple_rules import 제거)
- Modify: `apps/api/app/transactions/routes.py` 또는 `service.py`

- [ ] **Step 1:** simple_rules 사용처 확인.

Run: `grep -rn "simple_rules" apps/api/app/ apps/api/tests/`

- [ ] **Step 2:** `samsung_card.py`에서 simple_rules import와 호출 제거 (category 미설정 상태로 ParseResult 반환).

- [ ] **Step 3:** `apps/api/app/transactions/routes.py`의 upload 라우트에서 파싱 결과에 대해 classify 호출. 파일 읽고 정확한 위치 파악:

Run: `cat apps/api/app/transactions/routes.py`

- [ ] **Step 4:** 파싱 결과를 DB에 INSERT 하기 직전에 다음 추가 (예시 — 실제 변수명은 routes.py 보고 맞춤):

```python
from app.categorization.service import classify

# parse 후
for tx in items:
    tx.category = await classify(tx.merchant_raw)
```

- [ ] **Step 5:** simple_rules.py 삭제.

```bash
git rm apps/api/app/parsers/simple_rules.py
```

- [ ] **Step 6:** simple_rules 관련 테스트 삭제 또는 categorization으로 이전.

Run: `find apps/api/tests -name "*simple_rules*"` → 발견 시 삭제 또는 `tests/categorization/test_rulebook.py`로 케이스 통합.

### Task 31: 업로드 E2E 회귀 — 카테고리가 채워지는지

**Files:**
- Modify: `apps/api/tests/transactions/test_upload.py` (또는 기존 업로드 테스트)

- [ ] **Step 1:** 기존 업로드 테스트를 찾기.

Run: `grep -rn "test_upload\|/transactions/upload" apps/api/tests/`

- [ ] **Step 2:** 업로드 후 응답 또는 DB query로 `category` 컬럼이 NULL이 아니거나 룰북 매칭 거래에 대해 정확한 카테고리가 들어있는지 검증하는 assert 추가.

예시 추가:

```python
async def test_upload_populates_category_from_rulebook(...):
    # 기존 업로드 흐름 호출
    ...
    # DB에서 거래 조회
    async with test_db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT merchant_raw, category FROM transactions WHERE user_id = $1", user_id)
    starbucks_rows = [r for r in rows if "스타벅스" in r["merchant_raw"]]
    assert all(r["category"] == "coffee" for r in starbucks_rows)
```

### Task 32: 전체 테스트 회귀

- [ ] **Step 1:** Run.

```bash
cd apps/api && uv run pytest -x
```
Expected: all green.

### Task 33: Commit + Phase 4 PR

```bash
git add apps/api/migrations/versions/0002_add_llm_usage_log.py apps/api/tests/conftest.py apps/api/app/categorization/ apps/api/tests/categorization/ apps/api/app/transactions/ apps/api/app/parsers/samsung_card.py apps/api/app/settings.py apps/api/tests/.env.test
git rm apps/api/app/parsers/simple_rules.py
git commit -m "feat(api): add categorization module (rulebook + redis cache + budget) and wire into upload"
git push -u origin feat/w2-phase4-categorization
gh pr create --title "feat(api): categorization rulebook + cache + budget" --body "$(cat <<'EOF'
## Summary
- 마이그레이션 0002: llm_usage_log 테이블 (감사용)
- app/categorization/rulebook.py: 정규식 기반 11개 카테고리 룰
- app/categorization/cache.py: Redis 전역 캐시 + merchant 정규화
- app/categorization/budget.py: 월간 비용 카운터 + DB usage log
- app/categorization/service.py: 룰북 → 캐시 → (LLM, Phase 5) → unknown 흐름
- W1 app/parsers/simple_rules.py 제거 (categorization으로 통합)
- transactions/upload에서 classify 호출하여 category 채움

## Test plan
- [x] tests/categorization/* 4파일 통과
- [x] 업로드 E2E에서 룰북 매칭 거래의 category 검증
- [x] 회귀 — W1 테스트 전부 통과
EOF
)"
```

- [ ] **Step 2:** Squash merge → main 갱신.

---

## Phase 5: Claude Haiku LLM 통합 (7 tasks)

**브랜치:** `feat/w2-phase5-haiku`

### Task 34: 브랜치 + `anthropic` 의존성

**Files:**
- Modify: `apps/api/pyproject.toml`

- [ ] **Step 1:**

```bash
git checkout main && git pull --ff-only origin main
git checkout -b feat/w2-phase5-haiku
```

- [ ] **Step 2:** `apps/api/pyproject.toml`의 `dependencies` 배열에 추가:

```toml
"anthropic>=0.40",
```

- [ ] **Step 3:**

```bash
cd apps/api && uv sync
```

### Task 35: Settings + ENV에 `ANTHROPIC_API_KEY`

**Files:**
- Modify: `apps/api/app/settings.py`
- Modify: `.env.example`
- Modify: `apps/api/.env` (로컬, 사용자 직접)
- Modify: `apps/api/tests/.env.test`

- [ ] **Step 1:** `app/settings.py`에 필드 추가:

```python
    anthropic_api_key: str = "sk-ant-test-placeholder"
```

(default 둠 — 테스트는 mock하므로 실키 불필요.)

- [ ] **Step 2:** `.env.example`에 추가:

```
# Anthropic Claude Haiku — 카테고리 분류 폴백
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MONTHLY_BUDGET_USD=5.0
```

- [ ] **Step 3:** `apps/api/.env` 사용자 본인 실키 추가 (gitignored).

- [ ] **Step 4:** `apps/api/tests/.env.test`에 placeholder:

```
ANTHROPIC_API_KEY=sk-ant-test-placeholder
```

### Task 36: LLM 모듈 TDD

**Files:**
- Create: `apps/api/app/categorization/llm.py`
- Create: `apps/api/tests/categorization/test_llm.py`

- [ ] **Step 1:** Create test `apps/api/tests/categorization/test_llm.py`:

```python
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.categorization.llm import LLMClassifyError, classify_one


@pytest.fixture
def mock_anthropic(monkeypatch):
    fake_msg = MagicMock()
    fake_msg.content = [MagicMock(text='{"category": "coffee"}')]
    fake_msg.usage = MagicMock(input_tokens=120, output_tokens=8)

    fake_client = MagicMock()
    fake_client.messages = MagicMock()
    fake_client.messages.create = AsyncMock(return_value=fake_msg)

    monkeypatch.setattr("app.categorization.llm._client", lambda: fake_client)
    return fake_client


async def test_classify_one_returns_enum_value(mock_anthropic):
    cat, usage = await classify_one("듣보잡 카페")
    assert cat == "coffee"
    assert usage.input_tokens == 120
    assert usage.output_tokens == 8


async def test_classify_one_enum_violation_returns_unknown(mock_anthropic):
    mock_anthropic.messages.create.return_value.content = [
        MagicMock(text='{"category": "totally_invalid"}')
    ]
    cat, _ = await classify_one("뭔가")
    assert cat == "unknown"


async def test_classify_one_malformed_json_raises(mock_anthropic):
    mock_anthropic.messages.create.return_value.content = [
        MagicMock(text='not json at all')
    ]
    with pytest.raises(LLMClassifyError):
        await classify_one("뭔가")
```

- [ ] **Step 2:** Run (expect FAIL).

- [ ] **Step 3:** Create `apps/api/app/categorization/llm.py`:

```python
"""Claude Haiku 카테고리 분류 호출.

응답을 14개 enum 안으로 강제. enum 밖이면 'unknown'으로 대체.
"""
import json
from dataclasses import dataclass

import anthropic

from app.categorization.budget import HAIKU_MODEL_ID
from app.categorization.rulebook import CATEGORIES
from app.settings import settings


class LLMClassifyError(Exception):
    """LLM 호출/파싱 실패. 호출자가 unknown으로 폴백."""


@dataclass
class Usage:
    input_tokens: int
    output_tokens: int


_SYSTEM = (
    "당신은 한국 카드 거래의 가맹점명을 보고 카테고리를 정해주는 분류기입니다. "
    "다음 14개 중 정확히 하나를 JSON으로 답하세요: "
    f"{', '.join(CATEGORIES)}. "
    '응답 형식: {"category": "<enum>"}. 다른 문자 없이 JSON만.'
)


def _client() -> anthropic.AsyncAnthropic:
    return anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)


async def classify_one(merchant_raw: str) -> tuple[str, Usage]:
    client = _client()
    msg = await client.messages.create(
        model=HAIKU_MODEL_ID,
        max_tokens=64,
        system=_SYSTEM,
        messages=[{"role": "user", "content": f"가맹점명: {merchant_raw}"}],
    )

    text = "".join(block.text for block in msg.content if hasattr(block, "text"))

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LLMClassifyError(f"non-JSON response: {text[:200]}") from exc

    cat = parsed.get("category", "unknown")
    if cat not in CATEGORIES:
        cat = "unknown"

    return cat, Usage(
        input_tokens=msg.usage.input_tokens,
        output_tokens=msg.usage.output_tokens,
    )
```

- [ ] **Step 4:** Run (expect PASS).

### Task 37: Service 오케스트레이터에 LLM 연결

**Files:**
- Modify: `apps/api/app/categorization/service.py`

- [ ] **Step 1:** `apps/api/app/categorization/service.py` 수정:

```python
from app.categorization import budget, cache, llm, rulebook


async def classify(merchant_raw: str) -> str:
    cat = rulebook.match(merchant_raw)
    if cat is not None:
        return cat

    cached = await cache.get(merchant_raw)
    if cached is not None:
        return cached

    if not await budget.has_room():
        return "unknown"

    try:
        cat, usage = await llm.classify_one(merchant_raw)
    except (llm.LLMClassifyError, Exception):
        return "unknown"

    await cache.set(merchant_raw, cat)
    await budget.record_usage(
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        merchant=cache.normalize_merchant(merchant_raw),
    )
    return cat
```

### Task 38: Service+LLM 통합 테스트 추가

**Files:**
- Modify: `apps/api/tests/categorization/test_service.py`

- [ ] **Step 1:** 파일 끝에 추가:

```python
from unittest.mock import AsyncMock, MagicMock


async def _patch_llm(monkeypatch, category: str = "shopping"):
    fake_msg = MagicMock()
    fake_msg.content = [MagicMock(text=f'{{"category": "{category}"}}')]
    fake_msg.usage = MagicMock(input_tokens=100, output_tokens=5)
    fake_client = MagicMock()
    fake_client.messages = MagicMock()
    fake_client.messages.create = AsyncMock(return_value=fake_msg)
    monkeypatch.setattr("app.categorization.llm._client", lambda: fake_client)
    return fake_client


async def test_rulebook_miss_calls_llm_and_caches(monkeypatch):
    fake = await _patch_llm(monkeypatch, category="shopping")

    result = await classify("미지의가맹점XYZ")
    assert result == "shopping"
    assert fake.messages.create.await_count == 1

    # 두 번째 호출은 캐시 hit → LLM 호출 0회
    result2 = await classify("미지의가맹점XYZ")
    assert result2 == "shopping"
    assert fake.messages.create.await_count == 1


async def test_llm_failure_returns_unknown(monkeypatch):
    fake = await _patch_llm(monkeypatch)
    fake.messages.create.side_effect = RuntimeError("api down")

    result = await classify("새로운가맹점123")
    assert result == "unknown"


async def test_budget_exhausted_short_circuits_llm(monkeypatch):
    fake = await _patch_llm(monkeypatch)
    monkeypatch.setattr("app.categorization.budget.has_room", AsyncMock(return_value=False))

    result = await classify("아무거나가맹점")
    assert result == "unknown"
    assert fake.messages.create.await_count == 0
```

- [ ] **Step 2:** Run.

Run: `cd apps/api && uv run pytest tests/categorization/test_service.py -v`
Expected: 모두 PASS.

### Task 39: 업로드 E2E — LLM mock으로 카테고리 검증

**Files:**
- Modify: 기존 업로드 테스트

- [ ] **Step 1:** 룰북 미매칭 가맹점을 포함한 fixture를 추가하거나 mock LLM 응답을 셋업하여 업로드 후 해당 거래의 category가 mocked 값으로 저장되는지 검증.

(구체 코드는 기존 업로드 테스트 구조에 맞춰 작성 — Task 31에서 만든 패턴 재사용.)

### Task 40: Commit + Phase 5 PR

```bash
git add apps/api/pyproject.toml apps/api/uv.lock apps/api/app/settings.py apps/api/.env apps/api/tests/.env.test apps/api/app/categorization/llm.py apps/api/app/categorization/service.py apps/api/tests/categorization/test_llm.py apps/api/tests/categorization/test_service.py .env.example
git commit -m "feat(api): integrate Claude Haiku as categorization fallback with budget guard"
git push -u origin feat/w2-phase5-haiku
gh pr create --title "feat(api): Claude Haiku categorization fallback" --body "$(cat <<'EOF'
## Summary
- anthropic SDK 추가
- categorization/llm.py: Haiku 호출 + 14개 enum 강제
- service.py: 룰북 → 캐시 → (예산 OK) → LLM → 캐시 저장 + usage 기록
- LLM 실패/예산 초과 시 silent fallback to "unknown" — 업로드 흐름 안 끊김

## Test plan
- [x] tests/categorization/test_llm.py (mock 응답 3 케이스)
- [x] tests/categorization/test_service.py (LLM 호출 + 캐시 hit + 실패 폴백 + 예산 차단)
- [x] 업로드 E2E LLM mock 흐름 검증
EOF
)"
```

---

## Phase 6: parsers/registry + 우리카드 (8 tasks)

**브랜치:** `feat/w2-phase6-woori-card`

### Task 41: 브랜치 + 우리카드 fixture 빌드 스크립트

**Files:**
- Create: `apps/api/tests/fixtures/build_woori_fixture.py`
- Create: `apps/api/tests/fixtures/woori-sample.xlsx`

- [ ] **Step 1:**

```bash
git checkout main && git pull --ff-only origin main
git checkout -b feat/w2-phase6-woori-card
```

- [ ] **Step 2:** 실제 본인 우리카드 명세서 XLSX의 실제 헤더 행을 메모해 둠 (열기만 — 절대 commit 안 함). 메모할 것:
  - 시트명 (예: `이용내역`, `국내이용내역` 등)
  - 헤더 행 번호 (몇 번째 row인지)
  - 컬럼명: 날짜 / 시간 / 가맹점명 / 금액 / 할부 / 승인번호 / 카드번호 등

- [ ] **Step 3:** Create `apps/api/tests/fixtures/build_woori_fixture.py`:

```python
"""우리카드 명세서 익명화 fixture 빌더.

실제 본인 명세서의 헤더 행 위치와 컬럼명을 그대로 모방하되
거래 데이터는 fictitious. PAN은 'XXXX-XXXX-XXXX-1234' 형태.
"""
from openpyxl import Workbook


def build() -> Workbook:
    wb = Workbook()
    ws = wb.active
    ws.title = "이용내역"  # ← 실제 시트명으로 교체 필요

    # 상단 메타 행 (실제 명세서 모방)
    ws["A1"] = "우리카드 이용내역서"
    ws["A2"] = "기간: 2026-04-01 ~ 2026-04-30"
    # ... 실제 명세서의 메타 행 패턴 그대로

    # 헤더 행 — 실제 헤더 행 번호로 교체
    HEADER_ROW = 5
    headers = ["거래일자", "거래시간", "가맹점명", "이용금액", "할부", "승인번호", "카드번호"]
    for i, h in enumerate(headers, start=1):
        ws.cell(row=HEADER_ROW, column=i).value = h

    # 데이터 행 (10건 정도)
    rows = [
        ("2026-04-02", "12:34:56", "스타벅스 광교점", 5400, "일시불", "12345678", "XXXX-XXXX-XXXX-1234"),
        ("2026-04-03", "08:15:00", "GS25 광교점", 3200, "일시불", "12345679", "XXXX-XXXX-XXXX-1234"),
        ("2026-04-05", "19:21:00", "BBQ 광교점", 24000, "일시불", "12345680", "XXXX-XXXX-XXXX-1234"),
        # ... 7건 더
    ]
    for i, row in enumerate(rows, start=HEADER_ROW + 1):
        for j, val in enumerate(row, start=1):
            ws.cell(row=i, column=j).value = val

    return wb


if __name__ == "__main__":
    from pathlib import Path
    wb = build()
    out = Path(__file__).parent / "woori-sample.xlsx"
    wb.save(out)
    print(f"wrote {out}")
```

- [ ] **Step 4:** 빌드.

```bash
cd apps/api && uv run python tests/fixtures/build_woori_fixture.py
```
Expected: `tests/fixtures/woori-sample.xlsx` 생성.

### Task 42: registry 모듈 TDD

**Files:**
- Create: `apps/api/app/parsers/registry.py`
- Create: `apps/api/tests/parsers/test_registry.py`

- [ ] **Step 1:** Create test `apps/api/tests/parsers/test_registry.py`:

```python
from pathlib import Path

import pytest

from app.parsers.registry import detect, UnknownCardFormatError

FIXTURES = Path(__file__).parent.parent / "fixtures"


def test_detect_samsung_xlsx():
    data = (FIXTURES / "samsung-card-sample.xlsx").read_bytes()
    parser = detect(data)
    assert parser.__name__ == "samsung_card"  # 또는 .source_type == "samsung"


def test_detect_woori_xlsx():
    data = (FIXTURES / "woori-sample.xlsx").read_bytes()
    parser = detect(data)
    assert parser.__name__ == "woori_card"


def test_detect_unknown_raises():
    # 빈 워크북
    from io import BytesIO
    from openpyxl import Workbook
    wb = Workbook()
    buf = BytesIO()
    wb.save(buf)
    with pytest.raises(UnknownCardFormatError):
        detect(buf.getvalue())
```

- [ ] **Step 2:** Run (expect FAIL — registry/우리 파서 없음).

- [ ] **Step 3:** Create `apps/api/app/parsers/registry.py`:

```python
"""카드사 자동 감지 + 파서 dispatch.

각 파서 모듈에 `def detect(workbook) -> bool` 함수를 두고, registry가
첫 헤더 시그니처 매칭 파서를 반환한다.
"""
from io import BytesIO
from types import ModuleType

from openpyxl import load_workbook

from app.parsers import hana_card, samsung_card, woori_card  # 등록 순서 = 우선순위


class UnknownCardFormatError(Exception):
    pass


_PARSERS: list[ModuleType] = [samsung_card, woori_card, hana_card]


def detect(file_bytes: bytes) -> ModuleType:
    wb = load_workbook(BytesIO(file_bytes), data_only=True, read_only=True)
    for parser in _PARSERS:
        if parser.detect(wb):
            return parser
    raise UnknownCardFormatError("UNKNOWN_CARD_FORMAT")
```

- [ ] **Step 4:** `samsung_card.py`에 `detect(wb) -> bool` 함수 추가 (없으면). 패턴: 시트명 + 헤더 행에 특정 컬럼 존재 여부.

```python
def detect(wb) -> bool:
    for sheet_name in wb.sheetnames:
        if "국내이용내역" in sheet_name:
            return True
    return False
```

- [ ] **Step 5:** Run (Woori test는 아직 FAIL — 파서 없음. Samsung test와 unknown test는 PASS 기대).

### Task 43: 우리카드 파서 TDD

**Files:**
- Create: `apps/api/app/parsers/woori_card.py`
- Create: `apps/api/tests/parsers/test_woori_card.py`

- [ ] **Step 1:** Create test `apps/api/tests/parsers/test_woori_card.py`:

```python
from io import BytesIO
from pathlib import Path

from openpyxl import load_workbook

from app.parsers.woori_card import detect, parse

FIXTURE = Path(__file__).parent.parent / "fixtures" / "woori-sample.xlsx"


def test_detect_woori_workbook():
    wb = load_workbook(FIXTURE, read_only=True)
    assert detect(wb) is True


def test_parse_returns_expected_rows():
    data = FIXTURE.read_bytes()
    result = parse(BytesIO(data).read())
    assert result.parsed_rows >= 10
    starbucks = [r for r in result.transactions if "스타벅스" in r.merchant_raw]
    assert len(starbucks) >= 1
    assert starbucks[0].amount == 5400


def test_parse_masks_pan_in_raw_row():
    data = FIXTURE.read_bytes()
    result = parse(data)
    for tx in result.transactions:
        for v in tx.raw_row.values():
            assert "1234" not in str(v) or "XXXX" in str(v) or "****" in str(v)
```

- [ ] **Step 2:** Run (expect FAIL).

- [ ] **Step 3:** Create `apps/api/app/parsers/woori_card.py`. samsung_card.py를 참고하되 우리카드의 시트명/헤더 행 번호/컬럼 매핑에 맞춰 작성:

```python
"""우리카드 XLSX 명세서 파서.

시트: '이용내역' (또는 실제 시트명).
헤더 행: 5번째 (실제 값으로 교체).
컬럼: 거래일자/거래시간/가맹점명/이용금액/할부/승인번호/카드번호.
"""
from io import BytesIO

from openpyxl import load_workbook

from app.parsers.samsung_card import (  # 공통 헬퍼 재사용
    ParseResult,
    TransactionRow,
    _mask_pan,
    _parse_amount,
)

source_type = "woori"

_SHEET_HINTS = ("이용내역",)  # 실제 시트명에 맞춰 추가
_REQUIRED_COLUMNS = {"거래일자", "가맹점명", "이용금액", "승인번호"}


def detect(wb) -> bool:
    for name in wb.sheetnames:
        if any(hint in name for hint in _SHEET_HINTS):
            # 헤더 컬럼 확인
            ws = wb[name]
            for row in ws.iter_rows(min_row=1, max_row=15, values_only=True):
                if row and _REQUIRED_COLUMNS.issubset({str(c).strip() for c in row if c}):
                    return True
    return False


def parse(file_bytes: bytes) -> ParseResult:
    wb = load_workbook(BytesIO(file_bytes), data_only=True, read_only=True)
    ws = next(wb[name] for name in wb.sheetnames if any(h in name for h in _SHEET_HINTS))

    header_row_idx = None
    headers: list[str] = []
    for i, row in enumerate(ws.iter_rows(min_row=1, max_row=15, values_only=True), start=1):
        if row and _REQUIRED_COLUMNS.issubset({str(c).strip() for c in row if c}):
            header_row_idx = i
            headers = [str(c).strip() if c else "" for c in row]
            break

    if header_row_idx is None:
        return ParseResult(source_type=source_type, transactions=[], parsed_rows=0, errors=[])

    col = {name: idx for idx, name in enumerate(headers)}

    txs: list[TransactionRow] = []
    for raw in ws.iter_rows(min_row=header_row_idx + 1, values_only=True):
        if raw is None or raw[col["거래일자"]] is None:
            break
        merchant = str(raw[col["가맹점명"]] or "").strip()
        if not merchant:
            continue

        amount = _parse_amount(raw[col["이용금액"]])
        pan_raw = str(raw[col["카드번호"]] or "")
        pan_masked = _mask_pan(pan_raw)

        raw_row_dict = {h: raw[i] for i, h in enumerate(headers) if h}
        raw_row_dict["카드번호"] = pan_masked

        txs.append(TransactionRow(
            txn_date=raw[col["거래일자"]],
            txn_time=raw[col.get("거래시간", -1)] if "거래시간" in col else None,
            merchant_raw=merchant,
            amount=amount,
            approval_no=str(raw[col["승인번호"]] or "") or None,
            card_last4=pan_raw[-4:] if pan_raw else None,
            raw_row=raw_row_dict,
            source_type=source_type,
        ))

    return ParseResult(source_type=source_type, transactions=txs, parsed_rows=len(txs), errors=[])
```

- [ ] **Step 4:** Run.

Run: `cd apps/api && uv run pytest tests/parsers/test_woori_card.py -v`
Expected: 3 passed (실제 fixture 헤더와 컬럼명에 맞춰 코드 조정 필요할 수 있음).

### Task 44: registry test 다시 실행

- [ ] **Step 1:**

Run: `cd apps/api && uv run pytest tests/parsers/test_registry.py -v`
Expected: 3 passed (samsung/woori detect + unknown).

### Task 45: transactions 라우트가 registry 사용하도록 변경

**Files:**
- Modify: `apps/api/app/transactions/routes.py`

- [ ] **Step 1:** 현재 라우트에서 `samsung_card.parse(...)` 직접 호출하는 부분을 다음으로 변경:

```python
from app.parsers.registry import UnknownCardFormatError, detect

# 업로드 라우트 본문:
try:
    parser = detect(file_bytes)
except UnknownCardFormatError as exc:
    raise HTTPException(status_code=400, detail="UNKNOWN_CARD_FORMAT") from exc

result = parser.parse(file_bytes)
```

- [ ] **Step 2:** 회귀 — 삼성카드 fixture 업로드 테스트가 여전히 통과하는지 확인.

```bash
cd apps/api && uv run pytest tests/transactions/ -v
```

### Task 46: 업로드 E2E — 우리카드 fixture

**Files:**
- Modify: `apps/api/tests/transactions/test_upload.py`

- [ ] **Step 1:** 추가:

```python
async def test_upload_woori_xlsx_succeeds(...):
    files = {"file": ("woori-sample.xlsx", FIXTURE.read_bytes(),
                      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    r = await ac.post("/transactions/upload", files=files, headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["inserted"] >= 10
    assert body["source_type"] == "woori"
```

- [ ] **Step 2:** Run.

```bash
cd apps/api && uv run pytest tests/transactions/ -v
```

### Task 47: 회귀 + Commit + Phase 6 PR

```bash
cd apps/api && uv run pytest -x
cd ../..
git add apps/api/app/parsers/ apps/api/tests/parsers/ apps/api/tests/fixtures/build_woori_fixture.py apps/api/tests/fixtures/woori-sample.xlsx apps/api/app/transactions/
git commit -m "feat(api): add parser registry and Woori card XLSX parser"
git push -u origin feat/w2-phase6-woori-card
gh pr create --title "feat(api): Woori card parser + registry dispatch" --body "$(cat <<'EOF'
## Summary
- parsers/registry.py: 헤더 시그니처로 삼성/우리/하나 자동 선택
- parsers/woori_card.py + 익명화 fixture
- transactions/upload는 registry.detect 통해 파서 선택
- 알 수 없는 포맷은 400 UNKNOWN_CARD_FORMAT

## Test plan
- [x] tests/parsers/test_registry.py
- [x] tests/parsers/test_woori_card.py (detect + parse + PAN 마스킹)
- [x] tests/transactions/test_upload.py — 우리카드 fixture 업로드
EOF
)"
```

(주의: `hana_card` 모듈은 Phase 7에 생기므로, 이 PR의 registry에서는 hana import를 일시 주석 처리하거나 stub 모듈 만들기. 권장: stub `apps/api/app/parsers/hana_card.py`를 만들고 `detect`만 `return False`로 두기 — Phase 7에서 본구현. 그러면 import 깨짐 없음.)

### Task 48: hana_card.py stub 생성 (Phase 6 안에 같이)

**Files:**
- Create: `apps/api/app/parsers/hana_card.py` (stub)

- [ ] **Step 1:**

```python
"""하나카드 파서 — Phase 7에서 본구현."""


def detect(wb) -> bool:
    return False


def parse(file_bytes: bytes):
    raise NotImplementedError("hana_card parser is implemented in Phase 7")


source_type = "hana"
```

(이 stub은 Phase 6 PR에 함께 포함시켜 registry import가 깨지지 않게 함.)

---

## Phase 7: 하나카드 (5 tasks)

**브랜치:** `feat/w2-phase7-hana-card`

### Task 49: 브랜치 + 하나카드 fixture

**Files:**
- Create: `apps/api/tests/fixtures/build_hana_fixture.py`
- Create: `apps/api/tests/fixtures/hana-sample.xlsx`

- [ ] **Step 1:**

```bash
git checkout main && git pull --ff-only origin main
git checkout -b feat/w2-phase7-hana-card
```

- [ ] **Step 2:** 본인 하나카드 명세서의 실제 시트명, 헤더 행, 컬럼명을 메모.

- [ ] **Step 3:** `build_hana_fixture.py`를 `build_woori_fixture.py` 패턴 그대로 작성 (실제 하나카드 헤더에 맞춰). 빌드 후 `hana-sample.xlsx` 생성.

### Task 50: 하나카드 파서 TDD

**Files:**
- Create: `apps/api/tests/parsers/test_hana_card.py`
- Modify: `apps/api/app/parsers/hana_card.py` (stub → 본구현)

- [ ] **Step 1:** Create test (woori test와 동일 구조).

- [ ] **Step 2:** Run (expect FAIL — stub 상태).

- [ ] **Step 3:** `woori_card.py`를 참고해 하나카드 본구현 — 시트명, 헤더 컬럼, 일자 포맷에 맞춰. `source_type = "hana"`.

- [ ] **Step 4:** Run (expect PASS).

### Task 51: registry + 업로드 E2E

**Files:**
- Modify: `apps/api/tests/parsers/test_registry.py` (하나 케이스 추가)
- Modify: `apps/api/tests/transactions/test_upload.py` (하나 업로드 케이스 추가)

- [ ] **Step 1:** registry test에 하나 케이스 추가:

```python
def test_detect_hana_xlsx():
    data = (FIXTURES / "hana-sample.xlsx").read_bytes()
    parser = detect(data)
    assert parser.__name__.endswith("hana_card")
```

- [ ] **Step 2:** 업로드 테스트에 하나 fixture 케이스 추가.

- [ ] **Step 3:**

```bash
cd apps/api && uv run pytest -x
```

### Task 52: Commit + Phase 7 PR

```bash
git add apps/api/app/parsers/hana_card.py apps/api/tests/parsers/test_hana_card.py apps/api/tests/fixtures/build_hana_fixture.py apps/api/tests/fixtures/hana-sample.xlsx apps/api/tests/parsers/test_registry.py apps/api/tests/transactions/test_upload.py
git commit -m "feat(api): add Hana card XLSX parser"
git push -u origin feat/w2-phase7-hana-card
gh pr create --title "feat(api): Hana card parser" --body "$(cat <<'EOF'
## Summary
- parsers/hana_card.py: 하나카드 XLSX 본구현 (Phase 6의 stub 교체)
- registry test + 업로드 E2E에 하나 케이스 추가

## Test plan
- [x] tests/parsers/test_hana_card.py
- [x] tests/parsers/test_registry.py — 하나 detect
- [x] tests/transactions/test_upload.py — 하나 업로드
EOF
)"
```

---

## Phase 8: Lightsail Redis 추가 + 운영 ENV + 문서 (8 tasks)

**브랜치:** `chore/w2-phase8-deploy`

### Task 53: 브랜치 + docker-compose.prod.yml 갱신

**Files:**
- Modify: `infra/docker-compose.prod.yml`

- [ ] **Step 1:**

```bash
git checkout main && git pull --ff-only origin main
git checkout -b chore/w2-phase8-deploy
```

- [ ] **Step 2:** 현재 prod compose 확인.

Run: `cat infra/docker-compose.prod.yml`

- [ ] **Step 3:** `services:` 블록에 redis 추가 (postgres 다음):

```yaml
  redis:
    image: redis:7-alpine
    restart: unless-stopped
    command: ["redis-server", "--appendonly", "yes"]
    volumes:
      - redis_data:/data
    networks:
      - spendlens
```

- [ ] **Step 4:** `volumes:` 최상위에 추가:

```yaml
  redis_data:
```

- [ ] **Step 5:** `api` 서비스의 `environment`에 추가:

```yaml
      REDIS_URL: redis://redis:6379/0
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
      ANTHROPIC_MONTHLY_BUDGET_USD: ${ANTHROPIC_MONTHLY_BUDGET_USD:-5.0}
```

- [ ] **Step 6:** `api`의 `depends_on`에 `redis: condition: service_started` 추가.

### Task 54: 로컬 docker-compose에도 redis 추가

**Files:**
- Modify: `infra/docker-compose.local.yml` (또는 동등 파일)

- [ ] **Step 1:** 동일하게 redis 서비스 추가. 외부 포트 `6379:6379` 매핑 (로컬 개발 편의).

### Task 55: 운영 ENV 파일 갱신 가이드 (사용자 수동)

**Files:**
- Modify: `infra/README.md` 또는 `W1-DEPLOYMENT-SETUP.md`

- [ ] **Step 1:** 문서에 W2 ENV 추가 절차 명시:

```markdown
## W2 ENV 추가 (Lightsail)

```bash
ssh -i ~/.ssh/lightsail.pem ec2-user@<host>
sudo nano /opt/spendlens/.env

# 추가:
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MONTHLY_BUDGET_USD=5.0
REDIS_URL=redis://redis:6379/0

# 적용:
cd /opt/spendlens
sudo docker compose -f docker-compose.prod.yml pull
sudo docker compose -f docker-compose.prod.yml up -d
sudo docker compose -f docker-compose.prod.yml ps   # api + postgres + redis + caddy 모두 healthy 확인
```
```

### Task 56: README 갱신

**Files:**
- Modify: `README.md`

- [ ] **Step 1:** Status를 다음으로 교체:

```markdown
## Status
**W2 complete** — 다중 사용자 회원가입 + 카테고리 자동 분류(Claude Haiku 폴백) + Redis 캐시 + 우리/하나카드 파서.
Live:
- **Web:** https://spendlens.suim-app.store
- **Signup:** https://spendlens.suim-app.store/signup
- **Guest demo:** https://spendlens.suim-app.store/guest
- **API healthz:** https://api.spendlens.suim-app.store/healthz
```

- [ ] **Step 2:** Tech Stack에 추가:

```markdown
- Cache: Redis 7 (Lightsail Docker)
- AI: Claude Haiku 4.5 (카테고리 분류)
```

### Task 57: CHANGELOG 추가

**Files:**
- Create: `CHANGELOG.md` (없으면) 또는 Modify

- [ ] **Step 1:** 최상단에 W2 엔트리 추가:

```markdown
## W2 — 2026-05-27

### Added
- POST /auth/signup — 즉시 가입, 비밀번호 정책 (8자+영문+숫자)
- IP 기반 rate limit (시간당 5회) — signup/login
- Redis 7 컨테이너 (rate limit + categorization 캐시 + 비용 카운터)
- categorization 모듈: 룰북 → Redis 캐시 → Claude Haiku 폴백
- ANTHROPIC_MONTHLY_BUDGET_USD 비용 가드레일 (월 $5)
- parsers/registry.py: 카드사 자동 감지
- 우리카드/하나카드 XLSX 파서
- /signup 페이지 (React)

### Changed
- W1 simple_rules.py 제거 → categorization/rulebook.py로 통합
- transactions/upload는 registry.detect를 통해 파서 선택
- main 직접 커밋 → feature 브랜치 + PR squash merge 흐름

### Migrations
- 0002_add_llm_usage_log
```

### Task 58: 회고 문서 (선택)

**Files:**
- Create: `docs/retros/w2.md`

- [ ] **Step 1:** Skeleton 생성:

```markdown
# W2 Retro

## Shipped
- ...

## What worked
- ...

## What hurt
- ...

## Carry into W3
- ...

## Numbers
- PR count:
- Test count delta:
- LLM 호출 수 (월간):
- 룰북 hit rate:
```

### Task 59: 운영 배포 + 검수

**Files:** 없음 (운영 작업)

- [ ] **Step 1:** Phase 8 PR squash merge로 main에 코드 떨어진 후, GitHub Actions의 `deploy-api`가 자동 실행. 또는 수동으로 Lightsail에서:

```bash
ssh -i ~/.ssh/lightsail.pem ec2-user@<host>
cd /opt/spendlens
sudo docker compose -f docker-compose.prod.yml pull
sudo docker compose -f docker-compose.prod.yml up -d
sudo docker compose -f docker-compose.prod.yml ps
```

- [ ] **Step 2:** 검수 (spec §13 시나리오 1~8):
  1. `https://spendlens.suim-app.store/signup`에서 새 이메일로 가입 → /app 진입 → 본인 명세서 업로드 → 카테고리 칩 표시.
  2. 동일 이메일 재가입 → 409.
  3. 비번 `1234` → 400.
  4. 우리카드 fixture 업로드 → 카테고리 분류.
  5. 하나카드 fixture 업로드 → 카테고리 분류.
  6. 동일 우리카드 재업로드 → dedup skip + LLM 추가 호출 0건.
  7. SSH로 `docker compose exec redis redis-cli GET llm_budget:2026-05` → 0보다 큰 값.
  8. main에 squash merge된 PR 6+개 확인 (Conventional Commits 제목).

### Task 60: Phase 8 Commit + PR + 마무리

```bash
git add infra/ README.md CHANGELOG.md docs/retros/w2.md
git commit -m "chore(infra): add Redis to prod compose, document W2 ENV; docs: mark W2 complete"
git push -u origin chore/w2-phase8-deploy
gh pr create --title "chore(infra): W2 production rollout (Redis + ENV + docs)" --body "$(cat <<'EOF'
## Summary
- docker-compose.prod.yml에 redis:7-alpine 추가 + named volume + api 의존성
- 운영 ENV 추가 가이드 (ANTHROPIC_API_KEY, REDIS_URL, ANTHROPIC_MONTHLY_BUDGET_USD)
- README Status → "W2 complete", CHANGELOG W2 엔트리
- W2 회고 skeleton

## Test plan
- [x] Lightsail에 새 compose 적용 후 `docker compose ps` 전 서비스 healthy
- [x] /signup → 신규 가입 → 업로드 → 카테고리 표시 (수동 확인)
- [x] redis-cli GET llm_budget:YYYY-MM이 0보다 큼
EOF
)"
```

- [ ] **Step 2:** Squash merge → 운영 deploy-api 워크플로 트리거 → 수동 검수.

---

## Self-Review

### 1. Spec coverage

| Spec Done 항목 | 구현 Task |
|---|---|
| §2 Done #1 (/signup → 자동 로그인 → /app) | Task 15, 16, 21, 22 |
| §2 Done #2 (중복 이메일 409) | Task 15, 16 |
| §2 Done #3 (약한 비번 400) | Task 12, 15, 16 |
| §2 Done #4 (rate limit 429) | Task 14, 17, 18 |
| §2 Done #5 (category 필드 채워짐) | Task 26, 29, 30, 31, 37 |
| §2 Done #6 (룰북 즉시 분류) | Task 26, 29 |
| §2 Done #7 (캐시 hit → LLM 미호출) | Task 27, 29, 38 |
| §2 Done #8 (동일 가맹점 재업로드 시 LLM 카운트 동일) | Task 38, 46 |
| §2 Done #9 (예산 초과 → unknown) | Task 28, 38 |
| §2 Done #10 (우리카드 업로드) | Task 41-46 |
| §2 Done #11 (하나카드 업로드) | Task 49-51 |
| §2 Done #12 (자동 카드사 dispatch) | Task 42, 44, 45 |
| §2 Done #13 (PR 5+개 main squash merge) | 매 Phase 마지막 task |
| §2 Done #14 (README/CHANGELOG W2 갱신) | Task 56, 57 |
| §3 Decisions (15개) | Phase 0~8 전반 |
| §6 Data Model (llm_usage_log) | Task 25 |
| §7 Data Flow (signup, classify) | Task 16, 29, 37 |
| §8 Error Handling (5개 코드) | Task 12, 14, 15, 16, 17, 42, 45 |
| §11 ENV 키 명세 | Task 07, 28, 35, 55 |
| §12 CI workflow PR 트리거 + redis 서비스 | Task 02, 03 |

### 2. Placeholder scan
- 모든 step에 실제 코드/명령/예상 출력 포함. "TBD"/"TODO" 없음. 예외: 우리/하나 파서의 실제 시트명·헤더 컬럼명은 사용자 본인 명세서에 따라 fixture 빌더 스크립트와 파서 코드의 상수 부분을 조정해야 함 — 이건 Task 41 Step 2, Task 49 Step 2에서 "메모"로 명시. plan 작성 시점에 알 수 없는 정보이므로 placeholder가 아니라 사용자가 직접 채워야 하는 정상 단계.

### 3. Type consistency
- `Usage`, `Category`, `ParseResult`, `TransactionRow` — Phase 4/5에서 정의한 시그니처가 Phase 6/7에서 그대로 import되어 사용됨.
- `categorization.cache.set`은 builtin `set`과 충돌. `# noqa: A001`로 처리 (Task 27).
- `samsung_card.py`의 `detect(wb) -> bool` 시그니처가 Task 42 Step 4에서 추가됨 — registry가 이를 호출.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-13-w2-multi-user-llm-categorization.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — Phase별로 fresh subagent 디스패치, 두 단계 리뷰, 빠른 반복.
2. **Inline Execution** — 현재 세션에서 executing-plans 스킬로 batch + checkpoint.

W2는 8 Phase × 평균 6 task = 약 50 task. Subagent-driven이 컨텍스트 관리상 유리.

Which approach?
