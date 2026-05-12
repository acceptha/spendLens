# spendLens W1 배포 설정 기록

> 본 문서는 W1 코드 작성이 끝난 시점부터 라이브 데모 가동까지, **각 어플리케이션/서비스에서 수행한 모든 설정**을 한 곳에 정리한 기록이다. 새로 누군가 환경을 재구축하거나, 인스턴스를 옮기거나, 사고 후 복구할 때의 single source of truth.
>
> 자세한 step-by-step 명령어는 `infra/lightsail-al2023-setup.md`에 별도로 있다 (Lightsail 한정). 본 문서는 **무엇을 어디에 어떻게 설정했는가**의 inventory.

---

## 1. 아키텍처 한눈에

```
                              ┌──────────────────────────────┐
                              │ 가비아 DNS  (suim-app.store) │
                              ├─ A    api.spendlens → 3.38.103.25
                              └─ CNAME spendlens     → cname.vercel-dns.com.

                                          │ DNS 위임
                ┌─────────────────────────┼───────────────────────────────┐
                │                                                          │
                ▼                                                          ▼
   https://spendlens.suim-app.store                       https://api.spendlens.suim-app.store
                │                                                          │
                ▼                                                          ▼
   ┌─────────────────────────┐                       ┌────────────────────────────────┐
   │ Vercel (apps/web)       │                       │ AWS Lightsail (3.38.103.25)     │
   │ React + Vite + TS       │                       │ Amazon Linux 2023, 2GB/2vCPU    │
   │ - main push 자동 배포   │                       │ ┌────────────────────────────┐  │
   │ - VITE_API_BASE → api.. │                       │ │ Caddy (TLS auto, 80/443)   │  │
   └─────────────────────────┘                       │ │       │                    │  │
                                                     │ │       ▼ reverse_proxy      │  │
                                                     │ │ FastAPI + uvicorn :8000    │  │
                                                     │ │       │                    │  │
                                                     │ │       ▼ asyncpg            │  │
                                                     │ │ Postgres 16 (volume)       │  │
                                                     │ └────────────────────────────┘  │
                                                     └────────────────────────────────┘
                                                                  ▲
                                                                  │ docker pull
                                                     ┌────────────┴───────────────┐
                                                     │ GHCR (ghcr.io/acceptha)    │
                                                     │ spendlens-api:latest       │
                                                     │ + spendlens-api:<sha>      │
                                                     └────────────┬───────────────┘
                                                                  ▲
                                                                  │ Actions build/push
                                                     ┌────────────┴───────────────┐
                                                     │ GitHub: acceptha/spendLens │
                                                     │ - main branch              │
                                                     │ - CI workflow (web + api)  │
                                                     │ - Deploy workflow          │
                                                     └────────────────────────────┘
```

---

## 2. GitHub

### 2.1 레포

| 항목 | 값 |
|---|---|
| Owner | `acceptha` (조직) |
| Repo | `acceptha/spendLens` |
| Visibility | Private |
| Default branch | `main` |
| 원격 URL | `git@github.com-acceptha:acceptha/spendLens.git` (사용자별 SSH alias) |

### 2.2 GitHub Actions 워크플로

| 파일 | 트리거 | 잡 | 상태 |
|---|---|---|---|
| `.github/workflows/ci.yml` | push/PR to main | `web` (build + vitest), `api` (alembic + ruff + pytest with Postgres service) | ✅ 모두 ✅ |
| `.github/workflows/deploy-api.yml` | push to main + paths(`apps/api/**`, `infra/Caddyfile`, `infra/docker-compose.prod.yml`, deploy-api.yml 자체) + workflow_dispatch | docker build → GHCR push → scp Caddyfile/compose to Lightsail → ssh `docker compose pull && up -d` | ⚠️ build/push만 동작 (scp/ssh는 Secrets 등록 + username fix 후 활성화) |

#### Vercel (web 측) 자동 배포

별도 워크플로 없음. **Vercel이 GitHub webhook으로 main push를 감지** → 자동 빌드/배포. GitHub Actions 추가 설정 불필요.

### 2.3 Personal Access Token (classic)

| 토큰 | 용도 | scope | 보관 위치 |
|---|---|---|---|
| `spendlens-ghcr-pull-v1` | (revoked — 채팅 노출로 폐기) | — | — |
| `spendlens-ghcr-pull-v2` | Lightsail에서 GHCR image pull | `read:packages` | Lightsail의 `/home/ec2-user/.docker/config.json` (base64 저장) |

> push는 GitHub Actions의 `secrets.GITHUB_TOKEN`(자동)이 처리하므로 사용자 PAT는 read만 있으면 충분.

### 2.4 GitHub Secrets (Repo → Settings → Secrets and variables → Actions)

| Secret | 값 | 상태 |
|---|---|---|
| `LIGHTSAIL_HOST` | `3.38.103.25` | ❌ 미등록 (deploy-api scp/ssh가 이걸 요구) |
| `LIGHTSAIL_SSH_KEY` | `.pem` 파일 전체 내용 | ❌ 미등록 |
| `GITHUB_TOKEN` | (자동 제공) | ✅ |

### 2.5 GHCR (Container Registry)

| 항목 | 값 |
|---|---|
| Image name | `ghcr.io/acceptha/spendlens-api` |
| Tags | `latest`, `<git-sha>` |
| Visibility | (GitHub package settings에서 private/public 결정) |
| 빌드 주체 | GitHub Actions의 deploy-api 워크플로 |
| Pull 주체 | Lightsail의 docker (PAT 로그인) |

---

## 3. Vercel (frontend)

| 항목 | 값 / 상태 |
|---|---|
| Project | spendLens (or similar) |
| Source | GitHub `acceptha/spendLens` |
| Branch | `main` (push 자동 배포) |
| Framework Preset | **Vite** ⚠️ 확인 필요 |
| Root Directory | **`apps/web`** ⚠️ 모노레포 핵심 — 미설정이면 빌드 실패 |
| Install Command | `pnpm install --filter @spendlens/web...` (또는 Vercel auto) |
| Build Command | `pnpm --filter @spendlens/web build` (또는 `pnpm build` if root=apps/web) |
| Output Directory | `dist` |
| Environment Variables | `VITE_API_BASE` = `https://api.spendlens.suim-app.store` ⚠️ 미설정이면 frontend가 API 못 찾음 |
| Custom Domain | `spendlens.suim-app.store` ⚠️ DNS는 등록됨, Vercel UI에서 add 해야 활성 |

> ⚠️로 표시된 항목은 **사용자가 Vercel 대시보드에서 직접 확인/추가**해야 함. 임시 `*.vercel.app` URL은 환경변수 없이도 빌드되지만, `/guest`/`/login`/`/app` 페이지가 API 호출 시 `localhost:8000` 시도 → 실패.

---

## 4. AWS Lightsail (backend)

### 4.1 인스턴스

| 항목 | 값 |
|---|---|
| Region | `ap-northeast-2` (Seoul) |
| Blueprint | Amazon Linux 2023 |
| Plan | $10/mo (2 vCPU, 2GB RAM, 60GB SSD) |
| Instance name | (콘솔에서 확인) |
| Static IP | `3.38.103.25` (인스턴스에 attach) |
| 기본 SSH 사용자 | `ec2-user` |

### 4.2 방화벽 (Lightsail Networking → IPv4 Firewall)

| Application | Protocol | Port | Source | 용도 |
|---|---|---|---|---|
| SSH | TCP | 22 | 본인 IP 권장 | 관리 접속 |
| HTTP | TCP | 80 | Anywhere (0.0.0.0/0) | Caddy ACME challenge + HTTPS redirect |
| HTTPS | TCP | 443 | Anywhere (0.0.0.0/0) | API 요청 + Caddy serving |

### 4.3 SSH 키

| 항목 | 값 |
|---|---|
| Key name | (Lightsail 콘솔 표시) |
| Local path | 사용자 머신 `~/.ssh/<name>.pem` (chmod 400) |
| 사용 | `ssh -i <path> ec2-user@3.38.103.25` |

### 4.4 시스템 setup (수동 실행 — 자세한 내용은 `infra/lightsail-al2023-setup.md`)

| 단계 | 명령 | 결과 |
|---|---|---|
| 1 | `sudo dnf update -y` | 시스템 패키지 갱신 |
| 2 | `sudo dnf install -y docker` | Docker 엔진 설치 (AL2023 패키지) |
| 3 | `sudo systemctl enable --now docker` | 자동시작 + 즉시 시작 |
| 4 | `sudo usermod -aG docker ec2-user` | sudo 없이 docker 실행 가능 |
| 5 | (수동) docker compose v2 plugin 다운로드 → `/usr/libexec/docker/cli-plugins/docker-compose` | `docker compose version` 동작 |
| 6 | `sudo mkdir -p /opt/spendlens && sudo chown ec2-user:ec2-user /opt/spendlens` | 작업 디렉토리 |
| 7 | scp로 `Caddyfile`, `docker-compose.prod.yml` → `/opt/spendlens/` | compose가 읽을 파일 배치 |
| 8 | `cat > /opt/spendlens/.env` (chmod 600) | secrets 파일 (값은 4.5 참고) |
| 9 | `docker login ghcr.io -u acceptha --password-stdin <<< $PAT` | GHCR pull 권한 |
| 10 | `cd /opt/spendlens && docker compose -f docker-compose.prod.yml pull && up -d` | 첫 배포 |

### 4.5 `/opt/spendlens/.env` 내용 구조 (값은 인스턴스 내에만 보관)

```
DATABASE_URL=postgresql://postgres:<POSTGRES_PASSWORD>@postgres:5432/spendlens
POSTGRES_PASSWORD=<32자 랜덤>
ADMIN_EMAIL=acceptha@gmail.com
ADMIN_PASSWORD_HASH='<argon2id 해시 — single-quote 필수>'
JWT_SECRET=<64자 hex>
WEB_ORIGIN=https://spendlens.suim-app.store
GHCR_USER=acceptha
```

| 변수 | 값 위치 | 비고 |
|---|---|---|
| `DATABASE_URL` | `/opt/spendlens/.env` | host=`postgres` (compose 서비스명) |
| `POSTGRES_PASSWORD` | 위 + 백업 (1Password 권장) | 노출 시 즉시 rotate + DB volume 재초기화 |
| `ADMIN_EMAIL` | 위 | login ID |
| `ADMIN_PASSWORD_HASH` | 위 (`'$argon2id$...'` 단일 인용) | `scripts/hash_password.py` 결과 |
| `JWT_SECRET` | 위 | 노출 시 즉시 rotate (모든 access/refresh token 무효화 효과) |
| `WEB_ORIGIN` | 위 | CORS allow_origins. Vercel 도메인과 정확히 일치 |
| `GHCR_USER` | 위 | compose의 `${GHCR_USER}` 치환용 |

### 4.6 동작 중인 컨테이너 (3개)

| 컨테이너 | 이미지 | 포트 | 의존 |
|---|---|---|---|
| `spendlens-postgres-1` | `postgres:16-alpine` | 5432 (내부) | — |
| `spendlens-api-1` | `ghcr.io/acceptha/spendlens-api:latest` | 8000 (내부) | postgres healthy |
| `spendlens-caddy-1` | `caddy:2-alpine` | 80, 443 (외부) | — |

| Volume | 용도 |
|---|---|
| `postgres_data` | DB persistence (호스트 재부팅에도 보존) |
| `caddy_data` | TLS 인증서, ACME 상태 |
| `caddy_config` | Caddy 내부 config |
| `caddy_logs` | 액세스 로그 |

### 4.7 첫 배포 검증 결과 (2026-05-08)

```bash
$ curl -i https://api.spendlens.suim-app.store/healthz
HTTP/2 200
alt-svc: h3=":443"; ma=2592000
content-type: application/json
server: uvicorn
via: 1.1 Caddy

{"status":"ok"}
```

✅ TLS 자동 발급 (Let's Encrypt) · ✅ Caddy reverse_proxy · ✅ FastAPI 응답 · ✅ DB 마이그레이션 + admin seed 완료

---

## 5. 가비아 DNS (`suim-app.store`)

| 호스트 | 타입 | 값 | TTL | 용도 |
|---|---|---|---|---|
| `api.spendlens` | A | `3.38.103.25` | 3600 | Lightsail로 직결 (TLS는 Caddy가 발급) |
| `spendlens` | CNAME | `cname.vercel-dns.com.` | 3600 | Vercel CDN (TLS는 Vercel이 발급) |

### 검증
```bash
nslookup api.spendlens.suim-app.store 8.8.8.8  # → 3.38.103.25
nslookup spendlens.suim-app.store 8.8.8.8       # → cname.vercel-dns.com → 76.76.21.x
```

---

## 6. Supabase (제외됨)

당초 계획에서 운영 DB로 사용하려 했으나, 무료 플랜의 direct connection이 IPv6 only이고 사용자 네트워크에서 IPv6 외부 라우팅이 안 되어 **사용 안 함**. Lightsail 위 docker postgres로 대체.

| Supabase 자원 | 처리 |
|---|---|
| 프로젝트 `vvisirlpwlyzjwvkdxni` | 결제 안 함, 그대로 두거나 삭제 가능 |
| 프로젝트의 DB 자격증명 | 더 이상 사용 안 함 |

---

## 7. 로컬 개발 환경

### 7.1 도구 (사용자 머신)

| 도구 | 버전 | 용도 |
|---|---|---|
| pnpm | 10.12.1 | 모노레포 패키지 매니저 |
| uv | 0.7.8 | Python 의존성 + venv 관리 (apps/api) |
| Python | 3.12 (uv가 자동 설치, 시스템은 3.9) | 백엔드 런타임 |
| Node.js | 22 | 프론트엔드 빌드 |
| Docker | 24.0.7 | (선택) 로컬 컨테이너 |
| PostgreSQL | 18.3 (Windows native install) | 로컬 dev DB |

### 7.2 로컬 PostgreSQL

| 항목 | 값 |
|---|---|
| Host:Port | `localhost:5432` |
| Superuser | `postgres` / 비번 `suim` |
| Database 1 | `spendlens` (개발용 — `apps/api/.env`의 `DATABASE_URL`이 가리킴) |
| Database 2 | `spendlens_test` (pytest용 — `apps/api/tests/.env.test`의 `DATABASE_URL`이 가리킴) |
| 마이그레이션 적용 | 둘 다 `alembic upgrade head` 완료 (5 tables: alembic_version + users + refresh_tokens + source_files + transactions) |

### 7.3 .env 파일들 (모두 gitignored)

| 경로 | 용도 | 누가 관리 |
|---|---|---|
| `/<repo>/.env` | 사용자 master copy (NEXT_PUBLIC_* 잔재 가능) | 사용자 |
| `/<repo>/apps/api/.env` | 백엔드 로컬 실행 (pydantic-settings의 `env_file=".env"` 상대경로) | 사용자 (마이그레이션 시 사용) |
| `/<repo>/apps/api/tests/.env.test` | 테스트용 placeholder값 (커밋됨) | 코드에 포함 |

**커밋 가능한 템플릿:** `.env.example` (root)

---

## 8. 라이브 URL

| 서비스 | URL | 상태 |
|---|---|---|
| API healthz | https://api.spendlens.suim-app.store/healthz | ✅ |
| API seed | https://api.spendlens.suim-app.store/seed/transactions | ✅ |
| API auth/login | https://api.spendlens.suim-app.store/auth/login (POST) | 검증 필요 |
| API transactions | https://api.spendlens.suim-app.store/transactions (GET, Bearer) | 검증 필요 |
| Web 랜딩 | https://spendlens.suim-app.store | Vercel 빌드/도메인 설정 따라 |
| Web guest demo | https://spendlens.suim-app.store/guest | API 호출 검증 필요 |
| Web 로그인 | https://spendlens.suim-app.store/login | 위 동일 |
| Web 본인 모드 | https://spendlens.suim-app.store/app | ProtectedRoute, 로그인 후 |

---

## 9. 운영 명령어 모음 (인스턴스에서)

```bash
# 컨테이너 상태
cd /opt/spendlens
docker compose -f docker-compose.prod.yml ps

# 로그
docker compose -f docker-compose.prod.yml logs -f api
docker compose -f docker-compose.prod.yml logs -f caddy
docker compose -f docker-compose.prod.yml logs postgres | tail -50

# 수동 재시작 (api만)
docker compose -f docker-compose.prod.yml restart api

# 새 image 수동 적용 (자동 배포 활성화 전까지)
docker compose -f docker-compose.prod.yml pull api
docker compose -f docker-compose.prod.yml up -d
docker image prune -f

# DB 백업
docker compose -f docker-compose.prod.yml exec postgres \
  pg_dump -U postgres spendlens > spendlens-$(date +%F).sql

# DB 셸
docker compose -f docker-compose.prod.yml exec postgres \
  psql -U postgres spendlens

# 컨테이너 리소스
docker stats --no-stream
```

---

## 10. 미완료 / 다음 단계

| 항목 | 작업 주체 | 영향 |
|---|---|---|
| GitHub Secrets 등록 (`LIGHTSAIL_HOST`, `LIGHTSAIL_SSH_KEY`) | 사용자 | deploy-api workflow scp/ssh 활성화 |
| `.github/workflows/deploy-api.yml`의 `username: ubuntu` → `ec2-user` (2곳) | 코드 commit | AL2023 호환 |
| `infra/lightsail-bootstrap.sh` Ubuntu apt → AL2023 dnf 갱신 | 코드 commit | 미래 재구축 시 사용 |
| `infra/lightsail-al2023-setup.md` git add | 코드 commit | 본 작업의 부속 문서 |
| Vercel `VITE_API_BASE` 환경변수 추가 | 사용자 (Vercel UI) | frontend → API 연결 |
| Vercel 커스텀 도메인 `spendlens.suim-app.store` add | 사용자 (Vercel UI) | 짧은 URL로 접근 |
| 외부 검증: login + 업로드 flow + dedup 멱등 (Plan Tasks 63-64) | 사용자 + 코드 | W1 검수 마무리 |
| `README.md` Live Demo URL 업데이트 (Plan Task 65) | 코드 commit | 첫 release 표시 |

---

## 11. 보안 메모

- **revoked PAT** `ghp_ZL...` (채팅 노출) — 즉시 폐기 완료. 새 PAT v2 사용 중.
- **POSTGRES_PASSWORD / JWT_SECRET / ADMIN_PASSWORD_HASH** — `/opt/spendlens/.env` (chmod 600) + 사용자 1Password 등에 백업 권장.
- **.pem SSH key** — 사용자 머신 외부 노출 X. GitHub Secrets에는 그 내용을 페이스트하지만, 그 secret은 GitHub Actions 외부에서 조회 불가 (write-only).
- **citext 확장** — Postgres 16 이상에서 기본 포함. 별도 설치 불필요. 마이그레이션 0001이 `CREATE EXTENSION IF NOT EXISTS citext`로 처리.
- **httpOnly + Secure + SameSite=Lax** — refresh cookie. CSRF는 path=/auth로 제한 + Bearer 헤더 분리로 1차 방어. W2+에서 추가 강화.

---

## 12. 비용 추정 (월간)

| 항목 | 비용 (USD) |
|---|---|
| Lightsail 인스턴스 ($10 plan) | 10 |
| Lightsail 정적 IP | 0 (인스턴스에 attach 시 무료) |
| 가비아 도메인 `suim-app.store` | (이미 보유, 별도 비용 없음) |
| Vercel Hobby | 0 |
| GitHub Free + Actions | 0 (퍼블릭/프라이빗 무관, 일정 한도 무료) |
| GHCR | 0 (Free tier 한도 내) |
| **합계** | **~$10/월** |

W2에서 Claude Haiku API 호출이 추가되면 사용량 만큼 별도 비용.

---

## 부록 A: 레포 구조

```
spendLens/
├── .github/workflows/
│   ├── ci.yml               # CI (web + api)
│   └── deploy-api.yml       # Lightsail 자동 배포
├── apps/
│   ├── api/                 # FastAPI (Python 3.12, uv)
│   │   ├── app/             # 라우트, 서비스, 파서, 시드
│   │   ├── migrations/      # Alembic
│   │   ├── seed/            # 게스트 모드 데이터 (Docker context 포함)
│   │   ├── tests/           # pytest
│   │   ├── Dockerfile       # multi-stage
│   │   ├── pyproject.toml
│   │   └── uv.lock
│   └── web/                 # React (Vite, TS, Tailwind)
│       ├── src/             # 라우트, 컴포넌트, store, lib
│       ├── package.json
│       ├── vite.config.ts
│       └── tsconfig*.json
├── infra/
│   ├── Caddyfile            # 운영 reverse proxy
│   ├── docker-compose.prod.yml  # postgres + api + caddy
│   ├── docker-compose.yml   # 로컬 (postgres-test)
│   ├── lightsail-bootstrap.sh
│   ├── lightsail-al2023-setup.md   # 줄별 설명 가이드
│   └── README.md
├── scripts/
│   └── hash_password.py     # ADMIN_PASSWORD_HASH 생성기
├── docs/
│   └── superpowers/         # spec + plan 문서
├── package.json             # pnpm workspace root
├── pnpm-workspace.yaml
├── pnpm-lock.yaml
├── .npmrc
├── .env.example             # template (committed)
├── README.md
└── W1-DEPLOYMENT-SETUP.md   # 본 문서
```

---

## 부록 B: 참고 문서

- 구현 계획서: `docs/superpowers/plans/2026-04-30-w1-skeleton-and-samsung-xlsx-parser.md`
- 설계서: `docs/superpowers/specs/2026-04-29-w1-skeleton-and-samsung-xlsx-parser-design.md`
- Lightsail 명령어 줄별 설명: `infra/lightsail-al2023-setup.md`
- 인프라 README: `infra/README.md`

---

> **작성일:** 2026-05-08 (W1 첫 배포 검증 직후)
> **다음 갱신 예정:** Vercel/GitHub Secrets 마무리 + W2 시작 시점
