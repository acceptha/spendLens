# spendLens API

FastAPI backend, managed by `uv`. 모듈 구조·컨벤션은 루트 [`CLAUDE.md`](../../CLAUDE.md), 기능·API 레퍼런스는 [`docs/FEATURES.md`](../../docs/FEATURES.md).

## Local
```bash
docker compose -f infra/docker-compose.yml up -d redis   # 저장소 루트에서
cd apps/api
uv sync
# .env 필요: 루트 .env.example 참고 (DATABASE_URL, JWT_SECRET, ADMIN_EMAIL, ADMIN_PASSWORD_HASH 등)
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

## Test / Lint
```bash
uv run pytest      # 로컬 PostgreSQL 필요 — 접속 정보는 tests/.env.test
uv run ruff check .
```

## Migrations
Alembic **raw SQL**만 사용 (`--autogenerate` 금지). `migrations/versions/` 에 `000N_<설명>.py`로 추가.
