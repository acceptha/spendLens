# Infra

## Local Dev

옵션 A: 로컬 머신에 PostgreSQL 직접 설치 (권장):
```bash
# 1회: spendlens, spendlens_test DB 생성
# psql -U postgres -c "CREATE DATABASE spendlens;"
# psql -U postgres -c "CREATE DATABASE spendlens_test;"
cd apps/api && uv sync && uv run alembic upgrade head && uv run uvicorn app.main:app --reload
cd apps/web && pnpm dev
```

옵션 B: Docker로 테스트 DB만 (5433 포트):
```bash
cd infra && docker compose up -d postgres-test
# tests/.env.test의 DATABASE_URL을 localhost:5433/spendlens_test로 임시 수정
cd apps/api && DATABASE_URL=postgresql://postgres:postgres@localhost:5433/spendlens_test uv run alembic upgrade head
cd apps/api && uv run pytest -v
```

## Production (Lightsail)

운영은 Lightsail Ubuntu 22.04 인스턴스 1대에 docker compose로 postgres + api + caddy를 함께 띄움.

### Initial provisioning (once per instance)
1. SSH into Lightsail instance
2. Run bootstrap (download then exec, or scp first):
```bash
bash <(curl -sSL https://raw.githubusercontent.com/acceptha/spendLens/main/infra/lightsail-bootstrap.sh)
```
3. scp `Caddyfile` and `docker-compose.prod.yml` to `/opt/spendlens/`
4. Create `/opt/spendlens/.env` (chmod 600) with:
```
DATABASE_URL=postgresql://postgres:<POSTGRES_PASSWORD>@postgres:5432/spendlens
POSTGRES_PASSWORD=<강력한 랜덤 32자 이상>
ADMIN_EMAIL=<your email>
ADMIN_PASSWORD_HASH=<scripts/hash_password.py 실행 결과>
JWT_SECRET=<openssl rand -hex 32>
WEB_ORIGIN=https://spendlens.suim-app.store
GHCR_USER=<github username/org>
```
5. `docker login ghcr.io` (use GHCR_TOKEN PAT)
6. Export env vars + `up -d`:
```bash
cd /opt/spendlens
export $(grep -v '^#' .env | xargs)
docker compose -f docker-compose.prod.yml up -d
```

`api` 컨테이너의 entrypoint는 `alembic upgrade head && uvicorn ...`라서 첫 부팅 시 자동으로 schema 적용. `postgres` 컨테이너의 named volume `postgres_data`로 데이터 영구화.

### Ongoing deploy
- main push → GitHub Actions: build, push GHCR, ssh `docker compose pull && up -d`

### Backup
- Postgres data는 `postgres_data` named volume에 있음. 백업: `docker compose -f docker-compose.prod.yml exec postgres pg_dump -U postgres spendlens > backup.sql`
- Lightsail 인스턴스 스냅샷도 추천 (월 1회)

### Troubleshooting
- API 로그: `docker compose -f /opt/spendlens/docker-compose.prod.yml logs -f api`
- Caddy 로그: `docker compose -f /opt/spendlens/docker-compose.prod.yml logs -f caddy`
- DB 로그: `docker compose -f /opt/spendlens/docker-compose.prod.yml logs -f postgres`
- TLS 발급 실패 시 80/443 방화벽 + DNS 전파 확인
- 메모리 부족 시 (1GB 인스턴스): swap 1GB 추가 권장 (`sudo fallocate -l 1G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile`)
