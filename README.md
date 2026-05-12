# spendLens

> 광고 없는 가계부 · AI 코칭 · 데이터는 내 서버

## Status
**W1 complete** (skeleton + 삼성카드 XLSX 파서 + 첫 배포). Live:
- **Web:** https://spendlens.suim-app.store
- **Guest demo (5초):** https://spendlens.suim-app.store/guest
- **API healthz:** https://api.spendlens.suim-app.store/healthz

## Tech Stack
- Frontend: React + Vite + TypeScript + Tailwind + Zustand
- Backend: FastAPI + pandas + openpyxl + asyncpg + Alembic
- AI: Claude Haiku (W2)
- Deploy: Vercel + AWS Lightsail (Docker Compose + Caddy + PostgreSQL) + GitHub Actions

## Repo Layout
```
apps/web        — React frontend (Vercel)
apps/api        — FastAPI backend (Lightsail), includes seed/ data
infra/          — Caddyfile, docker-compose, bootstrap, setup docs
scripts/        — 운영 도우미 스크립트 (hash_password.py 등)
docs/           — 설계/계획 문서
```

## Deployment
- Infra setup record: [`W1-DEPLOYMENT-SETUP.md`](W1-DEPLOYMENT-SETUP.md)
- Lightsail step-by-step (AL2023): [`infra/lightsail-al2023-setup.md`](infra/lightsail-al2023-setup.md)

## Local Dev
See `infra/README.md`.

## Spec & Plan
- Spec: `docs/superpowers/specs/2026-04-29-w1-skeleton-and-samsung-xlsx-parser-design.md`
- Plan: `docs/superpowers/plans/2026-04-30-w1-skeleton-and-samsung-xlsx-parser.md`
