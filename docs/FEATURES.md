# SpendLens — 기능 문서

> 광고 없는 개인 가계부. 카드/은행 명세서를 업로드하면 자동 분류·분석하고, Claude로 월간 인사이트를 만든다. 데이터는 본인 서버(Lightsail)에 저장.
>
> 최종 갱신: 2026-06 (W5까지 반영). 주차별 상세는 `docs/superpowers/specs/`·`docs/releases/`, 회고는 `docs/retros/` 참고.

---

## 1. 개요

| 항목 | 내용 |
|---|---|
| 형태 | 모노레포 — `apps/api`(FastAPI 백엔드), `apps/web`(React+Vite 프론트) |
| 핵심 흐름 | 회원가입 → 카드/은행 명세서(XLSX) 업로드 → 자동 파싱·분류 → 거래 조회/수정 → 대시보드 분석 → 월간 LLM 인사이트 |
| 사용자 모드 | 본인 모드(로그인) + 게스트 데모(`/guest`, 로그인 없이 시드 데이터 열람) |
| 호스팅 | 웹=Vercel, API=AWS Lightsail(Docker Compose + Caddy + Let's Encrypt), DB=PostgreSQL, 캐시/예산=Redis |
| 도메인 | `spendlens.suim-app.store`(웹) · `api.spendlens.suim-app.store`(API) |

---

## 2. 기술 스택 & 아키텍처

**백엔드** — Python 3.12 / FastAPI / Pydantic v2 / **asyncpg raw SQL**(ORM 미사용) / Alembic raw SQL 마이그레이션 / `uv` 패키지 매니저 / anthropic SDK(Claude Haiku) / Redis.

**프론트** — React 18 / TypeScript / Vite / Tailwind / @tremor/react(차트) / **@tanstack/react-query v5**(서버 상태) / zustand(인증 상태) / axios / react-router v6 / `pnpm`.

**모듈 구조 (수직 슬라이스)** — `apps/api/app/` 아래 도메인별 디렉토리:

| 모듈 | 역할 |
|---|---|
| `auth/` | 회원가입·로그인·JWT·refresh·로그아웃, 관리자 시드, rate limit |
| `transactions/` | 명세서 업로드, 거래 목록/필터/검색, 카테고리·essential 수정 |
| `parsers/` | 카드/은행 XLSX 파서 (registry 패턴, 라우트 없음) |
| `categorization/` | 룰북 + Claude Haiku LLM 분류, 월간 예산 가드, essential 매핑 |
| `dashboard/` | 집계 API (요약·카테고리·현금흐름·필수/비필수·Top 가맹점) |
| `insights/` | 월간 LLM 인사이트 생성 + DB 캐시 |
| `seed/` | 게스트 데모 데이터 |

원칙: DB는 `async with acquire() as conn`, 인증만 `Depends(current_user_id)`, 라우터에서 `HTTPException` 직접 raise(에러 코드 `UPPER_SNAKE_CASE`).

---

## 3. 기능

### 3.1 인증 / 계정
- **회원가입** — 이메일+비밀번호(8자 이상, 영문+숫자). 가입 즉시 자동 로그인. 약한 비밀번호·중복 이메일·요청 과다(rate limit) 검증.
- **로그인 / 로그아웃** — 비밀번호 검증(argon2). access token(메모리) + refresh token(httpOnly 쿠키).
- **토큰 갱신** — `/auth/refresh`. 401 시 자동 재발급 인터셉터 + **앱 부팅 시 선제 재수화**(새로고침해도 세션 유지, W5 후속).
- 관리자 계정은 기동 시 환경변수로 시드.

### 3.2 명세서 업로드 & 파싱
- `.xlsx` 드래그앤드롭/클릭 업로드. dedup 해시로 중복 거래 자동 스킵(업로드 N건/중복 M건 표시).
- **지원 파서** (registry 패턴): 삼성카드, 우리카드, 하나은행(통장). 카드번호는 `****-1234` 마스킹, 취소건 표시.
- 파서는 `ParseError(code, **details)` 커스텀 예외 → 라우터에서 `HTTPException` 변환.

### 3.3 카테고리 자동 분류
- **2단계**: 룰북(가맹점명 규칙) 우선 → 미매칭만 **Claude Haiku LLM** 분류.
- 카테고리 19종(housing, utilities, telecom, groceries, health, insurance, transport, lunch, dinner, savings, income, transfer, coffee, snack_late, subscription, entertainment, shopping, etc, unknown).
- **월간 LLM 예산 가드** — Redis 버킷에 비용 누적, 한도 초과 시 LLM 호출 차단(분류·인사이트 공유).
- 사용자가 거래별 카테고리를 직접 오버라이드 가능. `effective_category = COALESCE(user_override, auto_category)` 단일 진실 출처.

### 3.4 거래 조회 / 관리
- 목록: 월 필터, 카테고리 다중 필터, 가맹점 검색(300ms 디바운스), 페이지네이션.
- 인라인 수정: 카테고리 칩 드롭다운, **필수/비필수 3-state 토글**(자동/필수/비필수).
- 낙관적 갱신(즉시 반영 → 실패 시 롤백) + 동시 토글 경합 가드.

### 3.5 대시보드 분석
- **요약 지표**: 지출 총액, 전월 대비 증감률, 수입 총액(이체 제외), 순저축, 저축률.
- **현금흐름 추세**: 월별 지출 vs 수입(최근 N개월).
- **카테고리별 지출 도넛**, **필수 vs 비필수 도넛**, **Top 5 가맹점**.
- 월 선택 시 이전 데이터 유지(`keepPreviousData`)로 깜빡임 없음, 빈 상태 메시지.

### 3.6 월간 LLM 인사이트
- "인사이트 생성" → 집계 수치를 Claude Haiku에 전달 → 구조화 하이라이트(top_growth / anomaly / saving_tip) 생성.
- 온디맨드 생성 후 `monthly_insights` 테이블에 캐시("다시 생성"은 캐시 무시 강제 재생성).
- 분류와 동일한 월간 예산 버킷 공유. 예산 초과 503, 생성 실패 502(graceful).

### 3.7 게스트 데모
- `/guest` — 로그인 없이 시드 사용자(김지철)의 한 달 거래로 분류·라벨을 미리 체험.

---

## 4. API 레퍼런스

베이스: `https://api.spendlens.suim-app.store` · 인증 헤더: `Authorization: Bearer <access_token>` (게스트/인증 제외 모든 경로).

| 메서드 | 경로 | 설명 | 인증 |
|---|---|---|---|
| GET | `/healthz` | 헬스체크 `{"status":"ok"}` | — |
| POST | `/auth/signup` | 회원가입 + 자동 로그인 | — |
| POST | `/auth/login` | 로그인 | — |
| POST | `/auth/refresh` | access token 재발급(refresh 쿠키) | 쿠키 |
| POST | `/auth/logout` | 로그아웃(쿠키 무효화) | ✓ |
| GET | `/seed/transactions` | 게스트 데모 거래 | — |
| POST | `/transactions/upload` | 명세서 XLSX 업로드 → `{uploaded, skipped}` | ✓ |
| GET | `/transactions` | 거래 목록(month/category/search/limit/offset) | ✓ |
| GET | `/transactions/months` | 거래 있는 월 목록(DESC) | ✓ |
| PATCH | `/transactions/{id}` | 카테고리 오버라이드 | ✓ |
| PATCH | `/transactions/{id}/essential` | 필수/비필수 3-state 토글 | ✓ |
| GET | `/dashboard/summary` | 요약 지표(지출/수입/순저축/저축률) | ✓ |
| GET | `/dashboard/by-category` | 카테고리별 지출 | ✓ |
| GET | `/dashboard/cashflow-by-month` | 월별 지출 vs 수입(`last_n`) | ✓ |
| GET | `/dashboard/by-essential` | 필수/비필수 집계 | ✓ |
| GET | `/dashboard/top-merchants` | Top 가맹점(`limit`) | ✓ |
| GET | `/insights?month=YYYY-MM` | 캐시된 월간 인사이트(없으면 null) | ✓ |
| POST | `/insights/generate` | 인사이트 생성/재생성(`?force`, body `{month}`) | ✓ |

주요 에러 코드: `INVALID_CREDENTIALS`, `WEAK_PASSWORD`, `EMAIL_ALREADY_EXISTS`, `TOO_MANY_REQUESTS`, `INVALID_FILE_TYPE`, `NOT_FOUND`, `INVALID_MONTH_FORMAT`, `INVALID_LAST_N`, `BUDGET_EXCEEDED`(503), `INSIGHT_GENERATION_FAILED`(502).

---

## 5. 프론트엔드 (페이지 / 라우트)

| 경로 | 페이지 | 비고 |
|---|---|---|
| `/` | 랜딩 | Guest Demo / 로그인 진입 |
| `/guest` | 게스트 데모 | 로그인 없이 시드 거래 열람 |
| `/login`, `/signup` | 인증 | |
| `/app` | 내 거래 | 업로드 + 필터바(월/검색/카테고리) + 거래 리스트(카테고리·essential 토글) |
| `/dashboard` | 대시보드 | 월간 인사이트 + 지표 + 현금흐름·카테고리·필수/비필수 차트 + Top 가맹점 |

`/app`·`/dashboard`는 `ProtectedRoute`로 보호(부팅 시 토큰 재수화 후 판정). 서버 상태는 전부 TanStack Query(`lib/queries.ts`의 쿼리 키 팩토리 + useQuery/useMutation 훅)로 관리.

---

## 6. 주차별 변천 (sub-projects)

| 주차 | 테마 | 핵심 |
|---|---|---|
| **W1** | 스켈레톤 + 삼성카드 파서 | 모노레포·배포 파이프라인, 업로드/거래, 첫 배포 |
| **W2** | 다중 사용자 + LLM 분류 | 회원가입, Claude Haiku 분류, Redis 예산, 우리/하나 파서 |
| **W3** | 본인 모드 UI | 필터/검색/인라인 오버라이드, Tremor 대시보드 4위젯, 카테고리 14→19, 통장 룰북 |
| **W4** | 분석 고도화 | 월간 LLM 인사이트(+캐시), 입금/소득 분석, 필수/비필수 토글, B+ 대시보드 |
| **W5** | 프론트 UX | TanStack Query 전면 전환(캐시·낙관적 갱신·debounce), 부팅 시 인증 재수화 |

---

## 7. 운영 / 배포

- **웹**: main 푸시 시 Vercel 자동 배포.
- **API**: `apps/api/**` 변경 푸시 시 GitHub Actions(`Deploy API`) → GHCR 이미지 빌드 → Lightsail에서 `docker compose pull && up -d`. 컨테이너 기동 시 `alembic upgrade head` 자동 적용.
- **CI**: 모든 push/PR에서 web(build+test) + api(ruff+pytest) 실행.
- **환경변수(API)**: `DATABASE_URL`, `JWT_SECRET`, `WEB_ORIGIN`, `REDIS_URL`, `ADMIN_EMAIL`/`ADMIN_PASSWORD_HASH`, **`ANTHROPIC_API_KEY`**, `ANTHROPIC_MONTHLY_BUDGET_USD`. 운영은 Lightsail `/opt/spendlens/.env`.

---

## 8. 알려진 한계 / 후속

- **`ANTHROPIC_API_KEY`가 운영에 설정돼 있어야** LLM 분류·인사이트가 동작(미설정 시 분류는 룰북만, 인사이트는 502). `settings` 기본값이 placeholder라 미설정이 조용히 가려질 수 있음.
- `by-essential` 집계가 savings/transfer 출금을 "필수"로 분류(`ESSENTIAL_DEFAULTS`) — 의미 정의는 추후 검토.
- 웹 번들 ~1.1MB(gzip 320KB) — 코드 스플리팅 별도 과제.
- 미구현(carry-over): 추가 카드사 파서(현대/신한/국민 등), 가맹점 정규화, 사용자별 분류 학습, 비밀번호 재설정/이메일 인증(SMTP), PWA/모바일 푸시. 상세 `docs/retros/w3.md`.
