# spendLens

> 광고 없는 가계부 · AI 코칭 · 데이터는 내 서버

## Status
**W3 complete** — 본인 모드 UI 완성: 거래 필터/검색·인라인 카테고리 오버라이드·`/dashboard` (Tremor 4 위젯)·enum 14→19·통장 룰북 보강. Live:
- **Web:** https://spendlens.suim-app.store
- **Signup:** https://spendlens.suim-app.store/signup
- **App (login required):** https://spendlens.suim-app.store/app
- **Dashboard (login required):** https://spendlens.suim-app.store/dashboard
- **Guest demo:** https://spendlens.suim-app.store/guest
- **API healthz:** https://api.spendlens.suim-app.store/healthz

## Tech Stack
- Frontend: React + Vite + TypeScript + Tailwind + Zustand + **Tremor** (대시보드 차트)
- Backend: FastAPI + pandas + openpyxl + asyncpg + Alembic
- Cache / Rate limit: Redis 7 (Lightsail Docker)
- AI: Claude Haiku 4.5 (카테고리 분류 폴백, 월 $5 cap)
- Deploy: Vercel + AWS Lightsail (Docker Compose + Caddy + PostgreSQL + Redis) + GitHub Actions

## 지원 명세서 포맷 (W3 기준)
- **삼성카드** XLSX (`■ 국내이용내역` 시트)
- **우리카드** XLSX (`이용대금명세서 상세 내역`)
- **하나은행 통장** XLSX (`거래내역조회` — 출금/입금 양쪽, 적요 기반 자동 분류)

`.xls` (구버전 Excel binary)는 사용자 머신에서 Excel/LibreOffice로 `.xlsx`로 변환 후 업로드.

## 카테고리 분류 (19개)
- 카드 지출: coffee · lunch · dinner · snack_late · groceries · transport · telecom · subscription · entertainment · health · shopping · utilities · etc · unknown
- W3 통장: **savings · insurance · income · transfer · housing**

분류 흐름: 룰북 정규식 → Redis 캐시 → Claude Haiku LLM → "unknown". 사용자가 거래의 카테고리 칩을 클릭해 직접 수정하면 `user_category_override`로 영구 저장 (재업로드해도 보존).

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
