# spendLens W1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** spendLens 4-5주 풀스택 프로젝트의 첫 출하 가능 단위(Week 1)를 구현한다. 라이브 URL 두 개(Vercel web + Lightsail api)에서 게스트 모드 시드 데모와 본인 모드(JWT 인증 → 삼성카드 XLSX 업로드 → 거래 리스트)가 동작하고, main push 시 GitHub Actions가 자동 배포한다.

**Architecture:** pnpm workspaces 모노레포(`apps/web` + `packages/parser-shared`) + 독립 Python 프로젝트(`apps/api`). 백엔드는 Lightsail VPS의 Docker Compose(Caddy+FastAPI)로, 프론트는 Vercel로, DB는 Supabase Postgres로. 인증은 FastAPI 자체 JWT(argon2id + access 15m + refresh 7d httpOnly cookie), 사용자는 ENV seed로 1명. 파서는 `pandas` + `openpyxl`로 삼성카드 XLSX(`■ 국내이용내역` 시트)를 처리. CI/CD는 GitHub Actions → GHCR → SSH로 Lightsail에서 `docker compose pull && up -d`.

**Tech Stack:**
- Frontend: React 18, Vite, TypeScript, Tailwind CSS, Zustand, axios, React Router
- Backend: Python 3.12, FastAPI, uvicorn, asyncpg, pandas, openpyxl, argon2-cffi, PyJWT, pydantic-settings, Alembic
- Infra: AWS Lightsail Ubuntu 22.04, Docker Compose, Caddy v2 (Let's Encrypt), Supabase Postgres (Tokyo), Vercel, 가비아 DNS
- CI/CD: GitHub Actions, GHCR, appleboy/ssh-action
- Test: pytest (api), vitest (web)

**Reference spec:** `docs/superpowers/specs/2026-04-29-w1-skeleton-and-samsung-xlsx-parser-design.md`

**Branching policy:** 모든 작업은 `main`에 직접 commit. PR 흐름은 W2부터(다중 사용자/CR 흐름 도입 시).

**Conventional Commit prefix:** `feat:` 새 기능, `chore:` 설정/인프라, `test:` 테스트, `fix:` 버그, `docs:` 문서, `ci:` 워크플로.

---

## Pre-flight Setup (Phase 0 — 수동 가이드, 코드 시작 전)

이 단계는 **코드 작성이 아닌 외부 서비스 셋업**이다. Phase 1 코딩 시작 전에 한 번 끝내고, Phase 13 배포 시 secrets/credentials을 채워 사용한다. 각 step의 결과(URL/key)는 안전한 곳(예: 1Password/로컬 메모)에 보관.

### Task 00-A: Supabase 프로젝트 생성

- [ ] **Step 1:** [supabase.com](https://supabase.com) → 로그인 → "New project"
- [ ] **Step 2:** Project name = `spendlens`, region = **Northeast Asia (Tokyo)**, plan = Free
- [ ] **Step 3:** DB password 설정 (강력한 랜덤). 생성 완료까지 1~2분 대기
- [ ] **Step 4:** Project Settings → Database → "Connection string" → URI 복사 (예: `postgresql://postgres:<pwd>@db.<ref>.supabase.co:5432/postgres`). 보관: `DATABASE_URL`
- [ ] **Step 5:** SQL Editor에서 다음 실행:
```sql
CREATE EXTENSION IF NOT EXISTS citext;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
```

### Task 00-B: AWS Lightsail 인스턴스 생성

- [ ] **Step 1:** [lightsail.aws.amazon.com](https://lightsail.aws.amazon.com) → "Create instance"
- [ ] **Step 2:** Region = Seoul(ap-northeast-2), Platform = Linux, Blueprint = Ubuntu 22.04 LTS
- [ ] **Step 3:** Plan = $5/mo (1 vCPU, 1GB RAM, 40GB SSD, 2TB transfer). 메모리 부족 우려 시 $10/mo로
- [ ] **Step 4:** Instance name = `spendlens-api-prod`. Create
- [ ] **Step 5:** 인스턴스 부팅 후 "Networking" → "Static IP" → 정적 IP 할당 + 보관
- [ ] **Step 6:** "Networking" → Firewall에 다음 규칙 추가:
   - HTTP (80) — Anywhere
   - HTTPS (443) — Anywhere
   - Custom (22) — *내 IP만* (가능하면)
- [ ] **Step 7:** "Account" → SSH keys → 키 다운로드 (.pem). chmod 400으로 보관. 보관: `LIGHTSAIL_SSH_KEY` (private), `LIGHTSAIL_HOST` (정적 IP)

### Task 00-C: 가비아 DNS 레코드 등록

- [ ] **Step 1:** My가비아 → 서비스 관리 → 도메인 → `suim-app.store` → DNS 관리툴
- [ ] **Step 2:** 다음 레코드 추가:
   - 호스트: `spendlens` / 타입: CNAME / 값: `cname.vercel-dns.com.` / TTL: 3600
   - 호스트: `api.spendlens` / 타입: A / 값: `<Lightsail 정적 IP>` / TTL: 3600
- [ ] **Step 3:** 적용 후 5분~몇 시간 대기. 확인:
```bash
nslookup spendlens.suim-app.store
nslookup api.spendlens.suim-app.store
```

### Task 00-D: Vercel 프로젝트 (코드 push 후 진짜 연결, 여기선 계정만)

- [ ] **Step 1:** [vercel.com](https://vercel.com) → GitHub 계정으로 로그인
- [ ] **Step 2:** GitHub 권한 부여 (acceptha 조직 또는 본인 계정의 spendLens 레포 접근)
- [ ] **Step 3:** 본 작업은 Phase 13에서 import. 여기선 stop.

### Task 00-E: GitHub 레포 + GHCR PAT

- [ ] **Step 1:** GitHub에서 `acceptha/spendLens` 레포가 비공개로 존재 확인 (이미 로컬에 git init 됨, push만 안 됨)
- [ ] **Step 2:** GitHub → Settings (개인) → Developer settings → Personal access tokens → Tokens (classic) → Generate new token (classic)
- [ ] **Step 3:** Note = `spendlens-ghcr-push-pull`, Expiration = 90 days, scope = `write:packages`, `read:packages`, `delete:packages`
- [ ] **Step 4:** 발급된 토큰 보관: `GHCR_TOKEN`

### Task 00-F: Lightsail SSH 첫 접속 + Docker 설치 (lightsail-bootstrap.sh로 자동화 예정 — Phase 13에서)

- [ ] **Step 1:** 로컬에서 SSH 가능 확인:
```bash
ssh -i ~/.ssh/lightsail-spendlens.pem ubuntu@<LIGHTSAIL_HOST>
```
연결 성공만 확인하고 즉시 종료. Phase 13에서 실제 셋업.

---

## Phase 1: 모노레포 루트 셋업 (3 tasks)

### Task 01: pnpm 워크스페이스 + 루트 package.json

**Files:**
- Create: `package.json`
- Create: `pnpm-workspace.yaml`
- Create: `.npmrc`

- [ ] **Step 1:** `pnpm`이 설치돼 있는지 확인:
```bash
pnpm --version
```
없으면: `npm install -g pnpm`

- [ ] **Step 2:** Create `package.json`:
```json
{
  "name": "spendlens",
  "version": "0.0.0",
  "private": true,
  "packageManager": "pnpm@9.0.0",
  "engines": {
    "node": ">=20"
  },
  "scripts": {
    "lint": "pnpm -r lint",
    "test": "pnpm -r test",
    "build": "pnpm -r build",
    "dev": "pnpm --filter @spendlens/web dev"
  }
}
```

- [ ] **Step 3:** Create `pnpm-workspace.yaml`:
```yaml
packages:
  - "apps/*"
  - "packages/*"
```

- [ ] **Step 4:** Create `.npmrc`:
```
shamefully-hoist=false
strict-peer-dependencies=false
```

- [ ] **Step 5:** Verify:
```bash
pnpm install
```
Expected: `Lockfile is up to date, resolution step is skipped` 또는 빈 install 성공.

- [ ] **Step 6:** Commit:
```bash
git add package.json pnpm-workspace.yaml .npmrc
git commit -m "chore: setup pnpm workspaces root"
```

### Task 02: .env.example 템플릿

**Files:**
- Create: `.env.example`

- [ ] **Step 1:** Create `.env.example`:
```bash
# DB (Supabase Postgres connection string)
DATABASE_URL=postgresql://postgres:<pwd>@db.<ref>.supabase.co:5432/postgres

# 본인 모드 단일 사용자 (ENV seed)
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD_HASH=

# JWT
JWT_SECRET=
JWT_ACCESS_TTL_MINUTES=15
JWT_REFRESH_TTL_DAYS=7

# CORS
WEB_ORIGIN=https://spendlens.suim-app.store

# 운영
LOG_LEVEL=INFO
```

- [ ] **Step 2:** Commit:
```bash
git add .env.example
git commit -m "chore: add .env.example template"
```

### Task 03: README 초안

**Files:**
- Create: `README.md`

- [ ] **Step 1:** Create `README.md`:
```markdown
# spendLens

> 광고 없는 가계부 · AI 코칭 · 데이터는 내 서버

## Status
W1 in progress (skeleton + 삼성카드 XLSX 파서 + 첫 배포). Live demo will land at:
- Web: https://spendlens.suim-app.store (TBD)
- API: https://api.spendlens.suim-app.store/healthz (TBD)

## Tech Stack
- Frontend: React + Vite + TypeScript + Tailwind + Zustand
- Backend: FastAPI + pandas + openpyxl + asyncpg + Alembic
- AI: Claude Haiku (W2)
- Deploy: Vercel + AWS Lightsail (Docker Compose + Caddy) + Supabase Postgres + GitHub Actions

## Repo Layout
\`\`\`
apps/web        — React frontend (Vercel)
apps/api        — FastAPI backend (Lightsail)
packages/parser-shared — Shared TS types
seed/           — 게스트 모드 시드 데이터
infra/          — Docker / Caddy / bootstrap
scripts/        — 운영 도우미 스크립트
docs/           — 설계/계획 문서
\`\`\`

## Local Dev
See `infra/README.md`.

## Spec & Plan
- Spec: `docs/superpowers/specs/2026-04-29-w1-skeleton-and-samsung-xlsx-parser-design.md`
- Plan: `docs/superpowers/plans/2026-04-30-w1-skeleton-and-samsung-xlsx-parser.md`
```

- [ ] **Step 2:** Commit:
```bash
git add README.md
git commit -m "docs: add README skeleton"
```

---

## Phase 2: apps/api 백본 (7 tasks)

### Task 04: apps/api 디렉토리 + pyproject.toml + uv 셋업

**Files:**
- Create: `apps/api/pyproject.toml`
- Create: `apps/api/.python-version`
- Create: `apps/api/README.md`

- [ ] **Step 1:** `uv` 설치 확인:
```bash
uv --version
```
없으면 [uv 공식 설치](https://docs.astral.sh/uv/) (Windows: `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`)

- [ ] **Step 2:** Create `apps/api/.python-version`:
```
3.12
```

- [ ] **Step 3:** Create `apps/api/pyproject.toml`:
```toml
[project]
name = "spendlens-api"
version = "0.0.0"
description = "spendLens FastAPI backend"
requires-python = ">=3.12,<3.13"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.32.0",
    "pydantic>=2.9.0",
    "pydantic-settings>=2.6.0",
    "asyncpg>=0.30.0",
    "alembic>=1.13.0",
    "sqlalchemy>=2.0.30",
    "argon2-cffi>=23.1.0",
    "pyjwt>=2.9.0",
    "pandas>=2.2.0",
    "openpyxl>=3.1.0",
    "python-multipart>=0.0.12",
]

[dependency-groups]
dev = [
    "pytest>=8.3.0",
    "pytest-asyncio>=0.24.0",
    "pytest-cov>=5.0.0",
    "httpx>=0.27.0",
    "ruff>=0.6.0",
    "mypy>=1.11.0",
]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "N", "S"]
ignore = ["S101"]  # allow assert in tests

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 4:** Create `apps/api/README.md`:
```markdown
# spendLens API

FastAPI backend, managed by `uv`.

## Local
\`\`\`bash
cd apps/api
uv sync
uv run uvicorn app.main:app --reload
\`\`\`
```

- [ ] **Step 5:** 실행해 의존성 락 생성:
```bash
cd apps/api && uv sync
```
Expected: `uv.lock` 생성, `.venv/` 생성.

- [ ] **Step 6:** Commit:
```bash
git add apps/api/pyproject.toml apps/api/.python-version apps/api/README.md apps/api/uv.lock
git commit -m "chore(api): scaffold apps/api with uv + pyproject.toml"
```

### Task 05: settings.py (pydantic-settings)

**Files:**
- Create: `apps/api/app/__init__.py` (empty)
- Create: `apps/api/app/settings.py`
- Create: `apps/api/tests/__init__.py` (empty)
- Create: `apps/api/tests/test_settings.py`

- [ ] **Step 1:** Create `apps/api/app/__init__.py` (empty file)

- [ ] **Step 2:** Create `apps/api/tests/__init__.py` (empty file)

- [ ] **Step 3:** Create test `apps/api/tests/test_settings.py`:
```python
import os

def test_settings_loads_from_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://test")
    monkeypatch.setenv("ADMIN_EMAIL", "test@example.com")
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", "$argon2id$xxx")
    monkeypatch.setenv("JWT_SECRET", "secret123")
    monkeypatch.setenv("WEB_ORIGIN", "http://localhost:5173")

    from app.settings import Settings
    s = Settings()

    assert s.database_url == "postgresql://test"
    assert s.admin_email == "test@example.com"
    assert s.jwt_access_ttl_minutes == 15  # default
    assert s.jwt_refresh_ttl_days == 7     # default
    assert s.log_level == "INFO"           # default
```

- [ ] **Step 4:** Run test (expect FAIL — Settings 없음):
```bash
cd apps/api && uv run pytest tests/test_settings.py -v
```
Expected: ImportError or ModuleNotFoundError.

- [ ] **Step 5:** Implement `apps/api/app/settings.py`:
```python
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    database_url: str
    admin_email: str
    admin_password_hash: str
    jwt_secret: str
    jwt_access_ttl_minutes: int = 15
    jwt_refresh_ttl_days: int = 7
    web_origin: str = "http://localhost:5173"
    log_level: str = "INFO"


settings = Settings()
```

- [ ] **Step 6:** Run test (expect PASS):
```bash
cd apps/api && uv run pytest tests/test_settings.py -v
```
Expected: 1 passed.

- [ ] **Step 7:** Commit:
```bash
git add apps/api/app/__init__.py apps/api/app/settings.py apps/api/tests/__init__.py apps/api/tests/test_settings.py
git commit -m "feat(api): add Settings via pydantic-settings"
```

### Task 06: db.py (asyncpg pool) + lifespan

**Files:**
- Create: `apps/api/app/db.py`

- [ ] **Step 1:** Create `apps/api/app/db.py`:
```python
import asyncpg
from contextlib import asynccontextmanager
from typing import AsyncIterator

from app.settings import settings


_pool: asyncpg.Pool | None = None


async def init_pool() -> None:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            settings.database_url,
            min_size=1,
            max_size=10,
            command_timeout=30,
        )


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("DB pool not initialized")
    return _pool


@asynccontextmanager
async def acquire() -> AsyncIterator[asyncpg.Connection]:
    pool = get_pool()
    async with pool.acquire() as conn:
        yield conn
```

- [ ] **Step 2:** Commit:
```bash
git add apps/api/app/db.py
git commit -m "feat(api): add asyncpg pool helper"
```

### Task 07: Alembic 셋업

**Files:**
- Create: `apps/api/alembic.ini`
- Create: `apps/api/migrations/env.py`
- Create: `apps/api/migrations/script.py.mako`
- Create: `apps/api/migrations/versions/.gitkeep`

- [ ] **Step 1:** alembic init:
```bash
cd apps/api && uv run alembic init -t async migrations
```
파일 생성됨: `alembic.ini`, `migrations/env.py`, `migrations/script.py.mako`, `migrations/versions/`.

- [ ] **Step 2:** Edit `apps/api/alembic.ini` — `sqlalchemy.url`을 빈 칸으로 (env.py에서 동적 주입):
```ini
sqlalchemy.url =
```

- [ ] **Step 3:** Replace `apps/api/migrations/env.py` 내용:
```python
import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

from app.settings import settings

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = None  # raw SQL 마이그레이션만 사용 (SQLAlchemy 모델 없음)


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url, target_metadata=target_metadata, literal_binds=True
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 4:** Create `apps/api/migrations/versions/.gitkeep` (빈 파일).

- [ ] **Step 5:** Commit:
```bash
git add apps/api/alembic.ini apps/api/migrations/
git commit -m "chore(api): scaffold Alembic with async env"
```

### Task 08: 첫 마이그레이션 (users + refresh_tokens + source_files + transactions)

**Files:**
- Create: `apps/api/migrations/versions/0001_initial.py`

- [ ] **Step 1:** Generate skeleton:
```bash
cd apps/api && uv run alembic revision -m "initial schema"
```
생성된 파일을 `0001_initial.py`로 rename (또는 그대로 두고 내용 교체).

- [ ] **Step 2:** Replace `apps/api/migrations/versions/0001_initial.py` 내용:
```python
"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-30
"""
from alembic import op


revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.execute("""
        CREATE TABLE users (
          id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          email         CITEXT UNIQUE NOT NULL,
          password_hash TEXT NOT NULL,
          created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    op.execute("""
        CREATE TABLE refresh_tokens (
          jti        UUID PRIMARY KEY,
          user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          expires_at TIMESTAMPTZ NOT NULL,
          revoked_at TIMESTAMPTZ
        );
    """)
    op.execute("CREATE INDEX idx_refresh_user ON refresh_tokens(user_id);")

    op.execute("""
        CREATE TABLE source_files (
          id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          user_id        UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          source_type    TEXT NOT NULL,
          filename       TEXT NOT NULL,
          rows_total     INTEGER NOT NULL,
          rows_inserted  INTEGER NOT NULL,
          rows_skipped   INTEGER NOT NULL,
          uploaded_at    TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    op.execute("""
        CREATE TABLE transactions (
          id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          source_file_id      UUID REFERENCES source_files(id) ON DELETE SET NULL,
          source_type         TEXT NOT NULL,
          txn_date            DATE NOT NULL,
          txn_time            TIME,
          amount              NUMERIC(12,2) NOT NULL,
          merchant_raw        TEXT NOT NULL,
          merchant_normalized TEXT,
          approval_no         TEXT,
          card_last4          TEXT,
          installment_months  INTEGER,
          is_canceled         BOOLEAN NOT NULL DEFAULT false,
          category            TEXT NOT NULL DEFAULT 'unknown',
          essential           BOOLEAN,
          essential_reason    TEXT,
          dedup_hash          TEXT NOT NULL,
          raw_row             JSONB NOT NULL,
          created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
          UNIQUE (user_id, dedup_hash)
        );
    """)
    op.execute("CREATE INDEX idx_transactions_user_date ON transactions(user_id, txn_date DESC);")
    op.execute(
        "CREATE INDEX idx_transactions_approval ON transactions(user_id, approval_no) "
        "WHERE approval_no IS NOT NULL;"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS transactions;")
    op.execute("DROP TABLE IF EXISTS source_files;")
    op.execute("DROP TABLE IF EXISTS refresh_tokens;")
    op.execute("DROP TABLE IF EXISTS users;")
```

- [ ] **Step 3:** 로컬에서 마이그레이션 실행 (Supabase DB에 직접):
```bash
cd apps/api && uv run alembic upgrade head
```
Expected: `Running upgrade -> 0001, initial schema`. Supabase Table Editor에서 4개 테이블 확인.

- [ ] **Step 4:** Commit:
```bash
git add apps/api/migrations/versions/0001_initial.py
git commit -m "feat(api): initial schema (users, refresh_tokens, source_files, transactions)"
```

### Task 09: app/main.py FastAPI 앱 + /healthz + lifespan

**Files:**
- Create: `apps/api/app/main.py`
- Create: `apps/api/tests/test_health.py`

- [ ] **Step 1:** Create test `apps/api/tests/test_health.py`:
```python
from httpx import ASGITransport, AsyncClient
import pytest


@pytest.mark.asyncio
async def test_healthz_returns_ok(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://test")
    monkeypatch.setenv("ADMIN_EMAIL", "test@example.com")
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", "$argon2id$xxx")
    monkeypatch.setenv("JWT_SECRET", "secret123")
    # importing after env set
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # lifespan은 DB 연결 시도하므로 startup 우회 (TestClient 직접 호출)
        resp = await client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
```

- [ ] **Step 2:** Run test (expect FAIL — main.py 없음):
```bash
cd apps/api && uv run pytest tests/test_health.py -v
```
Expected: ImportError.

- [ ] **Step 3:** Create `apps/api/app/main.py`:
```python
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import init_pool, close_pool
from app.settings import settings

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger("spendlens")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_pool()
    # seed_admin_user는 Task 14에서 추가
    logger.info("startup complete")
    yield
    await close_pool()
    logger.info("shutdown complete")


app = FastAPI(title="spendLens API", version="0.0.1", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 4:** 테스트가 lifespan을 우회하도록 — `tests/test_health.py`를 lifespan 무시 모드로 수정:
```python
from httpx import ASGITransport, AsyncClient
import pytest


@pytest.mark.asyncio
async def test_healthz_returns_ok(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://test")
    monkeypatch.setenv("ADMIN_EMAIL", "test@example.com")
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", "$argon2id$xxx")
    monkeypatch.setenv("JWT_SECRET", "secret123")
    from app.main import app

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
```

- [ ] **Step 5:** Run test (expect PASS):
```bash
cd apps/api && uv run pytest tests/test_health.py -v
```
Expected: 1 passed (lifespan은 startup 안 호출되거나 DB 없어도 healthz는 응답).

- [ ] **Step 6:** Commit:
```bash
git add apps/api/app/main.py apps/api/tests/test_health.py
git commit -m "feat(api): add FastAPI app with /healthz and lifespan"
```

### Task 10: 테스트 인프라 (conftest with test DB fixture)

**Files:**
- Create: `apps/api/tests/conftest.py`
- Create: `apps/api/tests/.env.test`

- [ ] **Step 1:** Create `apps/api/tests/.env.test`:
```bash
DATABASE_URL=postgresql://postgres:postgres@localhost:5433/spendlens_test
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD_HASH=$argon2id$v=19$m=65536,t=3,p=4$placeholder
JWT_SECRET=test_secret_64chars_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
WEB_ORIGIN=http://localhost:5173
LOG_LEVEL=WARNING
```

- [ ] **Step 2:** Create `apps/api/tests/conftest.py`:
```python
import os
import asyncio
from pathlib import Path

import asyncpg
import pytest


def _load_test_env() -> None:
    env_file = Path(__file__).parent / ".env.test"
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


_load_test_env()


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_db_pool():
    """세션 단위 DB 풀. 로컬 docker-compose의 postgres-test 컨테이너 또는 CI services 사용."""
    pool = await asyncpg.create_pool(os.environ["DATABASE_URL"], min_size=1, max_size=5)
    yield pool
    await pool.close()


@pytest.fixture(autouse=True)
async def reset_tables(test_db_pool):
    """각 테스트 전 모든 테이블을 비움. CASCADE로 의존성 해결."""
    async with test_db_pool.acquire() as conn:
        await conn.execute("""
            TRUNCATE transactions, source_files, refresh_tokens, users
            RESTART IDENTITY CASCADE;
        """)
    yield
```

- [ ] **Step 3:** Update `.gitignore`로 `apps/api/tests/.env.test` 가시성:
```bash
# 결정: .env.test는 placeholder 비번/키만 들어 있으므로 git 포함. 만약 비밀이 들어가면 별도 .env.test.local로.
```
(아무 변경 없음, 위 파일은 git 포함)

- [ ] **Step 4:** Commit:
```bash
git add apps/api/tests/conftest.py apps/api/tests/.env.test
git commit -m "test(api): add session-scoped DB pool fixture and table reset"
```

---

## Phase 3: 인증 (8 tasks)

### Task 11: auth/password.py (argon2)

**Files:**
- Create: `apps/api/app/auth/__init__.py` (empty)
- Create: `apps/api/app/auth/password.py`
- Create: `apps/api/tests/auth/__init__.py` (empty)
- Create: `apps/api/tests/auth/test_password.py`

- [ ] **Step 1:** Create empty `apps/api/app/auth/__init__.py` and `apps/api/tests/auth/__init__.py`.

- [ ] **Step 2:** Create test `apps/api/tests/auth/test_password.py`:
```python
import pytest
from app.auth.password import hash_password, verify_password


def test_hash_password_returns_argon2_string():
    h = hash_password("hunter2")
    assert h.startswith("$argon2id$")


def test_verify_password_round_trip():
    h = hash_password("hunter2")
    assert verify_password(h, "hunter2") is True
    assert verify_password(h, "wrong") is False


def test_verify_invalid_hash_returns_false():
    assert verify_password("not-a-hash", "anything") is False
```

- [ ] **Step 3:** Run test (expect FAIL):
```bash
cd apps/api && uv run pytest tests/auth/test_password.py -v
```
Expected: ModuleNotFoundError.

- [ ] **Step 4:** Implement `apps/api/app/auth/password.py`:
```python
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError

_ph = PasswordHasher()


def hash_password(plain: str) -> str:
    return _ph.hash(plain)


def verify_password(hashed: str, plain: str) -> bool:
    try:
        _ph.verify(hashed, plain)
        return True
    except (VerifyMismatchError, InvalidHashError, Exception):
        return False
```

- [ ] **Step 5:** Run test (expect PASS):
```bash
cd apps/api && uv run pytest tests/auth/test_password.py -v
```
Expected: 3 passed.

- [ ] **Step 6:** Commit:
```bash
git add apps/api/app/auth/__init__.py apps/api/app/auth/password.py apps/api/tests/auth/__init__.py apps/api/tests/auth/test_password.py
git commit -m "feat(api): add argon2id password hashing"
```

### Task 12: auth/jwt.py (HS256 발급/검증)

**Files:**
- Create: `apps/api/app/auth/jwt.py`
- Create: `apps/api/tests/auth/test_jwt.py`

- [ ] **Step 1:** Create test `apps/api/tests/auth/test_jwt.py`:
```python
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
import jwt as pyjwt

from app.auth.jwt import create_access_token, create_refresh_token, decode_token


def test_create_access_token_contains_sub_and_type():
    user_id = uuid4()
    token = create_access_token(user_id)
    payload = decode_token(token)
    assert payload["sub"] == str(user_id)
    assert payload["type"] == "access"


def test_create_refresh_token_contains_jti():
    user_id = uuid4()
    token, jti = create_refresh_token(user_id)
    payload = decode_token(token)
    assert payload["sub"] == str(user_id)
    assert payload["type"] == "refresh"
    assert payload["jti"] == str(jti)


def test_decode_invalid_signature_raises():
    user_id = uuid4()
    token = create_access_token(user_id)
    tampered = token[:-3] + "AAA"
    with pytest.raises(pyjwt.InvalidTokenError):
        decode_token(tampered)


def test_decode_expired_raises(monkeypatch):
    user_id = uuid4()
    # past expiry
    monkeypatch.setattr("app.auth.jwt._access_ttl", lambda: timedelta(seconds=-10))
    token = create_access_token(user_id)
    with pytest.raises(pyjwt.ExpiredSignatureError):
        decode_token(token)
```

- [ ] **Step 2:** Run (expect FAIL):
```bash
cd apps/api && uv run pytest tests/auth/test_jwt.py -v
```

- [ ] **Step 3:** Implement `apps/api/app/auth/jwt.py`:
```python
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4
from typing import Any

import jwt as pyjwt

from app.settings import settings


_ALGORITHM = "HS256"


def _access_ttl() -> timedelta:
    return timedelta(minutes=settings.jwt_access_ttl_minutes)


def _refresh_ttl() -> timedelta:
    return timedelta(days=settings.jwt_refresh_ttl_days)


def create_access_token(user_id: UUID) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + _access_ttl()).timestamp()),
    }
    return pyjwt.encode(payload, settings.jwt_secret, algorithm=_ALGORITHM)


def create_refresh_token(user_id: UUID) -> tuple[str, UUID]:
    jti = uuid4()
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "jti": str(jti),
        "type": "refresh",
        "iat": int(now.timestamp()),
        "exp": int((now + _refresh_ttl()).timestamp()),
    }
    return pyjwt.encode(payload, settings.jwt_secret, algorithm=_ALGORITHM), jti


def decode_token(token: str) -> dict[str, Any]:
    return pyjwt.decode(token, settings.jwt_secret, algorithms=[_ALGORITHM])
```

- [ ] **Step 4:** Run (expect PASS):
```bash
cd apps/api && uv run pytest tests/auth/test_jwt.py -v
```
Expected: 4 passed.

- [ ] **Step 5:** Commit:
```bash
git add apps/api/app/auth/jwt.py apps/api/tests/auth/test_jwt.py
git commit -m "feat(api): add JWT access/refresh token helpers"
```

### Task 13: scripts/hash_password.py CLI

**Files:**
- Create: `scripts/hash_password.py`

- [ ] **Step 1:** Create `scripts/hash_password.py`:
```python
"""Generate an argon2id hash for ADMIN_PASSWORD_HASH env.

Usage:
    cd apps/api && uv run python ../../scripts/hash_password.py
"""
import getpass
import sys

# 동일 venv에서 실행되어야 argon2-cffi 사용 가능 (apps/api에서 uv run)
from argon2 import PasswordHasher


def main() -> int:
    pwd = getpass.getpass("Enter password: ")
    confirm = getpass.getpass("Confirm:        ")
    if pwd != confirm:
        print("Mismatch.", file=sys.stderr)
        return 1
    h = PasswordHasher().hash(pwd)
    print()
    print(h)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2:** Smoke test:
```bash
cd apps/api && echo "test123" | uv run python ../../scripts/hash_password.py
```
(getpass가 stdin tty를 요구할 수 있으므로 이 명령이 실패하면 인터랙티브로 직접 실행해서 동작 확인)

- [ ] **Step 3:** Commit:
```bash
git add scripts/hash_password.py
git commit -m "chore: add hash_password.py CLI helper"
```

### Task 14: lifespan에 seed_admin_user 추가

**Files:**
- Modify: `apps/api/app/main.py`
- Create: `apps/api/app/auth/seed.py`
- Create: `apps/api/tests/auth/test_seed.py`

- [ ] **Step 1:** Create test `apps/api/tests/auth/test_seed.py`:
```python
import pytest
from app.auth.seed import ensure_admin_user
from app.settings import settings


@pytest.mark.asyncio
async def test_seed_creates_user_when_missing(test_db_pool):
    async with test_db_pool.acquire() as conn:
        await ensure_admin_user(conn)
        row = await conn.fetchrow("SELECT email FROM users WHERE email = $1", settings.admin_email)
    assert row is not None
    assert row["email"] == settings.admin_email


@pytest.mark.asyncio
async def test_seed_is_idempotent(test_db_pool):
    async with test_db_pool.acquire() as conn:
        await ensure_admin_user(conn)
        await ensure_admin_user(conn)
        count = await conn.fetchval("SELECT COUNT(*) FROM users WHERE email = $1", settings.admin_email)
    assert count == 1
```

- [ ] **Step 2:** Run (expect FAIL):
```bash
cd apps/api && uv run pytest tests/auth/test_seed.py -v
```

- [ ] **Step 3:** Create `apps/api/app/auth/seed.py`:
```python
import asyncpg

from app.settings import settings


async def ensure_admin_user(conn: asyncpg.Connection) -> None:
    """Insert admin user from ENV if not exists. Idempotent."""
    await conn.execute(
        """
        INSERT INTO users (email, password_hash)
        VALUES ($1, $2)
        ON CONFLICT (email) DO NOTHING
        """,
        settings.admin_email,
        settings.admin_password_hash,
    )
```

- [ ] **Step 4:** Modify `apps/api/app/main.py` lifespan to call seed:
```python
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import init_pool, close_pool, acquire
from app.auth.seed import ensure_admin_user
from app.settings import settings

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger("spendlens")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_pool()
    async with acquire() as conn:
        await ensure_admin_user(conn)
    logger.info("startup complete; admin seeded")
    yield
    await close_pool()
    logger.info("shutdown complete")


app = FastAPI(title="spendLens API", version="0.0.1", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 5:** Run (expect PASS):
```bash
cd apps/api && uv run pytest tests/auth/test_seed.py -v
```
Expected: 2 passed.

- [ ] **Step 6:** Commit:
```bash
git add apps/api/app/auth/seed.py apps/api/app/main.py apps/api/tests/auth/test_seed.py
git commit -m "feat(api): seed admin user from ENV on startup"
```

### Task 15: /auth/login

**Files:**
- Create: `apps/api/app/auth/routes.py`
- Create: `apps/api/app/auth/schemas.py`
- Modify: `apps/api/app/main.py` (include router)
- Create: `apps/api/tests/auth/test_login.py`

- [ ] **Step 1:** Create `apps/api/app/auth/schemas.py`:
```python
from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
```

- [ ] **Step 2:** Create test `apps/api/tests/auth/test_login.py`:
```python
import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.password import hash_password
from app.auth.seed import ensure_admin_user
from app.settings import settings


@pytest.fixture
async def seeded_user(test_db_pool, monkeypatch):
    pwd_hash = hash_password("hunter2")
    monkeypatch.setattr(settings, "admin_password_hash", pwd_hash)
    async with test_db_pool.acquire() as conn:
        await conn.execute("DELETE FROM users")
        await ensure_admin_user(conn)
    return settings.admin_email, "hunter2"


@pytest.mark.asyncio
async def test_login_success(seeded_user):
    from app.main import app
    email, pwd = seeded_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/auth/login", json={"email": email, "password": pwd})
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert body["token_type"] == "Bearer"
    assert "refresh_token" in resp.cookies


@pytest.mark.asyncio
async def test_login_wrong_password(seeded_user):
    from app.main import app
    email, _ = seeded_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/auth/login", json={"email": email, "password": "wrong"})
    assert resp.status_code == 401
```

- [ ] **Step 3:** Run (expect FAIL):
```bash
cd apps/api && uv run pytest tests/auth/test_login.py -v
```

- [ ] **Step 4:** Create `apps/api/app/auth/routes.py`:
```python
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Response

from app.auth.jwt import create_access_token, create_refresh_token
from app.auth.password import verify_password
from app.auth.schemas import LoginRequest, LoginResponse
from app.db import acquire
from app.settings import settings


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest, response: Response) -> LoginResponse:
    async with acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, password_hash FROM users WHERE email = $1", req.email
        )
        if row is None or not verify_password(row["password_hash"], req.password):
            raise HTTPException(status_code=401, detail="INVALID_CREDENTIALS")

        user_id = row["id"]
        access = create_access_token(user_id)
        refresh, jti = create_refresh_token(user_id)
        expires_at = datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_ttl_days)

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
    return LoginResponse(access_token=access)
```

- [ ] **Step 5:** Modify `apps/api/app/main.py` — include router. Add to import block and after `add_middleware`:
```python
from app.auth.routes import router as auth_router
# ...
app.include_router(auth_router)
```

- [ ] **Step 6:** Run (expect PASS):
```bash
cd apps/api && uv run pytest tests/auth/test_login.py -v
```
Expected: 2 passed.

- [ ] **Step 7:** Commit:
```bash
git add apps/api/app/auth/routes.py apps/api/app/auth/schemas.py apps/api/app/main.py apps/api/tests/auth/test_login.py
git commit -m "feat(api): add POST /auth/login with JWT + refresh cookie"
```

### Task 16: /auth/refresh (회전)

**Files:**
- Modify: `apps/api/app/auth/routes.py` (add /refresh)
- Modify: `apps/api/app/auth/schemas.py` (add RefreshResponse)
- Create: `apps/api/tests/auth/test_refresh.py`

- [ ] **Step 1:** Add to `apps/api/app/auth/schemas.py`:
```python
class RefreshResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
```

- [ ] **Step 2:** Create test `apps/api/tests/auth/test_refresh.py`:
```python
import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.password import hash_password
from app.auth.seed import ensure_admin_user
from app.settings import settings


@pytest.fixture
async def seeded_user(test_db_pool, monkeypatch):
    pwd_hash = hash_password("hunter2")
    monkeypatch.setattr(settings, "admin_password_hash", pwd_hash)
    async with test_db_pool.acquire() as conn:
        await conn.execute("DELETE FROM users")
        await ensure_admin_user(conn)
    return settings.admin_email, "hunter2"


@pytest.mark.asyncio
async def test_refresh_rotates_jti(test_db_pool, seeded_user):
    from app.main import app
    email, pwd = seeded_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login_resp = await client.post("/auth/login", json={"email": email, "password": pwd})
        assert login_resp.status_code == 200
        cookies1 = login_resp.cookies

        refresh_resp = await client.post("/auth/refresh", cookies=cookies1)
        assert refresh_resp.status_code == 200
        assert "access_token" in refresh_resp.json()
        # 새 refresh cookie 발급
        assert "refresh_token" in refresh_resp.cookies

    # DB에 두 jti가 모두 존재하지만 첫 번째는 revoked
    async with test_db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT jti, revoked_at FROM refresh_tokens ORDER BY expires_at")
    assert len(rows) == 2
    assert rows[0]["revoked_at"] is not None
    assert rows[1]["revoked_at"] is None


@pytest.mark.asyncio
async def test_refresh_without_cookie_returns_401(seeded_user):
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/auth/refresh")
    assert resp.status_code == 401
```

- [ ] **Step 3:** Run (expect FAIL):
```bash
cd apps/api && uv run pytest tests/auth/test_refresh.py -v
```

- [ ] **Step 4:** Add to `apps/api/app/auth/routes.py`:
```python
from uuid import UUID
from fastapi import Cookie
import jwt as pyjwt

from app.auth.jwt import decode_token
from app.auth.schemas import RefreshResponse


@router.post("/refresh", response_model=RefreshResponse)
async def refresh(response: Response, refresh_token: str | None = Cookie(default=None)) -> RefreshResponse:
    if not refresh_token:
        raise HTTPException(status_code=401, detail="MISSING_REFRESH")

    try:
        payload = decode_token(refresh_token)
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="TOKEN_EXPIRED")
    except pyjwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="INVALID_TOKEN")

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="WRONG_TOKEN_TYPE")

    user_id = UUID(payload["sub"])
    jti = UUID(payload["jti"])

    async with acquire() as conn:
        row = await conn.fetchrow(
            "SELECT revoked_at FROM refresh_tokens WHERE jti = $1", jti
        )
        if row is None or row["revoked_at"] is not None:
            raise HTTPException(status_code=401, detail="TOKEN_REVOKED")

        # rotate
        await conn.execute(
            "UPDATE refresh_tokens SET revoked_at = now() WHERE jti = $1", jti
        )

        new_access = create_access_token(user_id)
        new_refresh, new_jti = create_refresh_token(user_id)
        expires_at = datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_ttl_days)

        await conn.execute(
            "INSERT INTO refresh_tokens (jti, user_id, expires_at) VALUES ($1, $2, $3)",
            new_jti, user_id, expires_at,
        )

    response.set_cookie(
        key="refresh_token",
        value=new_refresh,
        max_age=settings.jwt_refresh_ttl_days * 86400,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/auth",
    )
    return RefreshResponse(access_token=new_access)
```

- [ ] **Step 5:** Run (expect PASS):
```bash
cd apps/api && uv run pytest tests/auth/test_refresh.py -v
```
Expected: 2 passed.

- [ ] **Step 6:** Commit:
```bash
git add apps/api/app/auth/routes.py apps/api/app/auth/schemas.py apps/api/tests/auth/test_refresh.py
git commit -m "feat(api): add POST /auth/refresh with token rotation"
```

### Task 17: /auth/logout (revoke)

**Files:**
- Modify: `apps/api/app/auth/routes.py` (add /logout)
- Create: `apps/api/tests/auth/test_logout.py`

- [ ] **Step 1:** Create test `apps/api/tests/auth/test_logout.py`:
```python
import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.password import hash_password
from app.auth.seed import ensure_admin_user
from app.settings import settings


@pytest.fixture
async def seeded_user(test_db_pool, monkeypatch):
    pwd_hash = hash_password("hunter2")
    monkeypatch.setattr(settings, "admin_password_hash", pwd_hash)
    async with test_db_pool.acquire() as conn:
        await conn.execute("DELETE FROM users")
        await ensure_admin_user(conn)
    return settings.admin_email, "hunter2"


@pytest.mark.asyncio
async def test_logout_revokes_refresh(test_db_pool, seeded_user):
    from app.main import app
    email, pwd = seeded_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login_resp = await client.post("/auth/login", json={"email": email, "password": pwd})
        cookies = login_resp.cookies

        logout_resp = await client.post("/auth/logout", cookies=cookies)
        assert logout_resp.status_code == 204

        # 같은 cookie로 refresh 시도 → 401
        refresh_resp = await client.post("/auth/refresh", cookies=cookies)
        assert refresh_resp.status_code == 401

    async with test_db_pool.acquire() as conn:
        rows = await conn.fetch("SELECT revoked_at FROM refresh_tokens")
    assert len(rows) == 1
    assert rows[0]["revoked_at"] is not None
```

- [ ] **Step 2:** Run (expect FAIL):
```bash
cd apps/api && uv run pytest tests/auth/test_logout.py -v
```

- [ ] **Step 3:** Add to `apps/api/app/auth/routes.py`:
```python
from fastapi import status


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response, refresh_token: str | None = Cookie(default=None)) -> None:
    if refresh_token:
        try:
            payload = decode_token(refresh_token)
            jti = UUID(payload["jti"])
            async with acquire() as conn:
                await conn.execute(
                    "UPDATE refresh_tokens SET revoked_at = now() WHERE jti = $1 AND revoked_at IS NULL",
                    jti,
                )
        except (pyjwt.InvalidTokenError, KeyError, ValueError):
            pass
    response.delete_cookie("refresh_token", path="/auth")
```

- [ ] **Step 4:** Run (expect PASS):
```bash
cd apps/api && uv run pytest tests/auth/test_logout.py -v
```
Expected: 1 passed.

- [ ] **Step 5:** Commit:
```bash
git add apps/api/app/auth/routes.py apps/api/tests/auth/test_logout.py
git commit -m "feat(api): add POST /auth/logout that revokes refresh"
```

### Task 18: auth/deps.py (current_user 의존성)

**Files:**
- Create: `apps/api/app/auth/deps.py`
- Create: `apps/api/tests/auth/test_deps.py`

- [ ] **Step 1:** Create test `apps/api/tests/auth/test_deps.py`:
```python
import pytest
from uuid import UUID
from fastapi import FastAPI, Depends
from httpx import ASGITransport, AsyncClient

from app.auth.deps import current_user_id
from app.auth.jwt import create_access_token


@pytest.mark.asyncio
async def test_current_user_id_from_bearer():
    test_app = FastAPI()

    @test_app.get("/me")
    async def me(uid: UUID = Depends(current_user_id)) -> dict:
        return {"user_id": str(uid)}

    user_id = UUID("00000000-0000-0000-0000-000000000001")
    token = create_access_token(user_id)
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == {"user_id": str(user_id)}


@pytest.mark.asyncio
async def test_current_user_id_missing_header_401():
    test_app = FastAPI()

    @test_app.get("/me")
    async def me(uid: UUID = Depends(current_user_id)) -> dict:
        return {}

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/me")
    assert resp.status_code == 401
```

- [ ] **Step 2:** Run (expect FAIL):
```bash
cd apps/api && uv run pytest tests/auth/test_deps.py -v
```

- [ ] **Step 3:** Create `apps/api/app/auth/deps.py`:
```python
from uuid import UUID

from fastapi import Header, HTTPException
import jwt as pyjwt

from app.auth.jwt import decode_token


async def current_user_id(authorization: str | None = Header(default=None)) -> UUID:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="MISSING_BEARER")
    token = authorization[7:]
    try:
        payload = decode_token(token)
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="TOKEN_EXPIRED")
    except pyjwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="INVALID_TOKEN")

    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="WRONG_TOKEN_TYPE")
    return UUID(payload["sub"])
```

- [ ] **Step 4:** Run (expect PASS):
```bash
cd apps/api && uv run pytest tests/auth/test_deps.py -v
```
Expected: 2 passed.

- [ ] **Step 5:** Commit:
```bash
git add apps/api/app/auth/deps.py apps/api/tests/auth/test_deps.py
git commit -m "feat(api): add current_user_id dependency"
```

---

> **다음 Phase는 본 plan의 후속 섹션에서 이어집니다.** 본 파일은 W1 끝까지의 모든 task를 포함합니다.

---

## Phase 4: 시드 모드 백엔드 (3 tasks)

### Task 19: seed/kim_jichul.py 데이터 작성

**Files:**
- Create: `seed/kim_jichul/transactions.json`
- Create: `apps/api/app/seed/__init__.py` (empty)
- Create: `apps/api/app/seed/kim_jichul.py`

- [ ] **Step 1:** Create `seed/kim_jichul/transactions.json` (30~60건 — 페르소나: 30대 서울 직장인 1인 가구). 아래는 시작 구조 (전체는 동일 패턴 30건+ 채움):
```json
[
  {
    "txn_date": "2026-04-28",
    "txn_time": "12:34:00",
    "amount": "9500.00",
    "merchant_raw": "스타벅스 강남대로점",
    "card_last4": "1234",
    "category": "coffee",
    "is_canceled": false,
    "essential": false,
    "essential_reason": "사무실 커피머신 활용 가능 — 대체 가능"
  },
  {
    "txn_date": "2026-04-28",
    "txn_time": "19:42:00",
    "amount": "18200.00",
    "merchant_raw": "이태원 BBQ",
    "card_last4": "1234",
    "category": "snack_late",
    "is_canceled": false,
    "essential": false,
    "essential_reason": "야식 — 하루 식사 충분, 추가 지출"
  },
  {
    "txn_date": "2026-04-27",
    "txn_time": "12:11:00",
    "amount": "11000.00",
    "merchant_raw": "김밥천국 역삼점",
    "card_last4": "1234",
    "category": "lunch",
    "is_canceled": false,
    "essential": true,
    "essential_reason": "점심 — 출근일 1인 식사"
  },
  {
    "txn_date": "2026-04-26",
    "txn_time": null,
    "amount": "59800.00",
    "merchant_raw": "이마트 잠실점",
    "card_last4": "1234",
    "category": "groceries",
    "is_canceled": false,
    "essential": true,
    "essential_reason": "1주일치 식료품"
  },
  {
    "txn_date": "2026-04-25",
    "txn_time": "13:22:00",
    "amount": "5500.00",
    "merchant_raw": "이디야커피 선릉점",
    "card_last4": "1234",
    "category": "coffee",
    "is_canceled": false,
    "essential": false,
    "essential_reason": "오후 카페인 — 사무실 커피로 대체 가능"
  }
]
```
**구현자 메모:** 위 5건을 템플릿 삼아 30~60건으로 확장. 분포 예시: 점심(8~14건, 9000~14000원), 커피(6~12건, 4500~6500원), 야식(2~4건, 15000~25000원), 마트(2~4건, 30000~80000원), 회식(1~3건, 25000~80000원), 통신(1건, 50000~70000원), 교통 충전(1~2건, 50000원), 구독(1~2건, 9900~14900원). 가맹점명은 한국 대표 브랜드 + 지점명으로. 모든 essential_reason은 한 줄 코멘트.

- [ ] **Step 2:** Create empty `apps/api/app/seed/__init__.py`.

- [ ] **Step 3:** Create `apps/api/app/seed/kim_jichul.py`:
```python
import json
from pathlib import Path
from typing import Any


# repo root는 apps/api 기준 두 단계 위
_DATA_PATH = Path(__file__).resolve().parents[3] / "seed" / "kim_jichul" / "transactions.json"


def load_seed_transactions() -> list[dict[str, Any]]:
    """Load 김지출 seed transactions for guest mode. No DB."""
    return json.loads(_DATA_PATH.read_text(encoding="utf-8"))
```

- [ ] **Step 4:** Commit:
```bash
git add seed/kim_jichul/transactions.json apps/api/app/seed/__init__.py apps/api/app/seed/kim_jichul.py
git commit -m "feat(api): add 김지출 seed data and loader"
```

### Task 20: seed/routes.py GET /seed/transactions

**Files:**
- Create: `apps/api/app/seed/routes.py`
- Modify: `apps/api/app/main.py` (include router)
- Create: `apps/api/tests/seed/__init__.py` (empty)
- Create: `apps/api/tests/seed/test_seed_routes.py`

- [ ] **Step 1:** Create empty `apps/api/tests/seed/__init__.py`.

- [ ] **Step 2:** Create test `apps/api/tests/seed/test_seed_routes.py`:
```python
import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_seed_transactions_returns_list_no_auth():
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/seed/transactions")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) >= 30
    sample = body[0]
    for k in ("txn_date", "amount", "merchant_raw", "category", "essential_reason"):
        assert k in sample
```

- [ ] **Step 3:** Run (expect FAIL):
```bash
cd apps/api && uv run pytest tests/seed/test_seed_routes.py -v
```

- [ ] **Step 4:** Create `apps/api/app/seed/routes.py`:
```python
from fastapi import APIRouter

from app.seed.kim_jichul import load_seed_transactions


router = APIRouter(prefix="/seed", tags=["seed"])


@router.get("/transactions")
async def seed_transactions() -> list[dict]:
    return load_seed_transactions()
```

- [ ] **Step 5:** Add to `apps/api/app/main.py`:
```python
from app.seed.routes import router as seed_router
# ...
app.include_router(seed_router)
```

- [ ] **Step 6:** Run (expect PASS):
```bash
cd apps/api && uv run pytest tests/seed/test_seed_routes.py -v
```
Expected: 1 passed.

- [ ] **Step 7:** Commit:
```bash
git add apps/api/app/seed/routes.py apps/api/app/main.py apps/api/tests/seed/__init__.py apps/api/tests/seed/test_seed_routes.py
git commit -m "feat(api): add GET /seed/transactions for guest mode"
```

### Task 21: seed 라우트 응답 형태 정렬 (옵션 — JSON 그대로 반환)

이미 Task 20에서 list[dict] 그대로 반환. 별도 schema 불필요. **Skip — task 19/20에 통합됨.** Phase 4 완료.

---

## Phase 5: XLSX 파서 (10 tasks)

### Task 22: 익명화 픽스처 XLSX 작성

**Files:**
- Create: `apps/api/tests/fixtures/__init__.py` (empty)
- Create: `apps/api/tests/fixtures/build_fixture.py`
- Create: `apps/api/tests/fixtures/samsung-card-fixture.xlsx` (생성됨)

- [ ] **Step 1:** Create empty `apps/api/tests/fixtures/__init__.py`.

- [ ] **Step 2:** Create `apps/api/tests/fixtures/build_fixture.py`:
```python
"""Build the samsung-card fixture XLSX. Run once to generate fixture file.

Usage:
    cd apps/api && uv run python tests/fixtures/build_fixture.py
"""
from pathlib import Path
import openpyxl


def build() -> None:
    wb = openpyxl.Workbook()
    other = wb.active
    other.title = "전체이용내역"
    other["A1"] = "(unused for W1)"

    ws = wb.create_sheet("■ 국내이용내역")
    # 1~3행: 헤더 위 메타 (실제 명세서 모방)
    ws["A1"] = "삼성카드 국내이용내역"
    ws["A2"] = "조회기간: 2026-04-01 ~ 2026-04-30"
    # 4행: 헤더
    headers = [
        "카드번호", "본인가족구분", "승인일자", "승인시각", "가맹점명",
        "승인금액(원)", "일시불할부구분", "할부개월", "승인번호",
        "취소여부", "사용포인트", "결제일",
    ]
    for col_idx, h in enumerate(headers, start=1):
        ws.cell(row=4, column=col_idx, value=h)

    # 5행~: 데이터
    rows = [
        ["1234-5678-9012-3456", "본인", "2026-04-28", "12:34:00", "스타벅스 강남대로점",
         9500, "일시불", 0, "A20260428001", "N", 0, "2026-05-25"],
        ["1234-5678-9012-3456", "본인", "2026-04-28", "19:42:00", "이태원 BBQ",
         18200, "일시불", 0, "A20260428002", "N", 0, "2026-05-25"],
        ["1234-5678-9012-3456", "본인", "2026-04-27", "12:11:00", "김밥천국 역삼점",
         11000, "일시불", 0, "A20260427001", "N", 0, "2026-05-25"],
        ["1234-5678-9012-3456", "본인", "2026-04-26", None, "이마트 잠실점",
         59800, "할부", 3, "A20260426001", "N", 0, "2026-05-25"],
        ["1234-5678-9012-3456", "본인", "2026-04-25", "13:22:00", "이디야커피 선릉점",
         5500, "일시불", 0, "A20260425001", "N", 0, "2026-05-25"],
        ["1234-5678-9012-3456", "본인", "2026-04-24", "20:00:00", "교보문고 강남점",
         24000, "일시불", 0, "A20260424001", "Y", 0, "2026-05-25"],  # 취소
        ["1234-5678-9012-3456", "본인", "2026-04-23", "00:00:00", "정산수수료",
         500, "일시불", 0, "", "N", 0, "2026-05-25"],  # 승인번호 누락
    ]
    for r_idx, row in enumerate(rows, start=5):
        for c_idx, val in enumerate(row, start=1):
            ws.cell(row=r_idx, column=c_idx, value=val)

    out = Path(__file__).parent / "samsung-card-fixture.xlsx"
    wb.save(out)
    print(f"wrote {out}")


if __name__ == "__main__":
    build()
```

- [ ] **Step 3:** 실행해 fixture 생성:
```bash
cd apps/api && uv run python tests/fixtures/build_fixture.py
```
Expected: `wrote .../samsung-card-fixture.xlsx`. 파일 생성 확인.

- [ ] **Step 4:** Commit:
```bash
git add apps/api/tests/fixtures/__init__.py apps/api/tests/fixtures/build_fixture.py apps/api/tests/fixtures/samsung-card-fixture.xlsx
git commit -m "test(api): add anonymized samsung-card XLSX fixture and builder"
```

### Task 23: parsers/__init__.py + 인터페이스

**Files:**
- Create: `apps/api/app/parsers/__init__.py`

- [ ] **Step 1:** Create `apps/api/app/parsers/__init__.py`:
```python
from typing import Protocol


class ParseError(Exception):
    """Raised when input is unrecoverably malformed."""

    def __init__(self, code: str, **details):
        self.code = code
        self.details = details
        super().__init__(f"{code}: {details}")


SOURCE_TYPE_SAMSUNG_XLSX = "samsung_card_xlsx"
```

- [ ] **Step 2:** Commit:
```bash
git add apps/api/app/parsers/__init__.py
git commit -m "feat(api): add parsers package with ParseError + source_type constants"
```

### Task 24: parsers/samsung_card.py 시트 선택 (부분 매칭)

**Files:**
- Create: `apps/api/app/parsers/samsung_card.py`
- Create: `apps/api/tests/parsers/__init__.py` (empty)
- Create: `apps/api/tests/parsers/test_samsung_card_sheet.py`

- [ ] **Step 1:** Create empty `apps/api/tests/parsers/__init__.py`.

- [ ] **Step 2:** Create test `apps/api/tests/parsers/test_samsung_card_sheet.py`:
```python
from pathlib import Path
import pytest

from app.parsers import ParseError
from app.parsers.samsung_card import find_target_sheet
import openpyxl


FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "samsung-card-fixture.xlsx"


def test_find_target_sheet_partial_match():
    wb = openpyxl.load_workbook(FIXTURE, read_only=True, data_only=True)
    name = find_target_sheet(wb)
    assert "국내이용내역" in name


def test_find_target_sheet_raises_when_missing():
    wb = openpyxl.Workbook()
    wb.active.title = "Other"
    with pytest.raises(ParseError) as ei:
        find_target_sheet(wb)
    assert ei.value.code == "SHEET_NOT_FOUND"
```

- [ ] **Step 3:** Run (expect FAIL):
```bash
cd apps/api && uv run pytest tests/parsers/test_samsung_card_sheet.py -v
```

- [ ] **Step 4:** Create `apps/api/app/parsers/samsung_card.py`:
```python
import openpyxl

from app.parsers import ParseError


_TARGET_SHEET_KEYWORD = "국내이용내역"


def find_target_sheet(wb: openpyxl.Workbook) -> str:
    """Return first sheet name containing '국내이용내역'."""
    for name in wb.sheetnames:
        if _TARGET_SHEET_KEYWORD in name:
            return name
    raise ParseError("SHEET_NOT_FOUND", looking_for=_TARGET_SHEET_KEYWORD, found=list(wb.sheetnames))
```

- [ ] **Step 5:** Run (expect PASS):
```bash
cd apps/api && uv run pytest tests/parsers/test_samsung_card_sheet.py -v
```
Expected: 2 passed.

- [ ] **Step 6:** Commit:
```bash
git add apps/api/app/parsers/samsung_card.py apps/api/tests/parsers/__init__.py apps/api/tests/parsers/test_samsung_card_sheet.py
git commit -m "feat(parser): samsung_card find_target_sheet with partial match"
```

### Task 25: parsers/samsung_card.py 헤더 행 자동 감지

**Files:**
- Modify: `apps/api/app/parsers/samsung_card.py`
- Create: `apps/api/tests/parsers/test_samsung_card_header.py`

- [ ] **Step 1:** Create test `apps/api/tests/parsers/test_samsung_card_header.py`:
```python
from pathlib import Path
import openpyxl
import pytest

from app.parsers import ParseError
from app.parsers.samsung_card import find_target_sheet, find_header_row, REQUIRED_COLUMNS


FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "samsung-card-fixture.xlsx"


def test_find_header_row_returns_4():
    wb = openpyxl.load_workbook(FIXTURE, read_only=False, data_only=True)
    sheet_name = find_target_sheet(wb)
    ws = wb[sheet_name]
    row_idx, col_map = find_header_row(ws)
    assert row_idx == 4
    for c in REQUIRED_COLUMNS:
        assert c in col_map


def test_find_header_row_raises_when_required_missing():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws["A1"] = "엉뚱한 헤더"
    with pytest.raises(ParseError) as ei:
        find_header_row(ws)
    assert ei.value.code == "HEADER_NOT_FOUND"
```

- [ ] **Step 2:** Run (expect FAIL):
```bash
cd apps/api && uv run pytest tests/parsers/test_samsung_card_header.py -v
```

- [ ] **Step 3:** Add to `apps/api/app/parsers/samsung_card.py`:
```python
from typing import Iterable

from openpyxl.worksheet.worksheet import Worksheet


REQUIRED_COLUMNS = ["승인일자", "가맹점명", "승인금액(원)", "승인번호", "카드번호"]
ALL_KNOWN_COLUMNS = [
    "카드번호", "본인가족구분", "승인일자", "승인시각", "가맹점명",
    "승인금액(원)", "일시불할부구분", "할부개월", "승인번호",
    "취소여부", "사용포인트", "결제일",
]


def find_header_row(ws: Worksheet) -> tuple[int, dict[str, int]]:
    """Scan rows top-down; return (row_index, {column_name: column_index_1based}).

    A row qualifies if it contains all REQUIRED_COLUMNS as cell values.
    """
    max_scan = min(ws.max_row or 20, 20)
    for row_idx in range(1, max_scan + 1):
        col_map: dict[str, int] = {}
        for col_idx, cell in enumerate(ws[row_idx], start=1):
            if isinstance(cell.value, str):
                col_map[cell.value.strip()] = col_idx
        if all(req in col_map for req in REQUIRED_COLUMNS):
            return row_idx, col_map

    raise ParseError(
        "HEADER_NOT_FOUND",
        required=REQUIRED_COLUMNS,
        scanned_rows=max_scan,
    )
```

- [ ] **Step 4:** Run (expect PASS):
```bash
cd apps/api && uv run pytest tests/parsers/test_samsung_card_header.py -v
```
Expected: 2 passed.

- [ ] **Step 5:** Commit:
```bash
git add apps/api/app/parsers/samsung_card.py apps/api/tests/parsers/test_samsung_card_header.py
git commit -m "feat(parser): samsung_card find_header_row auto-detection"
```

### Task 26: 카드번호 마스킹 함수 + 테스트

**Files:**
- Modify: `apps/api/app/parsers/samsung_card.py` (add mask_pan)
- Create: `apps/api/tests/parsers/test_mask_pan.py`

- [ ] **Step 1:** Create test `apps/api/tests/parsers/test_mask_pan.py`:
```python
from app.parsers.samsung_card import mask_pan


def test_mask_pan_full():
    masked, last4 = mask_pan("1234-5678-9012-3456")
    assert masked == "****-****-****-3456"
    assert last4 == "3456"


def test_mask_pan_no_dashes():
    masked, last4 = mask_pan("1234567890123456")
    assert masked == "****-****-****-3456"
    assert last4 == "3456"


def test_mask_pan_short():
    masked, last4 = mask_pan("12")
    assert masked == "****-****-****-****"
    assert last4 == ""


def test_mask_pan_empty():
    masked, last4 = mask_pan("")
    assert masked == "****-****-****-****"
    assert last4 == ""
```

- [ ] **Step 2:** Run (expect FAIL):
```bash
cd apps/api && uv run pytest tests/parsers/test_mask_pan.py -v
```

- [ ] **Step 3:** Add to `apps/api/app/parsers/samsung_card.py`:
```python
import re


def mask_pan(pan: str | None) -> tuple[str, str]:
    """Return (masked_string, last4)."""
    if not pan:
        return "****-****-****-****", ""
    digits = re.sub(r"\D", "", pan)
    last4 = digits[-4:] if len(digits) >= 4 else ""
    masked = f"****-****-****-{last4}" if last4 else "****-****-****-****"
    return masked, last4
```

- [ ] **Step 4:** Run (expect PASS):
```bash
cd apps/api && uv run pytest tests/parsers/test_mask_pan.py -v
```
Expected: 4 passed.

- [ ] **Step 5:** Commit:
```bash
git add apps/api/app/parsers/samsung_card.py apps/api/tests/parsers/test_mask_pan.py
git commit -m "feat(parser): mask_pan helper for card number masking"
```

### Task 27: parsers/simple_rules.py (5~10 키워드 매핑)

**Files:**
- Create: `apps/api/app/parsers/simple_rules.py`
- Create: `apps/api/tests/parsers/test_simple_rules.py`

- [ ] **Step 1:** Create test `apps/api/tests/parsers/test_simple_rules.py`:
```python
from app.parsers.simple_rules import classify


def test_classify_starbucks_to_coffee():
    assert classify("스타벅스 강남대로점") == "coffee"


def test_classify_unknown_returns_unknown():
    assert classify("정체불명상점") == "unknown"


def test_classify_case_insensitive_emart():
    assert classify("EMART 잠실점") == "groceries"
```

- [ ] **Step 2:** Run (expect FAIL):
```bash
cd apps/api && uv run pytest tests/parsers/test_simple_rules.py -v
```

- [ ] **Step 3:** Create `apps/api/app/parsers/simple_rules.py`:
```python
"""Very simple keyword → category mapping for W1.

W2 will replace this with a proper rulebook + LLM fallback.
"""

# 순서 의미 있음 (위에서부터 첫 매칭). 모두 lowercase로 비교.
_RULES: list[tuple[tuple[str, ...], str]] = [
    (("스타벅스", "이디야", "투썸", "할리스", "starbucks", "coffee bean"), "coffee"),
    (("김밥천국", "맘스터치", "롯데리아", "맥도날드", "버거킹", "쉐이크쉑"), "lunch"),
    (("BBQ", "교촌", "굽네", "푸라닭", "야식", "치킨"), "snack_late"),
    (("이마트", "EMART", "홈플러스", "롯데마트", "코스트코"), "groceries"),
    (("CGV", "메가박스", "롯데시네마", "예스24", "교보문고", "올리브영"), "entertainment"),
    (("스마일클럽", "넷플릭스", "유튜브", "쿠팡플레이", "왓챠", "디즈니"), "subscription"),
    (("KT", "SKT", "LGU"), "telecom"),
    (("티머니", "T머니", "캐시비", "교통"), "transport"),
]


def classify(merchant_raw: str) -> str:
    if not merchant_raw:
        return "unknown"
    text = merchant_raw.lower()
    for keywords, category in _RULES:
        for kw in keywords:
            if kw.lower() in text:
                return category
    return "unknown"
```

- [ ] **Step 4:** Run (expect PASS):
```bash
cd apps/api && uv run pytest tests/parsers/test_simple_rules.py -v
```
Expected: 3 passed.

- [ ] **Step 5:** Commit:
```bash
git add apps/api/app/parsers/simple_rules.py apps/api/tests/parsers/test_simple_rules.py
git commit -m "feat(parser): simple_rules keyword → category mapping"
```

### Task 28: 행 → TransactionIn 매핑 (parse_row)

**Files:**
- Modify: `apps/api/app/parsers/samsung_card.py` (add parse_row, TransactionIn)
- Create: `apps/api/app/transactions/__init__.py` (empty)
- Create: `apps/api/app/transactions/schemas.py`
- Create: `apps/api/tests/parsers/test_parse_row.py`

- [ ] **Step 1:** Create empty `apps/api/app/transactions/__init__.py`.

- [ ] **Step 2:** Create `apps/api/app/transactions/schemas.py`:
```python
from datetime import date, time
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


class TransactionIn(BaseModel):
    """One parsed row, before DB insert."""
    txn_date: date
    txn_time: time | None = None
    amount: Decimal
    merchant_raw: str
    approval_no: str | None = None
    card_last4: str | None = None
    installment_months: int | None = None
    is_canceled: bool = False
    category: str = "unknown"
    raw_row: dict[str, Any]


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
    essential: bool | None
    essential_reason: str | None


class UploadResponse(BaseModel):
    uploaded: int
    skipped: int
    parse_errors: list[dict[str, Any]] = Field(default_factory=list)
```

- [ ] **Step 3:** Create test `apps/api/tests/parsers/test_parse_row.py`:
```python
from datetime import date, time
from decimal import Decimal

import pytest

from app.parsers.samsung_card import parse_row, ALL_KNOWN_COLUMNS


def _make_row(values: dict[str, object]) -> dict[str, object]:
    return {col: values.get(col) for col in ALL_KNOWN_COLUMNS}


def test_parse_row_basic_lump_sum():
    row = _make_row({
        "카드번호": "1234-5678-9012-3456",
        "본인가족구분": "본인",
        "승인일자": "2026-04-28",
        "승인시각": "12:34:00",
        "가맹점명": "스타벅스 강남대로점",
        "승인금액(원)": 9500,
        "일시불할부구분": "일시불",
        "할부개월": 0,
        "승인번호": "A20260428001",
        "취소여부": "N",
    })
    txn = parse_row(row)
    assert txn.txn_date == date(2026, 4, 28)
    assert txn.txn_time == time(12, 34, 0)
    assert txn.amount == Decimal("9500")
    assert txn.merchant_raw == "스타벅스 강남대로점"
    assert txn.approval_no == "A20260428001"
    assert txn.card_last4 == "3456"
    assert txn.installment_months == 0
    assert txn.is_canceled is False
    assert txn.category == "coffee"
    # raw_row의 카드번호는 마스킹된 형태
    assert txn.raw_row["카드번호"] == "****-****-****-3456"


def test_parse_row_installment():
    row = _make_row({
        "카드번호": "1234-5678-9012-3456",
        "승인일자": "2026-04-26",
        "가맹점명": "이마트 잠실점",
        "승인금액(원)": 59800,
        "일시불할부구분": "할부",
        "할부개월": 3,
        "승인번호": "A20260426001",
        "취소여부": "N",
    })
    txn = parse_row(row)
    assert txn.installment_months == 3


def test_parse_row_canceled():
    row = _make_row({
        "카드번호": "1234-5678-9012-3456",
        "승인일자": "2026-04-24",
        "가맹점명": "교보문고 강남점",
        "승인금액(원)": 24000,
        "승인번호": "A20260424001",
        "취소여부": "Y",
    })
    txn = parse_row(row)
    assert txn.is_canceled is True


def test_parse_row_missing_approval_no():
    row = _make_row({
        "카드번호": "1234-5678-9012-3456",
        "승인일자": "2026-04-23",
        "가맹점명": "정산수수료",
        "승인금액(원)": 500,
        "승인번호": "",
        "취소여부": "N",
    })
    txn = parse_row(row)
    assert txn.approval_no is None
```

- [ ] **Step 4:** Run (expect FAIL):
```bash
cd apps/api && uv run pytest tests/parsers/test_parse_row.py -v
```

- [ ] **Step 5:** Add to `apps/api/app/parsers/samsung_card.py`:
```python
from datetime import date as _date, datetime, time
from decimal import Decimal, InvalidOperation
from typing import Any

from app.parsers.simple_rules import classify
from app.transactions.schemas import TransactionIn


def _to_date(v: Any) -> _date:
    if isinstance(v, _date) and not isinstance(v, datetime):
        return v
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, str):
        return datetime.strptime(v, "%Y-%m-%d").date()
    raise ValueError(f"unparseable date: {v!r}")


def _to_time(v: Any) -> time | None:
    if v is None or v == "":
        return None
    if isinstance(v, time):
        return v
    if isinstance(v, datetime):
        return v.time()
    if isinstance(v, str):
        for fmt in ("%H:%M:%S", "%H:%M"):
            try:
                return datetime.strptime(v, fmt).time()
            except ValueError:
                continue
        return None
    return None


def _to_decimal(v: Any) -> Decimal:
    if isinstance(v, Decimal):
        return v
    if isinstance(v, (int, float)):
        return Decimal(str(v))
    if isinstance(v, str):
        cleaned = v.replace(",", "").strip()
        return Decimal(cleaned)
    raise ValueError(f"unparseable amount: {v!r}")


def _to_int(v: Any) -> int | None:
    if v in (None, ""):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v)
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        try:
            return int(s)
        except ValueError:
            return None
    return None


def parse_row(row: dict[str, Any]) -> TransactionIn:
    pan = row.get("카드번호") or ""
    masked, last4 = mask_pan(str(pan))

    raw_row = dict(row)
    raw_row["카드번호"] = masked

    approval_raw = row.get("승인번호")
    approval_no: str | None = None
    if approval_raw is not None:
        s = str(approval_raw).strip()
        approval_no = s if s else None

    merchant = str(row.get("가맹점명") or "").strip()
    is_canceled = str(row.get("취소여부") or "").strip().upper() == "Y"

    return TransactionIn(
        txn_date=_to_date(row.get("승인일자")),
        txn_time=_to_time(row.get("승인시각")),
        amount=_to_decimal(row.get("승인금액(원)")),
        merchant_raw=merchant,
        approval_no=approval_no,
        card_last4=last4 or None,
        installment_months=_to_int(row.get("할부개월")),
        is_canceled=is_canceled,
        category=classify(merchant),
        raw_row=raw_row,
    )
```

- [ ] **Step 6:** Run (expect PASS):
```bash
cd apps/api && uv run pytest tests/parsers/test_parse_row.py -v
```
Expected: 4 passed.

- [ ] **Step 7:** Commit:
```bash
git add apps/api/app/parsers/samsung_card.py apps/api/app/transactions/__init__.py apps/api/app/transactions/schemas.py apps/api/tests/parsers/test_parse_row.py
git commit -m "feat(parser): parse_row + TransactionIn schema"
```

### Task 29: parse_workbook (전체 파일 파싱)

**Files:**
- Modify: `apps/api/app/parsers/samsung_card.py` (add parse_workbook)
- Create: `apps/api/tests/parsers/test_parse_workbook.py`

- [ ] **Step 1:** Create test `apps/api/tests/parsers/test_parse_workbook.py`:
```python
from pathlib import Path
import pytest

from app.parsers import ParseError
from app.parsers.samsung_card import parse_workbook


FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "samsung-card-fixture.xlsx"


def test_parse_workbook_returns_all_data_rows():
    with FIXTURE.open("rb") as f:
        result = parse_workbook(f.read())
    assert result.rows_total == 7
    assert len(result.transactions) >= 6  # at least 6 valid rows
    assert result.parse_errors == [] or all(
        isinstance(e, dict) for e in result.parse_errors
    )


def test_parse_workbook_canceled_row_present():
    with FIXTURE.open("rb") as f:
        result = parse_workbook(f.read())
    canceled = [t for t in result.transactions if t.is_canceled]
    assert len(canceled) == 1
    assert canceled[0].merchant_raw.startswith("교보문고")


def test_parse_workbook_missing_approval_no_present():
    with FIXTURE.open("rb") as f:
        result = parse_workbook(f.read())
    no_approval = [t for t in result.transactions if t.approval_no is None]
    assert len(no_approval) == 1
    assert no_approval[0].merchant_raw == "정산수수료"


def test_parse_workbook_corrupt_bytes_raises():
    with pytest.raises(ParseError) as ei:
        parse_workbook(b"\x00not-an-xlsx")
    assert ei.value.code == "WORKBOOK_LOAD_FAILED"
```

- [ ] **Step 2:** Run (expect FAIL):
```bash
cd apps/api && uv run pytest tests/parsers/test_parse_workbook.py -v
```

- [ ] **Step 3:** Add to `apps/api/app/parsers/samsung_card.py`:
```python
import io
from dataclasses import dataclass, field


@dataclass
class ParseResult:
    rows_total: int
    transactions: list[TransactionIn] = field(default_factory=list)
    parse_errors: list[dict[str, Any]] = field(default_factory=list)


def parse_workbook(file_bytes: bytes) -> ParseResult:
    try:
        wb = openpyxl.load_workbook(
            io.BytesIO(file_bytes), read_only=False, data_only=True
        )
    except Exception as e:
        raise ParseError("WORKBOOK_LOAD_FAILED", reason=str(e))

    sheet_name = find_target_sheet(wb)
    ws = wb[sheet_name]
    header_row, col_map = find_header_row(ws)

    transactions: list[TransactionIn] = []
    errors: list[dict[str, Any]] = []
    data_rows = 0

    max_row = ws.max_row or header_row
    for row_idx in range(header_row + 1, max_row + 1):
        row_dict: dict[str, Any] = {}
        for col_name in ALL_KNOWN_COLUMNS:
            col_idx = col_map.get(col_name)
            row_dict[col_name] = ws.cell(row=row_idx, column=col_idx).value if col_idx else None

        # 빈 행/합계 행 skip: 핵심 필드(승인일자 + 가맹점명) 둘 다 없으면 무시
        if not row_dict.get("승인일자") and not row_dict.get("가맹점명"):
            continue

        data_rows += 1
        try:
            transactions.append(parse_row(row_dict))
        except Exception as e:
            errors.append({"row": row_idx, "error": str(e)})

    if data_rows == 0:
        raise ParseError("EMPTY_SHEET", sheet=sheet_name)

    return ParseResult(rows_total=data_rows, transactions=transactions, parse_errors=errors)
```

- [ ] **Step 4:** Run (expect PASS):
```bash
cd apps/api && uv run pytest tests/parsers/test_parse_workbook.py -v
```
Expected: 4 passed.

- [ ] **Step 5:** Commit:
```bash
git add apps/api/app/parsers/samsung_card.py apps/api/tests/parsers/test_parse_workbook.py
git commit -m "feat(parser): parse_workbook end-to-end with row error capture"
```

### Task 30: 파서 registry (`__init__.py` enhance)

**Files:**
- Modify: `apps/api/app/parsers/__init__.py`

- [ ] **Step 1:** Enhance `apps/api/app/parsers/__init__.py`:
```python
from typing import Callable

from app.parsers.samsung_card import parse_workbook as _samsung_parse, ParseResult


_REGISTRY: dict[str, Callable[[bytes], ParseResult]] = {
    SOURCE_TYPE_SAMSUNG_XLSX: _samsung_parse,
}


def get_parser(source_type: str) -> Callable[[bytes], ParseResult]:
    if source_type not in _REGISTRY:
        raise ParseError("UNSUPPORTED_SOURCE_TYPE", source_type=source_type)
    return _REGISTRY[source_type]
```
**주의:** 위 코드 추가 시 `__init__.py`의 모든 정의가 다음 순서로 위치해야 함:
```python
class ParseError(Exception):
    ...

SOURCE_TYPE_SAMSUNG_XLSX = "samsung_card_xlsx"

# 아래는 위에 있어야 import 가능
from typing import Callable
from app.parsers.samsung_card import parse_workbook as _samsung_parse, ParseResult

_REGISTRY: dict[str, Callable[[bytes], ParseResult]] = {
    SOURCE_TYPE_SAMSUNG_XLSX: _samsung_parse,
}

def get_parser(source_type: str) -> Callable[[bytes], ParseResult]:
    if source_type not in _REGISTRY:
        raise ParseError("UNSUPPORTED_SOURCE_TYPE", source_type=source_type)
    return _REGISTRY[source_type]
```
**주의:** 순환 import 회피 — `samsung_card.py`는 `app.parsers`에서 `ParseError`만 import, `__init__.py`는 `samsung_card` 함수 import. Python lazy import 순서상 OK이나 만약 import error 시 `samsung_card.py`에서 `ParseError`를 직접 정의하고 `__init__.py`로 re-export.

- [ ] **Step 2:** Smoke test:
```bash
cd apps/api && uv run python -c "from app.parsers import get_parser, SOURCE_TYPE_SAMSUNG_XLSX; print(get_parser(SOURCE_TYPE_SAMSUNG_XLSX))"
```
Expected: `<function parse_workbook at 0x...>`. import error 시 `samsung_card.py`에서 `from app.parsers import ParseError`를 `class ParseError(Exception): ...` 인라인으로 변경 후 `__init__.py`에서 re-export.

- [ ] **Step 3:** 전체 파서 테스트 한 번 더:
```bash
cd apps/api && uv run pytest tests/parsers/ -v
```
Expected: 모든 parser 테스트 PASS.

- [ ] **Step 4:** Commit:
```bash
git add apps/api/app/parsers/__init__.py
git commit -m "feat(parser): add parser registry"
```

### Task 31: 파서 통합 테스트 (전체 fixture round-trip)

**Files:**
- Create: `apps/api/tests/parsers/test_samsung_card_integration.py`

- [ ] **Step 1:** Create `apps/api/tests/parsers/test_samsung_card_integration.py`:
```python
from pathlib import Path

from app.parsers import get_parser, SOURCE_TYPE_SAMSUNG_XLSX


FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "samsung-card-fixture.xlsx"


def test_full_pipeline_via_registry():
    parser = get_parser(SOURCE_TYPE_SAMSUNG_XLSX)
    with FIXTURE.open("rb") as f:
        result = parser(f.read())

    # 6개의 정상 거래 + 1 정산 행 = 7
    assert result.rows_total == 7
    assert len(result.transactions) == 7

    # 카테고리 분포 검증
    categories = [t.category for t in result.transactions]
    assert "coffee" in categories  # 스타벅스, 이디야
    assert "groceries" in categories  # 이마트
    assert "lunch" in categories  # 김밥천국

    # 모든 카드번호 마스킹 확인
    for t in result.transactions:
        assert t.raw_row["카드번호"].startswith("****")
```

- [ ] **Step 2:** Run (expect PASS):
```bash
cd apps/api && uv run pytest tests/parsers/test_samsung_card_integration.py -v
```
Expected: 1 passed.

- [ ] **Step 3:** Commit:
```bash
git add apps/api/tests/parsers/test_samsung_card_integration.py
git commit -m "test(parser): integration test through registry"
```

---

## Phase 6: 거래 라우트 (6 tasks)

### Task 32: transactions/service.py — compute_dedup_hash

**Files:**
- Create: `apps/api/app/transactions/service.py`
- Create: `apps/api/tests/transactions/__init__.py` (empty)
- Create: `apps/api/tests/transactions/test_dedup_hash.py`

- [ ] **Step 1:** Create empty `apps/api/tests/transactions/__init__.py`.

- [ ] **Step 2:** Create test `apps/api/tests/transactions/test_dedup_hash.py`:
```python
from datetime import date
from decimal import Decimal
from uuid import UUID

from app.transactions.service import compute_dedup_hash


USER = UUID("00000000-0000-0000-0000-000000000001")


def test_dedup_uses_approval_when_present():
    h1 = compute_dedup_hash(USER, "samsung_card_xlsx", "A001",
                            fallback_date=date(2026, 4, 1),
                            fallback_amount=Decimal("100"),
                            fallback_merchant="X")
    h2 = compute_dedup_hash(USER, "samsung_card_xlsx", "A001",
                            fallback_date=date(2026, 4, 2),  # 다른 fallback
                            fallback_amount=Decimal("999"),
                            fallback_merchant="Y")
    assert h1 == h2  # approval_no가 있으면 fallback 무관


def test_dedup_falls_back_when_no_approval():
    h = compute_dedup_hash(USER, "samsung_card_xlsx", None,
                           fallback_date=date(2026, 4, 1),
                           fallback_amount=Decimal("100"),
                           fallback_merchant="X")
    assert isinstance(h, str)
    assert len(h) == 64  # sha256 hex


def test_dedup_different_users_get_different_hashes():
    other = UUID("00000000-0000-0000-0000-000000000002")
    h1 = compute_dedup_hash(USER, "samsung_card_xlsx", "A001",
                            fallback_date=date(2026, 4, 1),
                            fallback_amount=Decimal("100"),
                            fallback_merchant="X")
    h2 = compute_dedup_hash(other, "samsung_card_xlsx", "A001",
                            fallback_date=date(2026, 4, 1),
                            fallback_amount=Decimal("100"),
                            fallback_merchant="X")
    assert h1 != h2
```

- [ ] **Step 3:** Run (expect FAIL):
```bash
cd apps/api && uv run pytest tests/transactions/test_dedup_hash.py -v
```

- [ ] **Step 4:** Create `apps/api/app/transactions/service.py`:
```python
import hashlib
import json
from datetime import date
from decimal import Decimal
from uuid import UUID

import asyncpg

from app.transactions.schemas import TransactionIn


def compute_dedup_hash(
    user_id: UUID,
    source_type: str,
    approval_no: str | None,
    *,
    fallback_date: date,
    fallback_amount: Decimal,
    fallback_merchant: str,
) -> str:
    if approval_no:
        payload = f"{user_id}|{source_type}|approval:{approval_no}"
    else:
        payload = (
            f"{user_id}|{source_type}|fb:"
            f"{fallback_date.isoformat()}|{fallback_amount}|{fallback_merchant}"
        )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


async def insert_transactions(
    conn: asyncpg.Connection,
    user_id: UUID,
    source_file_id: UUID,
    source_type: str,
    txns: list[TransactionIn],
) -> tuple[int, int]:
    """Insert with ON CONFLICT DO NOTHING. Returns (inserted, skipped)."""
    inserted = 0
    skipped = 0
    for t in txns:
        dedup = compute_dedup_hash(
            user_id, source_type, t.approval_no,
            fallback_date=t.txn_date,
            fallback_amount=t.amount,
            fallback_merchant=t.merchant_raw,
        )
        result = await conn.fetchrow(
            """
            INSERT INTO transactions (
              user_id, source_file_id, source_type,
              txn_date, txn_time, amount, merchant_raw,
              approval_no, card_last4, installment_months,
              is_canceled, category, dedup_hash, raw_row
            ) VALUES (
              $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14::jsonb
            )
            ON CONFLICT (user_id, dedup_hash) DO NOTHING
            RETURNING id
            """,
            user_id, source_file_id, source_type,
            t.txn_date, t.txn_time, t.amount, t.merchant_raw,
            t.approval_no, t.card_last4, t.installment_months,
            t.is_canceled, t.category, dedup, json.dumps(t.raw_row, default=str, ensure_ascii=False),
        )
        if result is not None:
            inserted += 1
        else:
            skipped += 1
    return inserted, skipped
```

- [ ] **Step 5:** Run (expect PASS):
```bash
cd apps/api && uv run pytest tests/transactions/test_dedup_hash.py -v
```
Expected: 3 passed.

- [ ] **Step 6:** Commit:
```bash
git add apps/api/app/transactions/service.py apps/api/tests/transactions/__init__.py apps/api/tests/transactions/test_dedup_hash.py
git commit -m "feat(api): compute_dedup_hash + insert_transactions service"
```

### Task 33: transactions/routes.py — POST /transactions/upload

**Files:**
- Create: `apps/api/app/transactions/routes.py`
- Modify: `apps/api/app/main.py` (include router)

- [ ] **Step 1:** Create `apps/api/app/transactions/routes.py`:
```python
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.auth.deps import current_user_id
from app.db import acquire
from app.parsers import ParseError, get_parser, SOURCE_TYPE_SAMSUNG_XLSX
from app.transactions.schemas import UploadResponse
from app.transactions.service import insert_transactions


router = APIRouter(prefix="/transactions", tags=["transactions"])


_MAX_FILE_BYTES = 10 * 1024 * 1024  # 10MB
_ALLOWED_EXT = ".xlsx"
_ALLOWED_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@router.post("/upload", response_model=UploadResponse)
async def upload(
    file: UploadFile = File(...),
    user_id: UUID = Depends(current_user_id),
) -> UploadResponse:
    if not file.filename or not file.filename.lower().endswith(_ALLOWED_EXT):
        raise HTTPException(status_code=400, detail={"error": "INVALID_FILE_TYPE", "expected": _ALLOWED_EXT})
    if file.content_type and file.content_type != _ALLOWED_MIME:
        # MIME 미스매치는 경고만 (브라우저별 다름) — 확장자 통과면 진행
        pass

    file_bytes = await file.read()
    if len(file_bytes) > _MAX_FILE_BYTES:
        raise HTTPException(status_code=400, detail={"error": "FILE_TOO_LARGE"})

    source_type = SOURCE_TYPE_SAMSUNG_XLSX
    parser = get_parser(source_type)
    try:
        result = parser(file_bytes)
    except ParseError as e:
        raise HTTPException(status_code=400, detail={"error": e.code, **e.details})

    source_file_id = uuid4()
    async with acquire() as conn:
        inserted, skipped = await insert_transactions(
            conn, user_id, source_file_id, source_type, result.transactions
        )
        await conn.execute(
            """
            INSERT INTO source_files (id, user_id, source_type, filename, rows_total, rows_inserted, rows_skipped)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
            source_file_id, user_id, source_type, file.filename,
            result.rows_total, inserted, skipped,
        )

    return UploadResponse(uploaded=inserted, skipped=skipped, parse_errors=result.parse_errors)
```

- [ ] **Step 2:** Add to `apps/api/app/main.py`:
```python
from app.transactions.routes import router as transactions_router
# ...
app.include_router(transactions_router)
```

- [ ] **Step 3:** Smoke startup:
```bash
cd apps/api && uv run python -c "from app.main import app; print([r.path for r in app.routes])"
```
Expected: `/healthz`, `/auth/login`, `/auth/refresh`, `/auth/logout`, `/seed/transactions`, `/transactions/upload` 모두 보임.

- [ ] **Step 4:** Commit:
```bash
git add apps/api/app/transactions/routes.py apps/api/app/main.py
git commit -m "feat(api): POST /transactions/upload (parse + insert + source_files)"
```

### Task 34: GET /transactions

**Files:**
- Modify: `apps/api/app/transactions/routes.py` (add GET)

- [ ] **Step 1:** Add to `apps/api/app/transactions/routes.py`:
```python
from app.transactions.schemas import TransactionOut


@router.get("", response_model=list[TransactionOut])
async def list_transactions(user_id: UUID = Depends(current_user_id)) -> list[TransactionOut]:
    async with acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id::text, txn_date, txn_time, amount, merchant_raw, merchant_normalized,
                   approval_no, card_last4, installment_months, is_canceled,
                   category, essential, essential_reason
            FROM transactions
            WHERE user_id = $1
            ORDER BY txn_date DESC, txn_time DESC NULLS LAST, created_at DESC
            """,
            user_id,
        )
    return [TransactionOut(**dict(r)) for r in rows]
```

- [ ] **Step 2:** Commit:
```bash
git add apps/api/app/transactions/routes.py
git commit -m "feat(api): GET /transactions (per-user list)"
```

### Task 35: 통합 테스트 — 업로드 + 멱등 + 리스트

**Files:**
- Create: `apps/api/tests/transactions/test_upload_integration.py`

- [ ] **Step 1:** Create test `apps/api/tests/transactions/test_upload_integration.py`:
```python
from pathlib import Path
import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.password import hash_password
from app.auth.seed import ensure_admin_user
from app.settings import settings


FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "samsung-card-fixture.xlsx"


@pytest.fixture
async def auth_headers(test_db_pool, monkeypatch):
    pwd_hash = hash_password("hunter2")
    monkeypatch.setattr(settings, "admin_password_hash", pwd_hash)
    async with test_db_pool.acquire() as conn:
        await conn.execute("DELETE FROM users")
        await ensure_admin_user(conn)
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        login = await client.post("/auth/login",
                                  json={"email": settings.admin_email, "password": "hunter2"})
        token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}, app


@pytest.mark.asyncio
async def test_upload_then_list(auth_headers):
    headers, app = auth_headers
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with FIXTURE.open("rb") as f:
            files = {"file": ("samsung-card-fixture.xlsx", f.read(),
                              "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
            up = await client.post("/transactions/upload", headers=headers, files=files)
        assert up.status_code == 200
        body = up.json()
        assert body["uploaded"] >= 6
        assert body["skipped"] == 0

        lst = await client.get("/transactions", headers=headers)
        assert lst.status_code == 200
        assert len(lst.json()) >= 6


@pytest.mark.asyncio
async def test_upload_idempotent_on_second_run(auth_headers):
    headers, app = auth_headers
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with FIXTURE.open("rb") as f:
            data = f.read()
        files1 = {"file": ("samsung-card-fixture.xlsx", data,
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        first = await client.post("/transactions/upload", headers=headers, files=files1)
        assert first.json()["uploaded"] >= 6

        files2 = {"file": ("samsung-card-fixture.xlsx", data,
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        second = await client.post("/transactions/upload", headers=headers, files=files2)
        assert second.json()["uploaded"] == 0
        assert second.json()["skipped"] >= 6
```

- [ ] **Step 2:** Run (expect PASS):
```bash
cd apps/api && uv run pytest tests/transactions/test_upload_integration.py -v
```
Expected: 2 passed.

- [ ] **Step 3:** Commit:
```bash
git add apps/api/tests/transactions/test_upload_integration.py
git commit -m "test(api): integration test for upload + dedup + list"
```

### Task 36: 전체 백엔드 테스트 한 번 (회귀)

- [ ] **Step 1:** Run all api tests:
```bash
cd apps/api && uv run pytest -v
```
Expected: 모두 PASS. 실패 시 해당 task로 돌아가 수정.

- [ ] **Step 2:** ruff lint:
```bash
cd apps/api && uv run ruff check
```
Expected: 0 errors. 발견 시 `uv run ruff check --fix` 후 commit.

- [ ] **Step 3:** Commit (lint 수정이 있었다면):
```bash
git add -u
git commit -m "chore(api): apply ruff fixes"
```

### Task 37: Phase 6 마무리 (no-op task — Phase 7로 진행 신호)

- [ ] **Step 1:** Backend 백본 + 파서 + 거래 + 인증 모두 동작 확인됨. apps/web 시작.

---

## Phase 7: apps/web 백본 (4 tasks)

### Task 38: apps/web Vite + React + TS + Tailwind 셋업

**Files:**
- Create: `apps/web/package.json`
- Create: `apps/web/tsconfig.json`
- Create: `apps/web/tsconfig.node.json`
- Create: `apps/web/vite.config.ts`
- Create: `apps/web/index.html`
- Create: `apps/web/postcss.config.js`
- Create: `apps/web/tailwind.config.js`
- Create: `apps/web/src/main.tsx`
- Create: `apps/web/src/App.tsx`
- Create: `apps/web/src/index.css`

- [ ] **Step 1:** Create `apps/web/package.json`:
```json
{
  "name": "@spendlens/web",
  "private": true,
  "version": "0.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview --port 4173",
    "lint": "eslint . --ext ts,tsx",
    "test": "vitest run"
  },
  "dependencies": {
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "react-router-dom": "^6.26.0",
    "axios": "^1.7.0",
    "zustand": "^4.5.0"
  },
  "devDependencies": {
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.0",
    "typescript": "^5.5.0",
    "vite": "^5.4.0",
    "vitest": "^2.1.0",
    "@testing-library/react": "^16.0.0",
    "@testing-library/jest-dom": "^6.5.0",
    "jsdom": "^25.0.0",
    "tailwindcss": "^3.4.0",
    "postcss": "^8.4.0",
    "autoprefixer": "^10.4.0",
    "eslint": "^9.10.0",
    "@typescript-eslint/parser": "^8.6.0",
    "@typescript-eslint/eslint-plugin": "^8.6.0"
  }
}
```

- [ ] **Step 2:** Create `apps/web/tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "skipLibCheck": true,
    "esModuleInterop": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "useDefineForClassFields": true,
    "types": ["vitest/globals", "@testing-library/jest-dom"]
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

- [ ] **Step 3:** Create `apps/web/tsconfig.node.json`:
```json
{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true,
    "strict": true
  },
  "include": ["vite.config.ts"]
}
```

- [ ] **Step 4:** Create `apps/web/vite.config.ts`:
```ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
  },
});
```

- [ ] **Step 5:** Create `apps/web/index.html`:
```html
<!doctype html>
<html lang="ko">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>spendLens</title>
  </head>
  <body class="bg-zinc-950 text-zinc-100">
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 6:** Create `apps/web/postcss.config.js`:
```js
export default {
  plugins: { tailwindcss: {}, autoprefixer: {} },
};
```

- [ ] **Step 7:** Create `apps/web/tailwind.config.js`:
```js
/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: { extend: {} },
  plugins: [],
};
```

- [ ] **Step 8:** Create `apps/web/src/index.css`:
```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

- [ ] **Step 9:** Create `apps/web/src/main.tsx`:
```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import { App } from "./App";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
```

- [ ] **Step 10:** Create `apps/web/src/App.tsx` (placeholder, 다음 task에서 라우터 추가):
```tsx
export function App() {
  return <div className="p-8 text-2xl">spendLens</div>;
}
```

- [ ] **Step 11:** Create `apps/web/src/test/setup.ts`:
```ts
import "@testing-library/jest-dom";
```

- [ ] **Step 12:** Install:
```bash
pnpm install
```

- [ ] **Step 13:** Verify dev server starts (no errors):
```bash
pnpm --filter @spendlens/web dev
```
브라우저에서 http://localhost:5173 → "spendLens" 텍스트 보임. Ctrl-C로 종료.

- [ ] **Step 14:** Commit:
```bash
git add apps/web/
git commit -m "chore(web): scaffold Vite + React + TS + Tailwind"
```

### Task 39: 라우터 + Zustand store + axios 셋업

**Files:**
- Modify: `apps/web/src/App.tsx` (add Router)
- Create: `apps/web/src/lib/api.ts`
- Create: `apps/web/src/stores/auth.ts`
- Create: `apps/web/src/routes/index.tsx`
- Create: `apps/web/src/routes/guest.tsx`
- Create: `apps/web/src/routes/login.tsx`
- Create: `apps/web/src/routes/app.tsx`

- [ ] **Step 1:** Create `apps/web/src/stores/auth.ts`:
```ts
import { create } from "zustand";

type AuthState = {
  accessToken: string | null;
  setAccess: (t: string | null) => void;
  isAuthed: () => boolean;
};

export const useAuth = create<AuthState>((set, get) => ({
  accessToken: null,
  setAccess: (t) => set({ accessToken: t }),
  isAuthed: () => !!get().accessToken,
}));
```

- [ ] **Step 2:** Create `apps/web/src/lib/api.ts`:
```ts
import axios, { AxiosError } from "axios";
import { useAuth } from "../stores/auth";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

export const api = axios.create({
  baseURL: API_BASE,
  withCredentials: true,
});

api.interceptors.request.use((config) => {
  const token = useAuth.getState().accessToken;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

let refreshing: Promise<string | null> | null = null;

async function tryRefresh(): Promise<string | null> {
  if (!refreshing) {
    refreshing = (async () => {
      try {
        const resp = await axios.post(
          `${API_BASE}/auth/refresh`,
          {},
          { withCredentials: true },
        );
        const newToken = resp.data.access_token as string;
        useAuth.getState().setAccess(newToken);
        return newToken;
      } catch {
        useAuth.getState().setAccess(null);
        return null;
      } finally {
        refreshing = null;
      }
    })();
  }
  return refreshing;
}

api.interceptors.response.use(
  (r) => r,
  async (err: AxiosError) => {
    const original = err.config as any;
    if (err.response?.status === 401 && !original?._retried) {
      original._retried = true;
      const newToken = await tryRefresh();
      if (newToken) {
        original.headers.Authorization = `Bearer ${newToken}`;
        return api(original);
      }
    }
    return Promise.reject(err);
  },
);
```

- [ ] **Step 3:** Create `apps/web/src/routes/index.tsx`:
```tsx
import { Link } from "react-router-dom";

export function LandingPage() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center gap-6 p-8">
      <h1 className="text-5xl font-bold">spendLens</h1>
      <p className="text-zinc-400 text-center max-w-xl">
        광고 없는 가계부 · 데이터는 내 서버 · AI 코칭 (W2 예정)
      </p>
      <div className="flex gap-4">
        <Link to="/guest" className="px-6 py-3 bg-blue-600 rounded">▶ Guest Demo</Link>
        <Link to="/login" className="px-6 py-3 border border-zinc-600 rounded">로그인</Link>
      </div>
    </div>
  );
}
```

- [ ] **Step 4:** Create `apps/web/src/routes/guest.tsx`:
```tsx
import { useEffect, useState } from "react";
import { api } from "../lib/api";

type Txn = {
  txn_date: string;
  txn_time: string | null;
  amount: string;
  merchant_raw: string;
  category: string;
  essential: boolean | null;
  essential_reason: string | null;
};

export function GuestPage() {
  const [txns, setTxns] = useState<Txn[]>([]);
  useEffect(() => {
    api.get<Txn[]>("/seed/transactions").then((r) => setTxns(r.data));
  }, []);
  return (
    <div className="p-8 max-w-3xl mx-auto">
      <h2 className="text-2xl mb-4">Guest Demo · 김지출의 한 달</h2>
      <ul className="space-y-2">
        {txns.map((t, i) => (
          <li key={i} className="border border-zinc-800 rounded p-3">
            <div className="flex justify-between">
              <span>{t.txn_date} · {t.merchant_raw}</span>
              <span className="font-mono">{Number(t.amount).toLocaleString()}원</span>
            </div>
            <div className="text-xs text-zinc-500 mt-1">
              [{t.category}] {t.essential === false ? "비필수" : "필수"} · {t.essential_reason}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
```

- [ ] **Step 5:** Create `apps/web/src/routes/login.tsx`:
```tsx
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth } from "../stores/auth";

export function LoginPage() {
  const [email, setEmail] = useState("");
  const [pwd, setPwd] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const setAccess = useAuth((s) => s.setAccess);
  const nav = useNavigate();

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    try {
      const resp = await api.post("/auth/login", { email, password: pwd });
      setAccess(resp.data.access_token);
      nav("/app");
    } catch {
      setErr("이메일 또는 비번 불일치");
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-8">
      <form onSubmit={submit} className="w-full max-w-sm space-y-3">
        <h2 className="text-2xl mb-2">로그인</h2>
        <input className="w-full p-2 bg-zinc-900 border border-zinc-700 rounded"
               placeholder="이메일" value={email} onChange={(e) => setEmail(e.target.value)} />
        <input className="w-full p-2 bg-zinc-900 border border-zinc-700 rounded" type="password"
               placeholder="비번" value={pwd} onChange={(e) => setPwd(e.target.value)} />
        {err && <p className="text-red-400 text-sm">{err}</p>}
        <button className="w-full p-2 bg-blue-600 rounded">로그인</button>
      </form>
    </div>
  );
}
```

- [ ] **Step 6:** Create `apps/web/src/routes/app.tsx` (placeholder, ProtectedRoute는 다음 task):
```tsx
import { useEffect, useState, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth } from "../stores/auth";

type Txn = {
  id: string;
  txn_date: string;
  txn_time: string | null;
  amount: string;
  merchant_raw: string;
  card_last4: string | null;
  category: string;
  is_canceled: boolean;
  essential_reason: string | null;
};

export function AppPage() {
  const [txns, setTxns] = useState<Txn[]>([]);
  const [msg, setMsg] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const isAuthed = useAuth((s) => s.isAuthed());
  const nav = useNavigate();

  useEffect(() => {
    if (!isAuthed) {
      nav("/login");
      return;
    }
    refresh();
  }, [isAuthed]);

  async function refresh() {
    const r = await api.get<Txn[]>("/transactions");
    setTxns(r.data);
  }

  async function upload(file: File) {
    const fd = new FormData();
    fd.append("file", file);
    setMsg("업로드 중...");
    try {
      const r = await api.post<{ uploaded: number; skipped: number }>(
        "/transactions/upload", fd,
      );
      setMsg(`업로드 ${r.data.uploaded}건, dedup ${r.data.skipped}건`);
      await refresh();
    } catch (e: any) {
      setMsg(`실패: ${JSON.stringify(e.response?.data?.detail ?? e.message)}`);
    }
  }

  return (
    <div className="p-8 max-w-3xl mx-auto">
      <h2 className="text-2xl mb-4">My Transactions</h2>
      <input ref={fileInputRef} type="file" accept=".xlsx" className="hidden"
             onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])} />
      <button className="px-4 py-2 bg-blue-600 rounded mb-4"
              onClick={() => fileInputRef.current?.click()}>
        삼성카드 XLSX 업로드
      </button>
      {msg && <p className="mb-4 text-sm text-zinc-400">{msg}</p>}
      <ul className="space-y-2">
        {txns.map((t) => (
          <li key={t.id} className="border border-zinc-800 rounded p-3">
            <div className="flex justify-between">
              <span>
                {t.txn_date} · {t.merchant_raw}
                {t.is_canceled && <span className="ml-2 text-red-400 text-xs">[Canceled]</span>}
              </span>
              <span className="font-mono">{Number(t.amount).toLocaleString()}원</span>
            </div>
            <div className="text-xs text-zinc-500 mt-1">
              [{t.category}] · {t.card_last4 ? `****-${t.card_last4}` : ""}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
```

- [ ] **Step 7:** Replace `apps/web/src/App.tsx`:
```tsx
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { LandingPage } from "./routes";
import { GuestPage } from "./routes/guest";
import { LoginPage } from "./routes/login";
import { AppPage } from "./routes/app";

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/guest" element={<GuestPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/app" element={<AppPage />} />
      </Routes>
    </BrowserRouter>
  );
}
```

- [ ] **Step 8:** Verify dev server (백엔드도 켜야 함):
```bash
# 터미널 A
cd apps/api && uv run uvicorn app.main:app --reload --port 8000
# 터미널 B (.env에 VITE_API_BASE=http://localhost:8000)
pnpm --filter @spendlens/web dev
```
브라우저: http://localhost:5173 → 랜딩, /guest → 시드 데이터, /login → 폼.

- [ ] **Step 9:** Commit:
```bash
git add apps/web/
git commit -m "feat(web): add router, auth store, axios interceptor, 4 routes"
```

### Task 40: ProtectedRoute 컴포넌트 + UploadDropzone 컴포넌트

**Files:**
- Create: `apps/web/src/components/ProtectedRoute.tsx`
- Create: `apps/web/src/components/UploadDropzone.tsx`
- Modify: `apps/web/src/App.tsx` (use ProtectedRoute)
- Modify: `apps/web/src/routes/app.tsx` (use UploadDropzone)

- [ ] **Step 1:** Create `apps/web/src/components/ProtectedRoute.tsx`:
```tsx
import { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../stores/auth";

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const isAuthed = useAuth((s) => s.isAuthed());
  if (!isAuthed) return <Navigate to="/login" replace />;
  return <>{children}</>;
}
```

- [ ] **Step 2:** Create `apps/web/src/components/UploadDropzone.tsx`:
```tsx
import { useRef } from "react";

export function UploadDropzone({ onFile }: { onFile: (f: File) => void }) {
  const ref = useRef<HTMLInputElement>(null);
  return (
    <div
      className="border-2 border-dashed border-zinc-700 rounded p-8 text-center cursor-pointer hover:border-zinc-500"
      onClick={() => ref.current?.click()}
      onDragOver={(e) => e.preventDefault()}
      onDrop={(e) => {
        e.preventDefault();
        const f = e.dataTransfer.files[0];
        if (f) onFile(f);
      }}
    >
      <input
        ref={ref}
        type="file"
        accept=".xlsx"
        className="hidden"
        onChange={(e) => e.target.files?.[0] && onFile(e.target.files[0])}
      />
      <p className="text-zinc-400">.xlsx 파일을 드래그하거나 클릭해서 업로드</p>
    </div>
  );
}
```

- [ ] **Step 3:** Modify `apps/web/src/App.tsx` — wrap /app:
```tsx
import { ProtectedRoute } from "./components/ProtectedRoute";
// ...
<Route path="/app" element={<ProtectedRoute><AppPage /></ProtectedRoute>} />
```

- [ ] **Step 4:** Modify `apps/web/src/routes/app.tsx` — replace inline upload with UploadDropzone:
```tsx
import { UploadDropzone } from "../components/UploadDropzone";
// ... (제거: useRef, fileInputRef, hidden input, button)
// 화면 jsx에서 button 자리에 다음 추가:
<UploadDropzone onFile={upload} />
```
**구체 변경:** `app.tsx`의 jsx 부분에서 `<input ref={fileInputRef} ...>` + `<button onClick={...}>` 두 줄을 `<UploadDropzone onFile={upload} />` 한 줄로 교체. `useRef` import + `fileInputRef` 변수 제거.

- [ ] **Step 5:** Verify in browser: /app에 접근하면 비로그인 시 /login으로 리디렉트, 로그인 후 dropzone이 보임.

- [ ] **Step 6:** Commit:
```bash
git add apps/web/src/components/ apps/web/src/App.tsx apps/web/src/routes/app.tsx
git commit -m "feat(web): add ProtectedRoute + UploadDropzone components"
```

### Task 41: TransactionList 컴포넌트 추출 + vitest 단위 테스트

**Files:**
- Create: `apps/web/src/components/TransactionList.tsx`
- Modify: `apps/web/src/routes/app.tsx` (use TransactionList)
- Modify: `apps/web/src/routes/guest.tsx` (use TransactionList)
- Create: `apps/web/src/components/TransactionList.test.tsx`

- [ ] **Step 1:** Create `apps/web/src/components/TransactionList.tsx`:
```tsx
export type Txn = {
  id?: string;
  txn_date: string;
  txn_time: string | null;
  amount: string;
  merchant_raw: string;
  category: string;
  card_last4?: string | null;
  is_canceled?: boolean;
  essential?: boolean | null;
  essential_reason?: string | null;
};

export function TransactionList({ items }: { items: Txn[] }) {
  return (
    <ul className="space-y-2" data-testid="txn-list">
      {items.map((t, i) => (
        <li key={t.id ?? i} className="border border-zinc-800 rounded p-3">
          <div className="flex justify-between">
            <span>
              {t.txn_date} · {t.merchant_raw}
              {t.is_canceled && <span className="ml-2 text-red-400 text-xs">[Canceled]</span>}
            </span>
            <span className="font-mono">{Number(t.amount).toLocaleString()}원</span>
          </div>
          <div className="text-xs text-zinc-500 mt-1">
            [{t.category}]
            {t.card_last4 && ` · ****-${t.card_last4}`}
            {t.essential_reason && ` · ${t.essential_reason}`}
          </div>
        </li>
      ))}
    </ul>
  );
}
```

- [ ] **Step 2:** Modify `apps/web/src/routes/app.tsx` and `guest.tsx` to use `<TransactionList items={txns} />` 대신 inline `<ul>...</ul>`. import와 jsx 한 줄 교체.

- [ ] **Step 3:** Create `apps/web/src/components/TransactionList.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { TransactionList, Txn } from "./TransactionList";

describe("TransactionList", () => {
  it("renders empty list without error", () => {
    render(<TransactionList items={[]} />);
    expect(screen.getByTestId("txn-list").children.length).toBe(0);
  });

  it("renders merchant and amount", () => {
    const items: Txn[] = [{
      txn_date: "2026-04-28", txn_time: null, amount: "9500.00",
      merchant_raw: "스타벅스 강남대로점", category: "coffee",
    }];
    render(<TransactionList items={items} />);
    expect(screen.getByText(/스타벅스/)).toBeInTheDocument();
    expect(screen.getByText(/9,500원/)).toBeInTheDocument();
  });

  it("shows Canceled badge", () => {
    const items: Txn[] = [{
      txn_date: "2026-04-24", txn_time: null, amount: "24000",
      merchant_raw: "교보문고", category: "entertainment", is_canceled: true,
    }];
    render(<TransactionList items={items} />);
    expect(screen.getByText("[Canceled]")).toBeInTheDocument();
  });
});
```

- [ ] **Step 4:** Run vitest:
```bash
pnpm --filter @spendlens/web test
```
Expected: 3 passed.

- [ ] **Step 5:** Commit:
```bash
git add apps/web/src/components/TransactionList.tsx apps/web/src/components/TransactionList.test.tsx apps/web/src/routes/
git commit -m "feat(web): extract TransactionList + vitest unit tests"
```

---

## Phase 8: 인프라 (Lightsail 배포 준비) (6 tasks)

### Task 42: apps/api/Dockerfile (multi-stage with uv)

**Files:**
- Create: `apps/api/Dockerfile`
- Create: `apps/api/.dockerignore`

- [ ] **Step 1:** Create `apps/api/Dockerfile`:
```dockerfile
FROM ghcr.io/astral-sh/uv:0.5.0 AS uv

FROM python:3.12-slim AS base
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1
WORKDIR /app
COPY --from=uv /uv /usr/local/bin/uv

FROM base AS deps
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

FROM base AS runtime
COPY --from=deps /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./alembic.ini
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
```

- [ ] **Step 2:** Create `apps/api/.dockerignore`:
```
.venv
__pycache__
*.pyc
.pytest_cache
.ruff_cache
.mypy_cache
tests
.env
.env.*
```

- [ ] **Step 3:** Local build:
```bash
cd apps/api && docker build -t spendlens-api:dev .
```
Expected: 빌드 성공, 이미지 ~200~300MB.

- [ ] **Step 4:** Commit:
```bash
git add apps/api/Dockerfile apps/api/.dockerignore
git commit -m "chore(api): add multi-stage Dockerfile with uv"
```

### Task 43: infra/Caddyfile

**Files:**
- Create: `infra/Caddyfile`

- [ ] **Step 1:** Create `infra/Caddyfile`:
```Caddyfile
api.spendlens.suim-app.store {
    reverse_proxy api:8000
    encode gzip zstd
    log {
        output file /var/log/caddy/access.log
        format json
    }
    request_body {
        max_size 10MB
    }
}
```

- [ ] **Step 2:** Commit:
```bash
git add infra/Caddyfile
git commit -m "chore(infra): add Caddyfile for api subdomain with TLS auto"
```

### Task 44: infra/docker-compose.prod.yml

**Files:**
- Create: `infra/docker-compose.prod.yml`

- [ ] **Step 1:** Create `infra/docker-compose.prod.yml`:
```yaml
services:
  api:
    image: ghcr.io/${GHCR_USER}/spendlens-api:latest
    restart: unless-stopped
    env_file:
      - /opt/spendlens/.env
    networks:
      - spendlens

  caddy:
    image: caddy:2-alpine
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - /opt/spendlens/Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
      - caddy_config:/config
      - caddy_logs:/var/log/caddy
    networks:
      - spendlens

networks:
  spendlens:

volumes:
  caddy_data:
  caddy_config:
  caddy_logs:
```

- [ ] **Step 2:** Commit:
```bash
git add infra/docker-compose.prod.yml
git commit -m "chore(infra): add production docker-compose (api + caddy)"
```

### Task 45: infra/docker-compose.yml (로컬 개발용)

**Files:**
- Create: `infra/docker-compose.yml`

- [ ] **Step 1:** Create `infra/docker-compose.yml`:
```yaml
services:
  postgres-test:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: spendlens_test
    ports:
      - "5433:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 3s
      retries: 5
```

- [ ] **Step 2:** 로컬 테스트 DB 띄우기:
```bash
cd infra && docker compose up -d postgres-test
```
대기 후:
```bash
cd apps/api && DATABASE_URL=postgresql://postgres:postgres@localhost:5433/spendlens_test uv run alembic upgrade head
cd apps/api && uv run pytest -v
```
Expected: 모든 테스트 PASS.

- [ ] **Step 3:** Commit:
```bash
git add infra/docker-compose.yml
git commit -m "chore(infra): add local docker-compose with postgres-test"
```

### Task 46: infra/lightsail-bootstrap.sh

**Files:**
- Create: `infra/lightsail-bootstrap.sh`

- [ ] **Step 1:** Create `infra/lightsail-bootstrap.sh`:
```bash
#!/usr/bin/env bash
# Run once on a fresh Lightsail Ubuntu 22.04 instance.
# Prereq: SSH'd in as ubuntu user.
set -euo pipefail

echo "==> Updating apt"
sudo apt-get update -y
sudo apt-get upgrade -y

echo "==> Installing docker"
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker ubuntu

echo "==> Installing docker compose plugin (already in get.docker.com but verify)"
docker compose version

echo "==> Creating /opt/spendlens"
sudo mkdir -p /opt/spendlens
sudo chown ubuntu:ubuntu /opt/spendlens

echo "==> Done. Now:"
echo "  1) scp Caddyfile and docker-compose.prod.yml to /opt/spendlens/"
echo "  2) Create /opt/spendlens/.env with DATABASE_URL, ADMIN_*, JWT_*, WEB_ORIGIN"
echo "  3) docker login ghcr.io  (use GHCR_TOKEN PAT)"
echo "  4) cd /opt/spendlens && docker compose -f docker-compose.prod.yml up -d"
echo "  5) Log out and back in for docker group to take effect"
```

- [ ] **Step 2:** Make executable:
```bash
chmod +x infra/lightsail-bootstrap.sh
```

- [ ] **Step 3:** Commit:
```bash
git add infra/lightsail-bootstrap.sh
git commit -m "chore(infra): add lightsail-bootstrap.sh for first-time provisioning"
```

### Task 47: infra/README.md

**Files:**
- Create: `infra/README.md`

- [ ] **Step 1:** Create `infra/README.md`:
```markdown
# Infra

## Local Dev
\`\`\`bash
cd infra && docker compose up -d postgres-test
cd apps/api && uv sync && uv run alembic upgrade head && uv run uvicorn app.main:app --reload
cd apps/web && pnpm dev
\`\`\`

## Production (Lightsail)

### Initial provisioning (once per instance)
1. SSH into Lightsail instance
2. \`bash <(curl -sSL https://raw.githubusercontent.com/acceptha/spendLens/main/infra/lightsail-bootstrap.sh)\`
   (또는 scp 후 실행)
3. scp \`Caddyfile\` and \`docker-compose.prod.yml\` to \`/opt/spendlens/\`
4. Create \`/opt/spendlens/.env\` (chmod 600) with:
   \`\`\`
   DATABASE_URL=...
   ADMIN_EMAIL=...
   ADMIN_PASSWORD_HASH=...
   JWT_SECRET=...
   WEB_ORIGIN=https://spendlens.suim-app.store
   GHCR_USER=<your-github-username>
   \`\`\`
5. \`docker login ghcr.io\` with PAT
6. \`cd /opt/spendlens && docker compose -f docker-compose.prod.yml up -d\`

### Ongoing deploy
- main push → GitHub Actions: build, push GHCR, ssh \`docker compose pull && up -d\`

### Troubleshooting
- \`docker compose -f /opt/spendlens/docker-compose.prod.yml logs -f api\`
- \`docker compose -f /opt/spendlens/docker-compose.prod.yml logs -f caddy\`
- TLS 발급 실패 시 80/443 방화벽 + DNS 전파 확인
```

- [ ] **Step 2:** Commit:
```bash
git add infra/README.md
git commit -m "docs(infra): add infra README"
```

---

## Phase 9: CI (3 tasks)

### Task 48: .github/workflows/ci.yml — web 매트릭스

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1:** Create `.github/workflows/ci.yml`:
```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  web:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v4
        with:
          version: 9
      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: pnpm
      - run: pnpm install --frozen-lockfile
      - run: pnpm -r --filter @spendlens/web build
      - run: pnpm -r --filter @spendlens/web test
```

- [ ] **Step 2:** Commit:
```bash
git add .github/workflows/ci.yml
git commit -m "ci: add web build + test workflow"
```

### Task 49: ci.yml — api 매트릭스 추가 (Postgres service)

**Files:**
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1:** Add `api` job to `ci.yml`:
```yaml
  api:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: spendlens_test
        ports:
          - 5433:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 5s
          --health-timeout 3s
          --health-retries 5
    env:
      DATABASE_URL: postgresql://postgres:postgres@localhost:5433/spendlens_test
      ADMIN_EMAIL: admin@example.com
      ADMIN_PASSWORD_HASH: $argon2id$v=19$m=65536,t=3,p=4$placeholder
      JWT_SECRET: ci_secret_64chars_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
      WEB_ORIGIN: http://localhost:5173
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
        with:
          version: "0.5.0"
      - run: uv python install 3.12
        working-directory: apps/api
      - run: uv sync --frozen
        working-directory: apps/api
      - run: uv run alembic upgrade head
        working-directory: apps/api
      - run: uv run ruff check
        working-directory: apps/api
      - run: uv run pytest -v
        working-directory: apps/api
```

- [ ] **Step 2:** Commit:
```bash
git add .github/workflows/ci.yml
git commit -m "ci: add api lint + test job with postgres service"
```

### Task 50: CI 검증 (브랜치 push 후 확인)

- [ ] **Step 1:** Push to GitHub:
```bash
git push origin main
```
(첫 push면 `git remote add origin git@github.com:acceptha/spendLens.git` 또는 `https://...` 한 번 한 후)

- [ ] **Step 2:** GitHub Actions 탭에서 CI 잡 확인. 두 잡(web/api) 모두 ✅면 PASS.

- [ ] **Step 3:** 실패 시 로그 확인 후 수정 → 새 commit → push.

---

## Phase 10: 배포 워크플로 (2 tasks)

### Task 51: deploy-api.yml — GHCR build + push + SSH deploy

**Files:**
- Create: `.github/workflows/deploy-api.yml`

- [ ] **Step 1:** Create `.github/workflows/deploy-api.yml`:
```yaml
name: Deploy API

on:
  push:
    branches: [main]
    paths:
      - "apps/api/**"
      - ".github/workflows/deploy-api.yml"
      - "infra/Caddyfile"
      - "infra/docker-compose.prod.yml"
  workflow_dispatch:

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
    steps:
      - uses: actions/checkout@v4

      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - uses: docker/setup-buildx-action@v3

      - uses: docker/build-push-action@v5
        with:
          context: ./apps/api
          push: true
          tags: |
            ghcr.io/${{ github.repository_owner }}/spendlens-api:latest
            ghcr.io/${{ github.repository_owner }}/spendlens-api:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Copy Caddyfile and compose to Lightsail
        uses: appleboy/scp-action@v0.1.7
        with:
          host: ${{ secrets.LIGHTSAIL_HOST }}
          username: ubuntu
          key: ${{ secrets.LIGHTSAIL_SSH_KEY }}
          source: "infra/Caddyfile,infra/docker-compose.prod.yml"
          target: "/opt/spendlens/"
          strip_components: 1

      - name: SSH deploy
        uses: appleboy/ssh-action@v1.0.3
        with:
          host: ${{ secrets.LIGHTSAIL_HOST }}
          username: ubuntu
          key: ${{ secrets.LIGHTSAIL_SSH_KEY }}
          script: |
            cd /opt/spendlens
            export GHCR_USER=${{ github.repository_owner }}
            docker compose -f docker-compose.prod.yml pull api
            docker compose -f docker-compose.prod.yml up -d
            docker image prune -f
```

- [ ] **Step 2:** Commit:
```bash
git add .github/workflows/deploy-api.yml
git commit -m "ci: add deploy-api workflow (GHCR build + SSH deploy to Lightsail)"
```

### Task 52: GitHub Secrets 등록

- [ ] **Step 1:** GitHub repo → Settings → Secrets and variables → Actions → "New repository secret":
   - `LIGHTSAIL_HOST` = Lightsail 정적 IP (Task 00-B에서 보관)
   - `LIGHTSAIL_SSH_KEY` = PEM 키 전체 내용 (BEGIN/END 라인 포함)
   - (`GITHUB_TOKEN`은 자동 제공)
- [ ] **Step 2:** 위 secrets가 deploy-api.yml에서 참조되는지 확인 (`secrets.LIGHTSAIL_HOST` 등).

---

## Phase 11: 인프라 프로비저닝 (수동) (8 tasks)

### Task 53: Lightsail bootstrap 실행

- [ ] **Step 1:** SSH:
```bash
ssh -i ~/.ssh/lightsail-spendlens.pem ubuntu@<LIGHTSAIL_HOST>
```
- [ ] **Step 2:** 로컬에서 bootstrap 스크립트 scp:
```bash
scp -i ~/.ssh/lightsail-spendlens.pem infra/lightsail-bootstrap.sh ubuntu@<LIGHTSAIL_HOST>:~/
```
- [ ] **Step 3:** 인스턴스에서 실행:
```bash
bash ~/lightsail-bootstrap.sh
```
- [ ] **Step 4:** 로그아웃 후 재 SSH (docker 그룹 적용):
```bash
exit
ssh -i ~/.ssh/lightsail-spendlens.pem ubuntu@<LIGHTSAIL_HOST>
docker --version
```

### Task 54: GHCR 로그인 (Lightsail에서)

- [ ] **Step 1:** PAT로 docker login (인스턴스 안에서):
```bash
echo "<GHCR_TOKEN>" | docker login ghcr.io -u <github-username> --password-stdin
```
Expected: `Login Succeeded`.

### Task 55: .env 작성 (Lightsail)

- [ ] **Step 1:** 로컬에서 비번 해시 생성:
```bash
cd apps/api && uv run python ../../scripts/hash_password.py
# 비번 입력 → $argon2id$... 출력 복사
```
- [ ] **Step 2:** JWT_SECRET 생성:
```bash
openssl rand -base64 64 | tr -d '\n'
```
- [ ] **Step 3:** Lightsail 안에서 `/opt/spendlens/.env` 작성:
```bash
sudo nano /opt/spendlens/.env
```
내용:
```bash
DATABASE_URL=postgresql://postgres:<supabase_pwd>@db.<ref>.supabase.co:5432/postgres
ADMIN_EMAIL=siha@ssrinc.co.kr
ADMIN_PASSWORD_HASH=$argon2id$v=19$m=65536,t=3,p=4$<...>
JWT_SECRET=<openssl 결과>
JWT_ACCESS_TTL_MINUTES=15
JWT_REFRESH_TTL_DAYS=7
WEB_ORIGIN=https://spendlens.suim-app.store
LOG_LEVEL=INFO
GHCR_USER=<github-username>
```
- [ ] **Step 4:** 권한 설정:
```bash
sudo chmod 600 /opt/spendlens/.env
sudo chown ubuntu:ubuntu /opt/spendlens/.env
```

### Task 56: Caddyfile + compose 파일 수동 배치 (첫 1회)

deploy-api.yml의 scp 단계가 자동 처리하지만 첫 배포 전에 수동으로 두면 안전:
- [ ] **Step 1:** 로컬에서 scp:
```bash
scp -i ~/.ssh/lightsail-spendlens.pem infra/Caddyfile infra/docker-compose.prod.yml ubuntu@<LIGHTSAIL_HOST>:/opt/spendlens/
```

### Task 57: Vercel 프로젝트 import

- [ ] **Step 1:** [vercel.com](https://vercel.com) → New Project → spendLens 레포 import
- [ ] **Step 2:** Framework preset = Vite, Root directory = `apps/web`
- [ ] **Step 3:** Environment Variables: `VITE_API_BASE` = `https://api.spendlens.suim-app.store`
- [ ] **Step 4:** Build settings:
   - Install command: `pnpm install --filter @spendlens/web...`
   - Build command: `pnpm --filter @spendlens/web build`
   - Output directory: `dist`
- [ ] **Step 5:** Deploy. 첫 배포는 vercel.app 서브도메인. 다음 task에서 커스텀 도메인.

### Task 58: Vercel 커스텀 도메인 연결

- [ ] **Step 1:** Vercel project → Settings → Domains → Add `spendlens.suim-app.store`
- [ ] **Step 2:** 가비아 DNS에 `cname.vercel-dns.com` 매핑된 CNAME 레코드가 이미 있는지 확인 (Task 00-C)
- [ ] **Step 3:** Vercel UI가 "Valid configuration" 표시할 때까지 대기 (5분~몇 시간)
- [ ] **Step 4:** https://spendlens.suim-app.store 접속 → 랜딩 페이지 보임 확인

### Task 59: 첫 API 배포 (수동 또는 push)

옵션 A — 수동:
- [ ] **Step 1:** Lightsail에서:
```bash
cd /opt/spendlens
docker login ghcr.io  # 이미 했으면 skip
# 첫 이미지 build는 GitHub Actions이 만들어줌. 즉 main push 먼저 필요.
```

옵션 B — main push로 자동 (권장):
- [ ] **Step 1:** 모든 변경 push:
```bash
git push origin main
```
- [ ] **Step 2:** GitHub Actions → Deploy API 워크플로 실행 확인. 빌드 + push + ssh deploy까지 ✅.
- [ ] **Step 3:** Lightsail에서 컨테이너 확인:
```bash
docker ps
docker compose -f /opt/spendlens/docker-compose.prod.yml logs -f api
```

### Task 60: Caddy TLS 발급 확인

- [ ] **Step 1:** Caddy 로그:
```bash
docker compose -f /opt/spendlens/docker-compose.prod.yml logs -f caddy
```
"certificate obtained" 또는 유사 메시지 보일 때까지 대기 (최초 30초~몇 분).
- [ ] **Step 2:** 외부에서:
```bash
curl -i https://api.spendlens.suim-app.store/healthz
```
Expected: `HTTP/2 200`, body `{"status":"ok"}`.

---

## Phase 12: 첫 배포 검수 + README 마무리 (6 tasks)

### Task 61: /healthz 외부 응답 확인

- [ ] **Step 1:**
```bash
curl -s https://api.spendlens.suim-app.store/healthz | jq
```
Expected: `{"status": "ok"}`.

### Task 62: /guest 외부 동작 확인

- [ ] **Step 1:** 브라우저로 https://spendlens.suim-app.store/guest 접속
- [ ] **Step 2:** 거래 30~60건이 시드 페르소나·카테고리·essential_reason 코멘트와 함께 보이는지 확인
- [ ] **Step 3:** 직접 API 호출도 동작 확인:
```bash
curl -s https://api.spendlens.suim-app.store/seed/transactions | jq '. | length'
```
Expected: 30 이상.

### Task 63: /login → /app → 업로드 flow 외부 동작 확인

- [ ] **Step 1:** 브라우저로 https://spendlens.suim-app.store/login → 본인 이메일/비번 입력 → /app 진입
- [ ] **Step 2:** UploadDropzone에 본인 `samsung-card-sample.xlsx` 드래그 → "업로드 N건, dedup 0건" 메시지
- [ ] **Step 3:** 거래 리스트 표시 확인. 카드번호 `****-****-****-NNNN` 마스킹 확인.

### Task 64: dedup 멱등 외부 검증

- [ ] **Step 1:** 같은 XLSX 다시 업로드 → "업로드 0건, dedup N건" 메시지

### Task 65: README 마무리

**Files:**
- Modify: `README.md`

- [ ] **Step 1:** Modify `README.md` — Live Demo URL을 진짜 URL로 교체, Status를 "W1 complete"로:
```markdown
# spendLens

> 광고 없는 가계부 · AI 코칭 (W2 예정) · 데이터는 내 서버

## Live Demo
- **Web**: https://spendlens.suim-app.store
- **Guest Mode (5초 데모)**: https://spendlens.suim-app.store/guest
- **API healthz**: https://api.spendlens.suim-app.store/healthz

## Status
W1 ✅ shipped — skeleton + 삼성카드 XLSX 파서 + 첫 배포.
W2 next — LLM (Claude Haiku) + Redis 캐시 + 카테고리 룰북 + 우리/하나 파서 + 회원가입.

## What you can try right now
- `/guest` — 회원가입 없이 시드 데이터로 가계부 데모
- 본인 모드는 ENV seed 단일 사용자 (Self-host 가능)

## Tech Stack
- Frontend: React + Vite + TypeScript + Tailwind + Zustand (Vercel)
- Backend: FastAPI + pandas + openpyxl + asyncpg (AWS Lightsail + Docker Compose + Caddy)
- DB: Supabase Postgres (Tokyo)
- CI/CD: GitHub Actions → GHCR → SSH deploy
- AI: Claude Haiku (W2 예정)

## Self-host
\`\`\`bash
git clone https://github.com/acceptha/spendLens
cd spendLens
cp .env.example .env  # 값 채움
docker compose -f infra/docker-compose.prod.yml up -d
\`\`\`

## Spec & Plan
- W1 spec: `docs/superpowers/specs/2026-04-29-w1-skeleton-and-samsung-xlsx-parser-design.md`
- W1 plan: `docs/superpowers/plans/2026-04-30-w1-skeleton-and-samsung-xlsx-parser.md`
```

- [ ] **Step 2:** Commit + push:
```bash
git add README.md
git commit -m "docs: mark W1 shipped, add live demo links"
git push origin main
```

### Task 66: W1 회고 메모 (선택)

**Files:**
- Create: `docs/retros/w1.md`

- [ ] **Step 1:** Create `docs/retros/w1.md`:
```markdown
# W1 Retro

## Shipped
- ...

## What worked
- ...

## What hurt
- ...

## Carry into W2
- ...
```

- [ ] **Step 2:** 본인이 채운 후 commit:
```bash
git add docs/retros/w1.md
git commit -m "docs: add W1 retro skeleton"
```

---

## Self-Review

> 이 섹션은 plan 작성자(나)가 spec과 대조해 점검한 결과. 실행자는 무시.

### 1. Spec coverage check

| Spec 항목 | 구현 task |
|---|---|
| §2 Done #1 (Web 200) | Task 57, 58, 62 |
| §2 Done #2 (API healthz) | Task 09, 60, 61 |
| §2 Done #3 (/guest 시드) | Task 19, 20, 38, 39, 62 |
| §2 Done #4 (/login JWT) | Task 11, 12, 14, 15 |
| §2 Done #5 (/app upload → 거래 리스트) | Task 28, 33, 34, 38, 39, 40, 41, 63 |
| §2 Done #6 (sample.xlsx 무결 파싱) | Task 22, 24, 25, 28, 29, 31 |
| §2 Done #7 (재업로드 dedup 멱등) | Task 32, 35, 64 |
| §2 Done #8 (PAN 마스킹) | Task 26, 28 |
| §2 Done #9 (CI/CD main push 자동 배포) | Task 48, 49, 51, 52, 59 |
| §2 Done #10 (Vercel 자동 배포) | Task 57, 58 |
| §2 Done #11 (README Live Demo) | Task 03, 65 |
| §3 Decisions (모든 11개) | Phase 1~11 전반 |
| §4 Architecture (Vercel + Lightsail + Caddy + Supabase) | Phase 8, 11 |
| §5 디렉토리 구조 (모든 디렉토리) | Phase 1~10 |
| §6 Data Model (4 테이블) | Task 08 |
| §7-A Data Flow (본인 모드) | Task 33, 34 |
| §7-B Data Flow (게스트) | Task 19, 20 |
| §7-C 토큰 갱신 | Task 16, 39 |
| §7-D dedup_hash | Task 32 |
| §7-E 카드번호 마스킹 | Task 26, 28 |
| §8 Error Handling (모두) | Task 24, 25, 28, 29, 33 |
| §9 Out of Scope | 명시적으로 plan에서 제외됨 ✓ |
| §10 Testing 전략 | Task 10, 11, 12, 14, 15, 16, 17, 18, 24, 25, 28, 29, 31, 32, 35, 41, 49 |
| §11 ENV 키 명세 | Task 02, 55 |
| §12 CI/CD 워크플로 | Task 48, 49, 51 |
| §13 검수 시나리오 | Task 61, 62, 63, 64 |
| §14 Open Items | implementation 단계 가이드로 해소: #1 Task 22 (fixture), #2 Task 00-B, #3 Task 00-E + 54, #4 Task 00-C |

**Gaps**: 발견 안 됨. Spec 모든 요구가 task로 매핑됨.

### 2. Placeholder scan
- "TBD"/"TODO" 검색: README의 첫 placeholder("TBD")는 Task 65에서 실제 URL로 교체됨. 그 외 본문에는 placeholder 없음.
- 모든 step에 코드/명령 박힘. "implement later", "fill in details" 없음.
- "Similar to Task N" 표현 없음 (각 task가 self-contained).

### 3. Type / signature consistency
- `TransactionIn` (Task 28에서 정의) — Task 32, 33에서 동일 import 경로 사용 ✓
- `ParseResult` (Task 29에서 정의) — Task 30, 33에서 동일 사용 ✓
- `ParseError` (Task 23에서 정의) — Task 24, 25, 29, 33에서 동일 ✓
- `compute_dedup_hash` (Task 32에서 정의) — `insert_transactions`에서 호출 ✓
- `current_user_id` (Task 18에서 정의) — Task 33, 34에서 의존성 사용 ✓
- `useAuth` (Task 39에서 정의) — Task 40, 41에서 동일 ✓
- `TransactionList` (Task 41에서 정의) — `app.tsx`/`guest.tsx`에서 사용 ✓
- `mask_pan` (Task 26에서 정의) — `parse_row` (Task 28)에서 호출 ✓

**Inconsistencies**: 발견 안 됨.

### 4. 알려진 미세 위험
- **순환 import 위험** (Task 30): `app/parsers/__init__.py` ↔ `samsung_card.py`. Task 30 Step 1에 우회 가이드 박음 (lazy import 또는 ParseError 인라인 정의).
- **HTTPX TestClient + lifespan**: `ASGITransport`가 lifespan을 항상 호출하지는 않음. Task 09 Step 4에서 raise_app_exceptions=False로 우회. DB 의존 테스트(Task 14, 15, 16, 17, 35)는 conftest의 직접 DB 풀로 처리.
- **Refresh cookie path=/auth**: 테스트에서 `cookies=cookies1` 전달 시 path가 일치해야 동작. httpx는 path 검사가 느슨해 OK.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-30-w1-skeleton-and-samsung-xlsx-parser.md`. Two execution options:

**1. Subagent-Driven (recommended)** — 매 task마다 fresh subagent 디스패치, 사이에 리뷰. 빠른 반복.

**2. Inline Execution** — 같은 세션에서 `superpowers:executing-plans` 사용. 체크포인트 단위 일괄 실행.

**Which approach?**

(이 plan 파일은 컨텍스트 clear 후에도 새 세션에서 읽어 진행 가능합니다. 새 세션에서 `/superpowers:subagent-driven-development docs/superpowers/plans/2026-04-30-w1-skeleton-and-samsung-xlsx-parser.md` 또는 `/superpowers:executing-plans <같은 경로>`로 호출.)
