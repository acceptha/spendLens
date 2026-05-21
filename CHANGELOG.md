# Changelog

## W3 — 2026-05-21

### Added
- `PATCH /transactions/{id}` — 사용자 카테고리 오버라이드 (`user_category_override` 컬럼, 19 enum Literal 검증, 404 NOT_FOUND, 422 invalid enum)
- `GET /transactions` 쿼리 파라미터 (`?month=YYYY-MM&category=csv&search=...&limit=...&offset=...`) — 필터/검색/페이지네이션. 카테고리 필터는 `effective_category` 기준.
- `GET /transactions/months` — 월 dropdown 옵션 (DISTINCT YYYY-MM DESC)
- 4 dashboard aggregate API: `/dashboard/{summary,by-category,by-month,top-merchants}` — 모두 `amount > 0` (출금) 기준
- `app/dashboard/` 모듈 (service + routes, raw SQL)
- 카테고리 enum **14 → 19** (+ `savings`, `insurance`, `income`, `transfer`, `housing`)
- 통장 룰북 5 패턴 (정기적금/CMS·보험/월급/이체/월세)
- LLM 시스템 프롬프트 갱신 — 통장 적요까지 포괄, `len(CATEGORIES)` 동적
- Frontend `components/Nav.tsx` — 헤더 nav (거래내역/대시보드/로그아웃, 활성 링크 강조)
- Frontend `components/CategoryChip.tsx` — 19 enum 인라인 드롭다운, 낙관적 업데이트 + 실패 시 롤백, outside click close
- Frontend `components/FilterBar.tsx` — 월 dropdown + 카테고리 multi-select + 가맹점 검색
- Frontend `routes/dashboard.tsx` (Tremor 4 위젯) — DonutChart + BarChart + Top 5 + 전월 대비 Metric
- Tailwind `darkMode: "class"` + `<html class="dark">` — Tremor 다크 테마 활성화

### Changed
- `TransactionOut` 응답에 `auto_category` / `user_category_override` / `effective_category` 추가
- `seed/routes.py`가 응답 시 TransactionRow shape 정렬 (id/auto_category/user_category_override/effective_category fallback)
- `transactions/routes.py` SELECT가 3 신규 컬럼 노출 (`COALESCE(user_category_override, category)`)
- 모든 dashboard 집계는 `amount > 0` (출금)만 — 입금/소득 분석은 W4+

### Migrations
- `0003_add_user_category_override` — `transactions.user_category_override TEXT NULL`

### Dependencies
- Frontend: `@tremor/react` 3.18.7 추가 (대시보드 차트)

### Tests
- W2 116 → W3 157 신규 + frontend 5 파일 18 tests (Nav 3 / CategoryChip 4 / FilterBar 4 / TransactionList 3 / signup 4)

## W2 — 2026-05-19

### Added
- `POST /auth/signup` — 즉시 가입, 비밀번호 정책 (8자 + 영문 + 숫자), 자동 로그인 토큰 발급
- IP 기반 rate limit (시간당 5회) — `/auth/signup`, `/auth/login` 양쪽 적용. 429 TOO_MANY_REQUESTS + Retry-After
- Redis 7 컨테이너 (rate limit + categorization 캐시 + LLM 비용 카운터)
- `app/categorization/` 모듈: rulebook → Redis 캐시 → 예산 체크 → Claude Haiku LLM → "unknown" 폴백
- `ANTHROPIC_MONTHLY_BUDGET_USD` 비용 가드 (월 $5 기본; 초과 시 LLM 호출 silent skip → "unknown")
- `parsers/registry.py`: 헤더 시그니처로 카드사/은행 자동 감지
- **우리카드** XLSX 파서 (`이용대금명세서 상세 내역`, MM.DD 일자 → 연도 추론, 승인번호 없음 → fallback dedup)
- **하나은행 통장** XLSX 파서 (`거래내역조회`, 출금=양수/입금=음수, full datetime)
- `/signup` React 페이지 + 에러 코드 한글 매핑 (WEAK_PASSWORD, EMAIL_ALREADY_EXISTS, TOO_MANY_REQUESTS)

### Changed
- W1 `app/parsers/simple_rules.py` 삭제 → `app/categorization/rulebook.py`로 통합 (정규식 + 14 카테고리 enum)
- `transactions/upload` 흐름: 파일 업로드 시 자동 카드사/은행 감지 → 거래마다 `await classify()` 호출 → DB 저장
- main 직접 commit → **feature 브랜치 + PR squash merge** 흐름으로 전환

### Spec Scope Change
- spec §9의 "통장/체크카드 거래 (W4+)"를 W2로 편입 — Phase 7이 하나카드 → 하나은행 통장으로 변경 (사용자 보유 명세서 현황 반영)

### Migrations
- `0002_add_llm_usage_log` — LLM 호출 감사 테이블 (model, tokens, cost_usd, purpose, merchant_normalized)

### Tests
- W1 (~57) → W2 (~116). 신규: password policy 5, rate limit 4, signup 4, categorization rulebook 17 + cache 7 + budget 4 + service 6 + LLM 4, registry 5, woori parser 8, hana bank parser 8.

## W1 — 2026-05-12

Initial release. Samsung XLSX parser, ENV-seeded single user, JWT auth (15m access + 7d refresh httpOnly cookie), guest mode with seed data, Vercel + Lightsail + Caddy + Supabase→PostgreSQL.
