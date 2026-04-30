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
```
apps/web        — React frontend (Vercel)
apps/api        — FastAPI backend (Lightsail)
packages/parser-shared — Shared TS types
seed/           — 게스트 모드 시드 데이터
infra/          — Docker / Caddy / bootstrap
scripts/        — 운영 도우미 스크립트
docs/           — 설계/계획 문서
```

## Local Dev
See `infra/README.md`.

## Spec & Plan
- Spec: `docs/superpowers/specs/2026-04-29-w1-skeleton-and-samsung-xlsx-parser-design.md`
- Plan: `docs/superpowers/plans/2026-04-30-w1-skeleton-and-samsung-xlsx-parser.md`
