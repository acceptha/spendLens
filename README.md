# spendLens

> 광고 없는 가계부 · AI 코칭 · 데이터는 내 서버

## Status
**W8 complete** — 월 결산 리포트(집계 · 예산 성적표 · 전월 대비 증감 Top 3), 현금 거래 직접 입력. (W7: 월 예산 목표 + 초과 경고 · 수정 학습 기반 자동 분류 · 레거시 `.xls` 지원 / W6: 가맹점 정규화 · 설치형 PWA · 거래 삭제 · 일일 DB 백업 · 가동 확인 / W5: TanStack Query 전면 전환 / W4: 월간 LLM 인사이트 + 룰 기반 폴백 / W3: Tremor 대시보드 · 카테고리 19종 · 통장 룰북)

> 전체 기능 · 아키텍처 · API 레퍼런스는 **[`docs/FEATURES.md`](docs/FEATURES.md)** 참고.

Live:
> `suim-app.store` 도메인 만료(2026-10)로 임시 주소 운영 중. 웹은 Vercel 기본 주소, API는 웹의 `/api/*` 프록시(→ `api-3-38-103-25.sslip.io`)로 접근.

- **Web:** https://spend-lens-web-suim9770-5820s-projects.vercel.app
- **Signup:** https://spend-lens-web-suim9770-5820s-projects.vercel.app/signup
- **App (login required):** https://spend-lens-web-suim9770-5820s-projects.vercel.app/app
- **Dashboard (login required):** https://spend-lens-web-suim9770-5820s-projects.vercel.app/dashboard
- **Guest demo:** https://spend-lens-web-suim9770-5820s-projects.vercel.app/guest
- **API healthz:** https://spend-lens-web-suim9770-5820s-projects.vercel.app/api/healthz

## Tech Stack
- Frontend: React + Vite + TypeScript + Tailwind + Zustand + **TanStack Query** (서버 상태) + **Tremor** (대시보드 차트)
- Backend: FastAPI + pandas + openpyxl + asyncpg + Alembic
- Cache / Rate limit: Redis 7 (Lightsail Docker)
- AI: Claude Haiku 4.5 (카테고리 분류 + 월간 인사이트, 월 예산 cap). 키 없거나 호출 실패 시 룰 기반 인사이트로 폴백.
- Deploy: Vercel + AWS Lightsail (Docker Compose + Caddy + PostgreSQL + Redis) + GitHub Actions

## 지원 명세서 포맷
- **삼성카드** XLSX (`■ 국내이용내역` 시트)
- **우리카드** XLSX (`이용대금명세서 상세 내역`)
- **하나은행 통장** XLSX (`거래내역조회` — 출금/입금 양쪽, 적요 기반 자동 분류)

`.xls` (구버전 Excel binary)도 그대로 업로드 가능 — 서버가 메모리상에서 `.xlsx`로 변환한 뒤 같은 파서를 사용 (`parsers/xls.py`).

## 카테고리 분류 (19개)
- 카드 지출: coffee · lunch · dinner · snack_late · groceries · transport · telecom · subscription · entertainment · health · shopping · utilities · etc · unknown
- W3 통장: **savings · insurance · income · transfer · housing**

분류 흐름: 수정 학습(같은 가맹점에 사용자가 고친 카테고리) → 룰북 정규식 → Redis 캐시 → Claude Haiku LLM → "unknown". 사용자가 거래의 카테고리 칩을 클릭해 직접 수정하면 `user_category_override`로 영구 저장 (재업로드해도 보존).

## Repo Layout
```
apps/web        — React frontend (Vercel)
apps/api        — FastAPI backend (Lightsail), categorization + dashboard 모듈 포함
infra/          — Caddyfile, docker-compose, bootstrap, deployment notes
scripts/        — 운영 도우미 스크립트
docs/           — 설계/계획/회고 문서
```

## Deployment
- W1 infra setup: [`W1-DEPLOYMENT-SETUP.md`](W1-DEPLOYMENT-SETUP.md)
- W2 운영 배포 메모 (Redis + Anthropic ENV): [`infra/W2-DEPLOYMENT-NOTES.md`](infra/W2-DEPLOYMENT-NOTES.md)
- W3 인프라 변경 없음 (마이그레이션 0003은 자동 적용, `@tremor/react`는 frontend만)
- Lightsail step-by-step (AL2023): [`infra/lightsail-al2023-setup.md`](infra/lightsail-al2023-setup.md)

## Local Dev
```
docker compose -f infra/docker-compose.yml up -d redis
cd apps/api && uv run alembic upgrade head && uv run uvicorn app.main:app --reload
pnpm -C apps/web dev
```

## Spec & Plan
- W1 spec/plan: `docs/superpowers/specs/2026-04-29-w1-skeleton-and-samsung-xlsx-parser-design.md`, `plans/2026-04-30-w1-skeleton-and-samsung-xlsx-parser.md`
- W2 spec/plan: `docs/superpowers/specs/2026-05-13-w2-multi-user-llm-categorization-design.md`, `plans/2026-05-13-w2-multi-user-llm-categorization.md`
- W3 spec/plan: `docs/superpowers/specs/2026-05-20-w3-personal-mode-ui-design.md`, `plans/2026-05-20-w3-personal-mode-ui.md`
- W4 spec/plan: `docs/superpowers/specs/2026-06-10-w4-analytics-enhancement-design.md`, `plans/2026-06-10-w4-analytics-enhancement.md`
- W5 spec/plan: `docs/superpowers/specs/2026-06-12-w5-tanstack-query-migration-design-v2.md`, `plans/2026-06-12-w5-tanstack-query-migration.md`
