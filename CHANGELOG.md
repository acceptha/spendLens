# Changelog

## W7 — 2026-10-20 (월 예산)

### Added
- `GET /budgets/status?month=YYYY-MM` — 월 예산 현황 (예산·사용액·비율·월말 예상·상태 `over`/`warn`/`ok`)
- `PUT /budgets` — 예산 설정 `{category, amount}` (`_total`=총액, `amount: null`=해제). 이번 달(KST)부터 적용, 지난달은 당시 예산 유지
- `app/budgets/` 모듈 (routes + schemas + service)
- Frontend `/budget` 탭 + 대시보드 예산 카드 (총액 진행률 + 주의/초과 카테고리 최대 3개)

### Changed
- 카테고리의 **첫 예산은 가장 오래된 거래 월부터 소급 적용** (#52)
- 모바일 375px에서 예산 탭 포함 nav가 넘치지 않도록 조정 (#51)

### Migrations
- `0007_add_budgets` — `budgets` 테이블 (`effective_from` 행 단위 이력)

## W6 + 운영 후속 — 2026-07-09 ~ 2026-10-19

### Added
- 가맹점 정규화 (`categorization/merchant.py`) — 별칭 테이블 + 지점 토큰 제거로 브랜드 단위 그룹핑, `merchant_normalized` 저장, Top 가맹점·LLM 캐시 키에 사용 (#34)
- 설치형 PWA — `vite-plugin-pwa` 매니페스트 + 서비스워커 + 아이콘 (#35)
- `DELETE /transactions/{id}` — 거래 삭제 (API + 목록 버튼) (#44)
- 레거시 `.xls` 업로드 — 서버에서 메모리상 `.xlsx` 변환 후 기존 파서 사용 (`parsers/xls.py`) (#47)
- 수정 학습 — 사용자가 고친 카테고리를 같은 정규화 가맹점의 다음 업로드에 우선 적용 (#49)
- 일일 Postgres 백업 서비스 (14일 보관) (#42), 스케줄 업타임 체크 워크플로 `uptime.yml` (#48)
- 한글 카테고리 라벨 (`categorization/labels.py`) (#40)

### Changed
- 도메인(`suim-app.store`) 만료 대응 — 웹은 Vercel 기본 주소, API는 웹 `/api/*` 프록시 → `api-3-38-103-25.sslip.io` (#36, #39)
- rate limit을 실제 클라이언트 IP 기준으로 (#38)
- 현금흐름 추세를 최신 데이터 월 기준으로 고정 + 빈 달 0 채움 (#41)
- 거래 변경 시 해당 월 인사이트 캐시 무효화 (#45)

### Migrations
- `0005_backfill_merchant_normalized` — 기존 거래 `merchant_normalized` 자동 백필 (#43)
- `0006_invalidate_insight_on_txn_change` — 거래 INSERT/UPDATE/DELETE 시 해당 월 `monthly_insights` 삭제 트리거 (#45)

## W5 — 2026-06-12 ~ 2026-07-08 (프론트 UX)

### Added
- 프론트 서버 상태를 TanStack Query로 전면 전환 (쿼리 키 팩토리, 낙관적 갱신, 검색 debounce, `keepPreviousData`)
- 부팅 시 인증 재수화 — 새로고침해도 세션 유지 (#23, #25)
- 룰 기반 인사이트 폴백 (`insights/rules.py`) — LLM 키가 없거나 호출 실패 시 사용 (#27, #28)
- 대시보드 카테고리 차트 클릭 → `/app` 필터 프리필 (#29)
- 라우트 단위 코드 스플리팅 (#30)

### Changed
- 모든 지출 집계에서 `transfer`·`savings` 제외 (`NON_SPENDING_CATEGORIES`) (#31, #32)
- LLM 호출 실패를 `InsightError`로 감싸 500 대신 502 → 이후 룰 폴백으로 전환 (#26, #28)

## W4 — 2026-06-10 (분석 고도화)

### Added
- `POST /insights/generate` (body `{month}`, `?force`) + `GET /insights?month=` — Claude Haiku 월간 인사이트(구조화 하이라이트 top_growth/anomaly/saving_tip), 온디맨드 + `monthly_insights` DB 캐시. 예산초과 503 BUDGET_EXCEEDED, LLM 실패 502 INSIGHT_GENERATION_FAILED.
- `app/insights/` 모듈 (llm + service + routes + schemas)
- `GET /dashboard/cashflow-by-month?last_n=` — 월별 지출+수입 결합 추세
- `GET /dashboard/by-essential?month=` — 필수/비필수 합계
- `PATCH /transactions/{id}/essential` — 3-state 토글 (필수/비필수/자동)
- `app/categorization/essential.py` — 카테고리 → 필수 기본 매핑(파생 계산)
- Frontend `components/{InsightCard,MetricStrip,CashflowChart,EssentialDonut,EssentialToggle}.tsx` + B+ 대시보드 레이아웃

### Changed
- `GET /dashboard/summary` — `income_total` / `net_savings` / `savings_rate` 추가 (수입은 이체 제외)
- `GET /transactions` 응답 — `essential`/`essential_reason` 제거 → `essential_override` / `effective_essential`
- 마이그레이션 0004 — `transactions.essential_override` 컬럼 + `monthly_insights` 테이블

### Removed
- `GET /dashboard/by-month` — `cashflow-by-month`로 대체

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
