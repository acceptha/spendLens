# spendLens

> 광고 없는 가계부 · AI 코칭 · 데이터는 내 서버

## Status
**W2 complete** — 다중 사용자 회원가입 + 카테고리 자동 분류(Claude Haiku 폴백) + Redis 캐시 + 우리카드 + 하나은행 통장 거래내역 파서. Live:
- **Web:** https://spendlens.suim-app.store
- **Signup:** https://spendlens.suim-app.store/signup
- **Guest demo (5초):** https://spendlens.suim-app.store/guest
- **API healthz:** https://api.spendlens.suim-app.store/healthz

## Tech Stack
- Frontend: React + Vite + TypeScript + Tailwind + Zustand
- Backend: FastAPI + pandas + openpyxl + asyncpg + Alembic
- Cache / Rate limit: Redis 7 (Lightsail Docker)
- AI: Claude Haiku 4.5 (카테고리 분류 폴백, 월 $5 cap)
- Deploy: Vercel + AWS Lightsail (Docker Compose + Caddy + PostgreSQL + Redis) + GitHub Actions

## 지원 명세서 포맷 (W2)
- **삼성카드** XLSX (`■ 국내이용내역` 시트)
- **우리카드** XLSX (`이용대금명세서 상세 내역`)
- **하나은행 통장** XLSX (`거래내역조회` — 출금/입금 양쪽)

`.xls` (구버전 Excel binary)는 사용자 머신에서 Excel/LibreOffice로 `.xlsx`로 변환 후 업로드. 한국 카드사 `.xls`의 codepage 메타데이터가 손상되어 라이브러리 추가로는 해결되지 않음.

## Repo Layout
```
apps/web        — React frontend (Vercel)
apps/api        — FastAPI backend (Lightsail), includes seed/ data
infra/          — Caddyfile, docker-compose, bootstrap, deployment notes
scripts/        — 운영 도우미 스크립트 (hash_password.py 등)
docs/           — 설계/계획 문서
```

## Deployment
- Infra setup record: [`W1-DEPLOYMENT-SETUP.md`](W1-DEPLOYMENT-SETUP.md)
- W2 운영 배포 메모: [`infra/W2-DEPLOYMENT-NOTES.md`](infra/W2-DEPLOYMENT-NOTES.md)
- Lightsail step-by-step (AL2023): [`infra/lightsail-al2023-setup.md`](infra/lightsail-al2023-setup.md)

## Local Dev
See `infra/README.md`. W2부터 redis 컨테이너 필요:
```
docker compose -f infra/docker-compose.yml up -d redis
```

## Spec & Plan
- W1 spec: `docs/superpowers/specs/2026-04-29-w1-skeleton-and-samsung-xlsx-parser-design.md`
- W1 plan: `docs/superpowers/plans/2026-04-30-w1-skeleton-and-samsung-xlsx-parser.md`
- W2 spec: `docs/superpowers/specs/2026-05-13-w2-multi-user-llm-categorization-design.md`
- W2 plan: `docs/superpowers/plans/2026-05-13-w2-multi-user-llm-categorization.md`
