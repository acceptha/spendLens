# Design: spendLens W2 — 다중 사용자(회원가입) + LLM 카테고리 분류 + Redis 캐시 + 우리/하나 파서

작성일: 2026-05-13
저자: hattuping
상위 설계: `~/.gstack/projects/acceptha-spendLens/hattuping-main-design-20260428-152458.md`
선행 sub-project: `docs/superpowers/specs/2026-04-29-w1-skeleton-and-samsung-xlsx-parser-design.md`
범위: spendLens 두 번째 sub-project (Week 2) — 2026-05-13 ~ 2026-05-27 (2주)
상태: DRAFT — 사용자 리뷰 후 writing-plans로 implementation plan 작성 예정

**변경 이력**
- 2026-05-13 v1: 초안. 7개 의사결정(즉시 가입 / 룰북 우선 / 전역 캐시 / 우리·하나 본인 명세서 보유 / feature 브랜치 + squash / 2주 일정 / $5 월간 상한) 반영.

---

## 1. Goal

W1에서 만든 **단일 사용자 + 삼성카드 XLSX** MVP를 다음으로 확장한다:

1. **다중 사용자**: ENV seed 단일 계정에서 벗어나, 누구나 이메일+비번으로 즉시 회원가입해 본인 가계부를 가질 수 있다.
2. **카테고리 자동 분류**: W1의 8줄짜리 키워드 룰을 정식 룰북으로 확장하고, 미매칭 가맹점은 **Claude Haiku**로 분류해 `transactions.category`에 저장한다.
3. **Redis 캐시**: LLM 분류 결과를 전역(`merchant_name → category`)으로 캐싱해 동일 가맹점 재호출을 방지한다.
4. **카드사 2종 추가**: 우리카드 · 하나카드 XLSX 명세서를 삼성과 동일한 흐름으로 업로드 가능하게 한다.
5. **PR 흐름 도입**: W1까지 main 직접 커밋이었으나, W2부터 feature 브랜치 → PR squash merge로 전환해 포트폴리오 PR 히스토리를 만든다.

이 단위가 끝나면:
- spendlens.suim-app.store/signup으로 **타인이 본인 계정을 만들어** 본인 명세서를 업로드해볼 수 있다.
- 거래 리스트에 **카테고리 칩**이 표시된다 (커피, 점심, 교통 등).
- Anthropic 월간 비용이 $5를 넘지 않는다 (초과 시 503).
- 우리/하나 카드 사용자도 데모 가능하다 (실제 본인 명세서 익명화 fixture 기반).

대시보드 시각화, 월별 리포트, 예산 설정, 비밀번호 재설정/이메일 인증, PWA는 모두 W3 이후로 미룬다 (§9 참조).

## 2. Done 체크리스트

> spec 작성 시점(2026-05-13)에는 어느 것도 동작하지 않는 것이 정상이다.

- [ ] [W2 완료 시] `https://spendlens.suim-app.store/signup` — 이메일+비번 입력 → `POST /auth/signup` → 즉시 자동 로그인 → `/app` 진입
- [ ] [W2 완료 시] 동일 이메일 재가입 시 `409 EMAIL_ALREADY_EXISTS`
- [ ] [W2 완료 시] 비밀번호 정책(최소 8자 + 영문/숫자 혼합) 미달 시 `400 WEAK_PASSWORD`
- [ ] [W2 완료 시] `/auth/signup` 또는 `/auth/login` 동일 IP에서 시간당 6회째 요청 시 `429 TOO_MANY_REQUESTS` + `Retry-After` 헤더
- [ ] [W2 완료 시] 업로드된 거래에 `category` 필드가 채워져 응답 (NULL/`unknown` 비율 ≤ 10%)
- [ ] [W2 완료 시] 룰북 매칭 가맹점은 LLM 호출 없이 즉시 분류 (Redis 미적중도 LLM 미호출)
- [ ] [W2 완료 시] 룰북 미매칭 가맹점 → Redis 캐시 hit이면 캐시값 사용, miss면 Claude Haiku 호출 후 결과를 Redis에 영구 저장
- [ ] [W2 완료 시] 동일 가맹점 두 번째 업로드 시 Anthropic API 호출 카운트가 증가하지 않음 (캐시 hit)
- [ ] [W2 완료 시] `ANTHROPIC_MONTHLY_BUDGET_USD` 도달 시 신규 LLM 호출은 `503 LLM_BUDGET_EXHAUSTED`, 업로드 자체는 성공(분류 안 된 거래는 `unknown`으로 저장)
- [ ] [W2 완료 시] 우리카드 XLSX 업로드 → 정상 파싱 + 카테고리 분류 + dedup
- [ ] [W2 완료 시] 하나카드 XLSX 업로드 → 정상 파싱 + 카테고리 분류 + dedup
- [ ] [W2 완료 시] 카드사 dispatch: 업로드 시 파일 헤더 시그니처로 삼성/우리/하나 자동 식별 (사용자가 카드사 선택 안 함)
- [ ] [W2 완료 시] W2 PR 최소 5건이 main에 squash merge된 흔적 (signup, redis, rulebook, llm, woori, hana 각각 분리)
- [ ] [W2 완료 시] README의 Tech Stack에 Redis + Anthropic 추가, Status가 "W2 complete"로 갱신

## 3. Decisions

| 영역 | 결정 | 근거 |
|---|---|---|
| 회원가입 검증 | **즉시 가입** (이메일 인증 없음) | SMTP/외부 의존성 회피. 포트폴리오 데모 목적상 충분. 이메일 인증·재설정은 W3+ |
| 비밀번호 정책 | 최소 8자 + 영문 1자 이상 + 숫자 1자 이상 | argon2id 해시는 W1 그대로 |
| Seed 사용자 보존 | `ADMIN_EMAIL` 단일 사용자는 lifespan seed 유지 | 기존 본인 로그인 흐름 깨지 않음 |
| 카테고리 분류 흐름 | **룰북 우선 → 미매칭만 LLM** | 비용 최소·결정적·테스트 가능 |
| 룰북 구조 | `apps/api/app/categorization/rulebook.py` — `list[tuple[pattern, category]]` 형식 + 정규식 지원 | W1 `simple_rules.py`를 그대로 흡수·확장 |
| 카테고리 enum | `coffee / lunch / dinner / snack_late / groceries / transport / telecom / subscription / entertainment / health / shopping / utilities / etc / unknown` (14개) | LLM hallucination 방지. JSON mode + enum 제약 |
| LLM 모델 | **Claude Haiku** (`claude-haiku-4-5-20251001`) | 분류는 작은 모델로 충분. CLAUDE.md 가이드 따름 |
| LLM 캐시 키 | **전역**: `category:v1:{normalized_merchant_name}` | 모든 사용자 공유, cold-start 최소화. 개인화는 W3+ user override로 |
| 캐시 정규화 | 소문자 + 공백 정리 + 가맹점 접미사 제거(`(주)`, `점`, `1호점` 등) | hit rate ↑ |
| Redis 운영 | Lightsail docker-compose에 `redis:7-alpine` 추가 (named volume `redis_data`, 외부 포트 비공개) | postgres/api와 동일 패턴 |
| 비용 가드레일 | **월간 상한 $5/mo** (`ANTHROPIC_MONTHLY_BUDGET_USD`) + Redis에 누적 비용 기록, 초과 시 `503 LLM_BUDGET_EXHAUSTED` | 매월 1일 KST 00:00에 카운터 리셋 |
| 비용 추적 단위 | LLM 호출 1건당 `input_tokens * input_price + output_tokens * output_price` 합산 | Anthropic 응답의 `usage` 객체 사용 |
| 카드사 dispatch | 파일 첫 시트의 헤더 패턴 매칭으로 자동 선택 (`parsers/registry.py`) | 사용자가 카드사 선택 안 함. 식별 실패 시 `400 UNKNOWN_CARD_FORMAT` |
| 우리/하나 파서 의존성 | W1과 동일 (`pandas` + `openpyxl`) | 신규 의존성 없음 |
| 우리/하나 fixture | 본인 실제 명세서 → 익명화 스크립트로 변환 → `tests/fixtures/woori-sample.xlsx`, `hana-sample.xlsx` | W1 삼성 fixture 패턴과 동일 |
| 브랜치/PR 흐름 | **feature 브랜치 → PR squash merge** | 포트폴리오 PR 히스토리. self-review 강제 |
| PR 단위 | 모듈/Phase 1개 = PR 1개 (최소 6 PR: signup / redis / rulebook / llm / woori / hana) | reviewer 부담 ↓, revert 용이 |
| W2 기간 | 2026-05-13 ~ 2026-05-27 (2주) | 외부 의존성 추가 있어 W1보다 보수적 |
| Rate limiting | `/auth/signup`, `/auth/login` 모두 **IP 기준 5회/시간** Redis 카운터 | 다중 사용자 가입 개방 시 스팸 가입·brute-force login 방지. Redis 이미 들어오므로 추가 인프라 0 |
| Rate limit 키 형식 | `ratelimit:{endpoint}:{ip}:{YYYYMMDDHH}` — TTL 3600s | 시간 단위 sliding은 W3+에서 검토 (현재 fixed window로 충분) |
| Rate limit 응답 | `429 TOO_MANY_REQUESTS` + `Retry-After` 헤더 (다음 시간까지 남은 초) | 표준 HTTP. 클라이언트가 자동 백오프 가능 |

## 4. Architecture

W1 다이어그램에서 **Redis 컨테이너**, **Anthropic API 외부 호출**, **/signup 엔드포인트**가 추가된다.

```
┌─────────────────┐
│   사용자 브라우저  │
└────────┬────────┘
         │ HTTPS
         │
         ├──► spendlens.suim-app.store ──► Vercel (web)
         │      /signup  /login  /app  /guest
         │
         │
         ├──► api.spendlens.suim-app.store ──► ┌─────────────────────────┐
         │                                     │ Lightsail VPS           │
         │                                     │ ┌─────────┐             │
         │                                     │ │ Caddy   │ TLS         │
         │                                     │ └────┬────┘             │
         │                                     │      │                  │
         │                                     │ ┌────▼────────────┐     │
         │                                     │ │ FastAPI         │     │
         │                                     │ │ + pandas        │     │
         │                                     │ │ + openpyxl      │     │
         │                                     │ │ + anthropic SDK │     │
         │                                     │ │ + redis-py      │     │
         │                                     │ └──┬──────────┬──┘     │
         │                                     │    │          │         │
         │                                     │    │ asyncpg  │ aioredis│
         │                                     │    ▼          ▼         │
         │                                     │ ┌────────┐ ┌────────┐  │
         │                                     │ │postgres│ │ redis  │  │
         │                                     │ │ :16    │ │ :7     │  │
         │                                     │ └────────┘ └────────┘  │
         │                                     └─────────┬───────────────┘
         │                                               │
         │                                               │ HTTPS (cache miss only)
         │                                               ▼
         │                                     ┌──────────────────┐
         │                                     │ api.anthropic.com│
         │                                     │ Claude Haiku     │
         │                                     └──────────────────┘
         │
         ├── POST /auth/signup {email, password}
         │     → 비번 정책 검증 → argon2 해시 → users INSERT
         │     → 즉시 /auth/login 동일 로직 실행 → access JWT + refresh cookie
         │
         └── POST /transactions/upload (multipart .xlsx)
               → parsers/registry.py — 헤더 시그니처로 삼성/우리/하나 선택
               → 파싱 → 거래 리스트 추출
               → categorization.classify(merchant_raw)
                   1) rulebook 매칭 → 즉시 반환
                   2) Redis GET category:v1:{normalized}
                       2-a) hit → 반환
                       2-b) miss → 월 예산 확인 → Haiku 호출 → Redis SET (영구) → 반환
                       2-c) 예산 초과 → "unknown" 반환 (저장은 성공)
               → transactions INSERT (category 포함)
               → 응답
```

**구성 요소 변경**:
- **Backend**: `anthropic` (Python SDK), `redis` (asyncio 클라이언트) 의존성 추가. `httpx` 등 W1 의존성 유지.
- **DB**: 신규 테이블 `llm_usage_log`. `transactions` 컬럼 변경 없음 (W1에 이미 `category` TEXT 존재).
- **Redis**: 캐시 + 비용 카운터 둘 다 보관. AOF 활성화 (`appendonly yes`)로 캐시 영속.
- **Caddyfile**: 변경 없음. Redis는 외부 노출 없음.

## 5. Components / 디렉토리 구조

W2가 끝났을 때의 `apps/api/app/` 구조:

```
apps/api/app/
├── main.py                      # 변경: signup 라우터 등록, lifespan에 redis 풀 추가
├── db.py                        # 무변경
├── settings.py                  # 변경: ANTHROPIC_API_KEY, ANTHROPIC_MONTHLY_BUDGET_USD, REDIS_URL 추가
├── redis_client.py              # 신규: aioredis 풀 헬퍼 (db.py와 동일 패턴)
├── common/                      # 신규 공통 모듈
│   ├── __init__.py
│   └── rate_limit.py            # 신규: Redis 기반 IP rate limiter (signup/login에서 호출)
├── auth/
│   ├── routes.py                # 변경: POST /auth/signup 추가, login/signup 진입 시 rate_limit.check
│   ├── schemas.py               # 변경: SignupRequest 추가
│   ├── password.py              # 변경: 정책 검증 함수 추가 (validate_password_policy)
│   ├── seed.py                  # 무변경 (단일 ENV admin 유지)
│   ├── deps.py / jwt.py         # 무변경
├── transactions/
│   ├── routes.py                # 변경: 업로드 후 categorization.classify 호출
│   ├── schemas.py               # 무변경 (category 필드 이미 있음)
│   └── service.py               # 변경: insert_transactions에 category 인자
├── categorization/              # 신규 모듈 (도메인)
│   ├── __init__.py
│   ├── rulebook.py              # 정규식 기반 룰북 (W1 simple_rules.py 흡수·확장)
│   ├── service.py               # classify() = rulebook → cache → llm
│   ├── llm.py                   # Claude Haiku 호출 + JSON enum 제약
│   ├── cache.py                 # Redis get/set + merchant_name 정규화
│   └── budget.py                # 월간 비용 누적·체크
├── parsers/
│   ├── __init__.py
│   ├── registry.py              # 신규: 헤더 시그니처 → 파서 선택
│   ├── samsung_card.py          # 무변경
│   ├── woori_card.py            # 신규
│   ├── hana_card.py             # 신규
│   └── simple_rules.py          # 삭제 → categorization/rulebook.py로 이관
└── seed/
    ├── routes.py / kim_jichul.py # 무변경
```

신규 테스트 디렉토리:
- `tests/auth/test_signup.py`
- `tests/categorization/` (rulebook, cache, llm 모킹, budget)
- `tests/parsers/test_woori_card.py`, `test_hana_card.py`, `test_registry.py`

## 6. Data Model

### 6-A. `users` 테이블 — 변경 없음
W1에서 이미 `id, email, password_hash, created_at` 있음. 회원가입은 INSERT만 추가.

### 6-B. 신규 테이블 — `llm_usage_log`

월간 비용 cap 계산을 위해 매 LLM 호출의 토큰 사용량을 저장한다. Redis 누적값은 빠른 조회용이고 이 테이블은 감사/리포팅용.

```sql
CREATE TABLE llm_usage_log (
    id BIGSERIAL PRIMARY KEY,
    called_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    model TEXT NOT NULL,
    input_tokens INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cost_usd NUMERIC(10, 6) NOT NULL,
    purpose TEXT NOT NULL,        -- 'categorize' (W2 단일 용도)
    merchant_normalized TEXT      -- 디버깅용
);

CREATE INDEX llm_usage_log_called_at_idx ON llm_usage_log (called_at);
```

> 카테고리 캐시는 **Redis만** 사용 (별도 DB 테이블 없음). 이유: 재기동 시에도 AOF로 복구되고, 캐시 무효화·TTL 조정이 쉽다. 캐시값이 사라져도 LLM 재호출하면 동일값 재구성 가능.

### 6-C. `transactions.category` — 무변경
이미 W1 마이그레이션에 `category TEXT` 컬럼 존재. W1에서는 `simple_rules.classify`가 채웠고, W2에서는 동일 컬럼에 새 분류 흐름 결과를 채운다.

### 6-D. 마이그레이션 파일
- `0002_add_llm_usage_log.py` — 위 테이블 생성. raw SQL `op.execute(...)` 사용.

## 7. Data Flow

### 7-A. 회원가입 흐름

```
POST /auth/signup {email, password}
  │
  ├─ rate_limit.check(endpoint="signup", ip=request.client.host, max=5, window_s=3600)
  │    초과 → 429 TOO_MANY_REQUESTS (+ Retry-After 헤더)
  │
  ├─ Pydantic SignupRequest: EmailStr + min_length=8
  │
  ├─ validate_password_policy(password)
  │    실패 → 400 WEAK_PASSWORD
  │
  ├─ INSERT INTO users (email, password_hash, created_at) VALUES (..., argon2($1), now())
  │    UNIQUE 충돌 → 409 EMAIL_ALREADY_EXISTS
  │
  ├─ 자동 로그인: auth.routes._issue_tokens(user_id)
  │    → access JWT + refresh row INSERT + Set-Cookie
  │
  └─ 200 OK {access_token, user: {id, email}}
```

`/auth/login`도 동일한 rate_limit.check를 진입 직후 적용 (endpoint="login"). 성공/실패 무관 시도 횟수로 카운트하여 brute-force 탐색 자체를 차단한다. 카운터는 **시도 시점에 1 증가**하며, 가입/로그인 성공 시에도 감소시키지 않는다 (정상 사용자는 시간당 5회를 넘지 않음).

`rate_limit` 모듈 위치: `apps/api/app/common/rate_limit.py` (신규). FastAPI Depends 패턴이 아니라, 라우터 함수 안에서 직접 호출 — W1의 "Depends는 인증에만" 규칙(CLAUDE.md §5) 준수.

```python
# 슈도코드
async def check(endpoint: str, ip: str, max: int, window_s: int) -> None:
    bucket = datetime.utcnow().strftime("%Y%m%d%H")
    key = f"ratelimit:{endpoint}:{ip}:{bucket}"
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, window_s)
    if count > max:
        ttl = await redis.ttl(key)
        raise HTTPException(
            status_code=429,
            detail="TOO_MANY_REQUESTS",
            headers={"Retry-After": str(max(ttl, 1))},
        )
```

IP는 `request.client.host`로 추출하되, Caddy reverse proxy 뒤이므로 `X-Forwarded-For` 첫 토큰을 신뢰할지 결정 필요 — Caddy가 항상 셋팅하면 spoofing 불가하므로 사용 OK (plan 단계에서 Caddyfile 점검).

### 7-B. 업로드 + 분류 흐름

```
POST /transactions/upload (multipart)
  │
  ├─ parsers.registry.detect(file_bytes)
  │    └─ 각 파서의 `detect(header_row)` 호출, 첫 매칭 반환
  │       실패 → 400 UNKNOWN_CARD_FORMAT
  │
  ├─ parser.parse(file_bytes) → list[TransactionIn]  (category 미지정)
  │
  ├─ for tx in items:
  │    tx.category = await categorization.classify(tx.merchant_raw)
  │
  ├─ insert_transactions(conn, user_id, items)  (dedup_hash UNIQUE로 멱등)
  │
  └─ 200 OK {inserted: N, skipped_duplicate: M, ...}
```

### 7-C. categorization.classify 내부

```python
async def classify(merchant_raw: str) -> str:
    # 1. 룰북
    cat = rulebook.match(merchant_raw)
    if cat:
        return cat

    # 2. Redis 캐시
    key = cache.make_key(merchant_raw)
    cached = await cache.get(key)
    if cached:
        return cached

    # 3. 예산 체크
    if not await budget.has_room():
        return "unknown"

    # 4. LLM 호출
    try:
        cat = await llm.classify_one(merchant_raw)
    except (anthropic.APIError, asyncio.TimeoutError):
        return "unknown"

    # 5. 캐시 + 사용량 기록
    await cache.set(key, cat)
    await budget.record_usage(...)
    return cat
```

### 7-D. 룰북 매칭 — `rulebook.py`

W1 `simple_rules.py`를 흡수하면서 정규식·우선순위·카테고리 enum 검증 추가:

```python
# (regex, category) — 위에서부터 첫 매칭
_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"스타벅스|이디야|투썸|할리스|starbucks|coffee bean", re.I), "coffee"),
    (re.compile(r"김밥천국|맘스터치|롯데리아|맥도날드|버거킹", re.I), "lunch"),
    ...
]
```

W2에서 룰북은 50~80개 룰까지 확장 (실제 사용자 본인 데이터 패턴 기반).

### 7-E. LLM 호출 — `llm.py`

Claude Haiku를 JSON mode로 호출하고 응답에서 카테고리만 추출:

```python
SYSTEM = """당신은 한국 가계부 거래 분류기입니다.
가맹점명을 받아 다음 14개 카테고리 중 정확히 하나를 JSON으로 반환합니다.
{coffee, lunch, dinner, snack_late, groceries, transport, telecom,
 subscription, entertainment, health, shopping, utilities, etc, unknown}
"""

# response_format: tool_use with enum schema
```

응답이 enum 밖의 값이면 `"unknown"`으로 fallback.

### 7-F. 비용 가드레일 — `budget.py`

```
KEY: llm_budget:{YYYY-MM} → float (누적 비용 USD)

has_room():
    cur = await redis.get(f"llm_budget:{this_month()}") or 0.0
    return cur < settings.anthropic_monthly_budget_usd

record_usage(input_t, output_t):
    cost = input_t * 0.80/1e6 + output_t * 4.00/1e6   # Haiku 가격
    await redis.incrbyfloat(f"llm_budget:{this_month()}", cost)
    await db: INSERT INTO llm_usage_log ...
```

매월 1일 KST 00:00에 자동 리셋 (키 이름에 `YYYY-MM`이 들어가므로 자연스럽게 새 키 사용).

## 8. Error Handling

W1 패턴 유지 — 라우터에서 `HTTPException` 직접 raise. detail은 UPPER_SNAKE_CASE 코드.

| 코드 | HTTP | 발생 위치 |
|---|---|---|
| `EMAIL_ALREADY_EXISTS` | 409 | /auth/signup — users.email UNIQUE 충돌 |
| `WEAK_PASSWORD` | 400 | /auth/signup — 비번 정책 미달 |
| `TOO_MANY_REQUESTS` | 429 | /auth/signup, /auth/login — IP 기준 시간당 5회 초과. `Retry-After` 헤더 포함 |
| `UNKNOWN_CARD_FORMAT` | 400 | /transactions/upload — registry detect 실패 |
| `LLM_BUDGET_EXHAUSTED` | (HTTP 안 됨) | 분류 단계에서 silent fallback → category="unknown" |
| `LLM_TIMEOUT` | (HTTP 안 됨) | 분류 단계에서 silent fallback → category="unknown" |

LLM 실패는 사용자 흐름을 끊지 않는다. 분류 안 된 거래는 `unknown`으로 저장되고, 사용자는 추후(W3 user-override 도입 시) 직접 분류 가능.

## 9. Out of Scope (W3+ 명시 이관)

- 대시보드 시각화 (월별/카테고리별 차트)
- 월별 리포트 PDF 생성
- 예산 설정 + 알림
- 비밀번호 재설정 / 이메일 인증 / SMTP 통합
- 사용자별 카테고리 오버라이드 (W3에서 user-specific override 테이블)
- 다른 카드사 (현대, 신한, 국민, 롯데, BC, NH 등)
- 통장/체크카드 거래 (W4+ 은행 명세서)
- PDF 명세서 파싱
- 다크 모드, 다국어, PWA
- 회원 탈퇴 / GDPR 데이터 export

## 10. Testing 전략

W1 conftest(`tests/conftest.py`)의 session-scoped `test_db_pool` + `TRUNCATE CASCADE` 패턴 유지.

신규 픽스처:
- `test_redis_pool` — session-scoped fakeredis 또는 별도 docker redis (DB index 분리)
- `mock_anthropic` — `anthropic.AsyncAnthropic` 자동 패치, fixture로 응답 주입 가능
- `tests/fixtures/woori-sample.xlsx`, `hana-sample.xlsx` — 익명화 본인 명세서

테스트 우선순위:
1. **categorization 단위 테스트** — rulebook(매칭/미매칭), cache(get/set/정규화), llm(JSON 파싱/enum 위반/timeout), budget(누적/cap)
2. **회원가입 통합 테스트** — 신규/중복/약한 비번/즉시 로그인 가능
3. **rate limit 단위 테스트** — `common/rate_limit.py` — 5회까진 통과, 6회째 429 + Retry-After, 시간 경과 후 리셋 (Redis TTL 모킹)
4. **rate limit 통합 테스트** — `/auth/signup` 6회 연속 호출 시 마지막만 429, `/auth/login` 동일, IP 다르면 카운터 독립
5. **registry 단위 테스트** — 삼성/우리/하나 헤더로 정확한 파서 반환, unknown 시 None
6. **우리/하나 파서 단위 테스트** — 헤더 자동 감지, 행 파싱, 취소/할부 처리, PAN 마스킹
7. **업로드 E2E** — 우리·하나 fixture 업로드 → 카테고리까지 채워진 응답 + LLM mock 호출 카운트 검증

LLM 통합 테스트에서는 절대 실제 Anthropic API를 호출하지 않는다. CI 환경변수에 `ANTHROPIC_API_KEY=test-fake`.

## 11. ENV 키 명세

`.env.example` 추가:
```
# W2 추가
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MONTHLY_BUDGET_USD=5.0
REDIS_URL=redis://redis:6379/0
```

`apps/api/.env` (로컬 개발) 추가:
```
ANTHROPIC_API_KEY=sk-ant-...               # 실키
ANTHROPIC_MONTHLY_BUDGET_USD=1.0           # 로컬은 더 낮게
REDIS_URL=redis://localhost:6379/0         # docker-compose.local 통해
```

`/opt/spendlens/.env` (Lightsail) — 운영 실키 + `$5`.

`settings.py`에 `Settings` 필드 추가:
```python
anthropic_api_key: str
anthropic_monthly_budget_usd: float = 5.0
redis_url: str
```

## 12. CI/CD 워크플로 (요약)

W1과 동일하지만 **PR 흐름** 추가:

- `.github/workflows/api.yml` — push 외에 **pull_request** 트리거 추가. 동일하게 ruff + pytest. **Redis 서비스 컨테이너 추가** (`services: redis: image: redis:7-alpine`).
- `.github/workflows/web.yml` — pull_request 트리거 추가.
- `.github/workflows/deploy-api.yml` — `on: push: branches: [main]` 유지. PR에서는 deploy 안 함. squash merge로 main에 떨어진 시점에만 트리거.
- 신규 `.github/PULL_REQUEST_TEMPLATE.md` — Summary / Why / Test plan / Screenshots / Checklist.

Lightsail `docker-compose.prod.yml` 변경:
- `redis: redis:7-alpine` 서비스 추가, `appendonly yes`, named volume `redis_data`
- `api` 서비스의 `environment`에 `REDIS_URL=redis://redis:6379/0`, `ANTHROPIC_API_KEY`, `ANTHROPIC_MONTHLY_BUDGET_USD` 주입
- `api`의 `depends_on`에 `redis` 추가

## 13. W2 검수 시나리오 (PR 5건 머지 후)

1. `/signup`에서 새 이메일로 가입 → 자동 로그인 → 본인 명세서 업로드 → 거래에 카테고리 칩 표시
2. 동일 이메일로 재가입 → 409
3. 비번 `1234` → 400 WEAK_PASSWORD
4. 우리카드 XLSX 업로드 → 정상 카테고리 분류
5. 하나카드 XLSX 업로드 → 정상 카테고리 분류
6. 동일 우리카드 XLSX 재업로드 → 모두 dedup skip + Anthropic 호출 0건 (캐시 hit)
7. Lightsail에 SSH → `docker compose exec redis redis-cli GET llm_budget:2026-05` → 0보다 큰 값 확인
8. W2 동안 main에 squash merge된 PR 6개 이상 (Conventional Commits 제목)

## 14. Open Items (plan 단계에서 해결)

- [ ] 우리/하나 명세서의 정확한 헤더 행 패턴 (실제 파일 열어 확인 필요)
- [ ] 우리/하나 dedup 키 — 삼성처럼 "승인번호" 컬럼이 있는지, 없으면 fallback 키 정의
- [ ] 룰북 50~80개 룰 — 사용자 본인 명세서의 실제 가맹점 빈도 분석 후 작성
- [ ] Redis 캐시 정규화 함수의 구체 규칙 (어디까지 통합할 것인지)
- [ ] `mock_anthropic` 픽스처 구현 방식 (`respx`처럼 HTTP 레벨 모킹 vs SDK 모킹)
- [ ] LLM 응답 enum 위반 시 재시도 1회 할지 vs 즉시 unknown
- [ ] Caddyfile에 `X-Forwarded-For` 셋팅이 이미 들어있는지 확인 (없으면 추가) — rate limit IP 추출 신뢰성

## 15. Next Step

1. 본 spec을 사용자가 리뷰 → 수정/승인.
2. `superpowers:writing-plans` 스킬로 `docs/superpowers/plans/2026-05-XX-w2-...-plan.md` 작성. Phase 단위:
   - Phase 0: 브랜치/PR 흐름 셋업 (PR 템플릿, web CI에 PR 트리거)
   - Phase 1: 회원가입 (POST /auth/signup + /signup 프론트)
   - Phase 2: Redis 컨테이너 + 클라이언트 + lifespan
   - Phase 3: categorization 모듈 (rulebook → cache → budget) + W1 simple_rules.py 제거
   - Phase 4: Claude Haiku 통합 + 모킹 + 비용 cap
   - Phase 5: parsers/registry.py + 우리카드 파서 + fixture
   - Phase 6: 하나카드 파서 + fixture
   - Phase 7: E2E 검수 + README/CHANGELOG 갱신
3. 각 Phase = 1 PR. main으로 squash merge.
