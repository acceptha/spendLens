# Design: spendLens W1 — Skeleton + 삼성카드 XLSX 파서 + 첫 배포

작성일: 2026-04-29
저자: hattuping
상위 설계: `~/.gstack/projects/acceptha-spendLens/hattuping-main-design-20260428-152458.md`
범위: spendLens 4-5주 풀스택 프로젝트의 첫 번째 sub-project (Week 1)
상태: DRAFT — 사용자 리뷰 후 writing-plans로 implementation plan 작성 예정

**변경 이력**:
- 2026-04-29 v1: 초안. 삼성카드 CSV 가정.
- 2026-04-29 v2: 삼성카드는 CSV 미제공, XLSX(`■ 국내이용내역` 시트)로 변경. PDF는 W2로 이관. dedup 키를 `승인번호` 기반으로 변경. `card_last4`/`approval_no` 컬럼 추가, PAN 마스킹 정책 명시.
- 2026-04-29 v3: dedup·신규 컬럼 근거를 §6/§7-D 본문 안에 풀어 설명. PDF 정책 톤 완화 (삼성 PDF 처리는 향후 필요 시 W2에 추가 가능). `installment_months` 일시불 표현을 0으로 명확화. is_canceled UI 처리 명확화.

---

## 1. Goal

spendLens 프로젝트의 **첫 출하 가능 단위**를 만든다. 라이브 URL이 인터넷에 떠 있고, 인증 없는 면접관이 5초 안에 게스트 모드 데모를 보고, 본인은 비번 로그인으로 들어가 실제 삼성카드 **XLSX** 명세서를 업로드해 거래 리스트로 보는 것까지를 W1으로 묶는다.

이 단위가 끝나면 다음 두 가지가 동시에 검증된다:
- **벽돌 한 장이 끝까지 도달함** (파일 업로드부터 DB 영속까지 풀스택 통과)
- **CI/CD 파이프라인이 동작함** (main push → 자동 배포)

LLM, 룰북, 차트, Sandbox 모드, 우리/하나 파서, **PDF 명세서 처리(필요 시 삼성 PDF 포함)**, 회원가입 흐름은 모두 W2 이후로 미룬다 (§9 참조).

## 2. Done 체크리스트

> 아래는 모두 **W1 작업이 끝났을 때** 만족해야 할 검수 조건이다. spec 작성 시점(2026-04-29)에는 어느 것도 동작하지 않는 것이 정상이다.

- [ ] [W1 완료 시] `https://spendlens.suim-app.store` 가 200 응답 (Vercel 배포)
- [ ] [W1 완료 시] `https://api.spendlens.suim-app.store/healthz` 가 200 응답 (Lightsail + Caddy + Let's Encrypt)
- [ ] [W1 완료 시] `/guest` — 인증 없이 시드(가짜 김지출) 거래 30~60건이 카테고리·essential_reason 코멘트와 함께 렌더
- [ ] [W1 완료 시] `/login` → `/auth/login` (이메일+비번) → access JWT 발급 + refresh httpOnly cookie
- [ ] [W1 완료 시] `/app` — 로그인 사용자만 진입 → 삼성카드 **XLSX** 업로드 → `■ 국내이용내역` 시트 파싱 → DB 저장 → 거래 리스트 표시
- [ ] [W1 완료 시] `samples/samsung-card-sample.xlsx` (사용자 본인의 실제 1주~1개월치) 1회 이상 무결 파싱 성공
- [ ] [W1 완료 시] 동일 XLSX 두 번 업로드 → 두 번째는 모두 dedup으로 skip (멱등, **승인번호 기준**)
- [ ] [W1 완료 시] `transactions.raw_row` JSONB의 카드번호가 `****-****-****-1234` 형태로 마스킹됨, `card_last4`엔 마지막 4자리만
- [ ] [W1 완료 시] `main` push 시 GitHub Actions가 lint + test → 통과 시 GHCR에 api 이미지 push → SSH로 Lightsail에서 `docker compose pull && up -d` 자동 실행
- [ ] [W1 완료 시] Vercel은 git 연동으로 web 자동 배포
- [ ] [W1 완료 시] README에 Live Demo 링크 + W1 범위 메모

## 3. Decisions (Round 1~3 합의 사항)

| 영역 | 결정 |
|---|---|
| Sub-project 분해 | 5개 (W1~W5), 본 문서는 W1 |
| Web 호스팅 | Vercel (apps/web 자동 배포) |
| API 호스팅 | AWS Lightsail Instance (Ubuntu LTS, $5~$10 플랜) + Docker Compose + Caddy reverse proxy + Let's Encrypt |
| 모노레포 | pnpm workspaces (apps/web + packages/parser-shared). apps/api는 독립 Python 프로젝트(uv 관리) |
| DB | Supabase Postgres (Tokyo 리전, 무료 티어). **Postgres 기능만** 사용. Auth/Storage/Realtime 미사용 |
| 인증 | FastAPI 자체 구현. 비번(argon2id) + JWT(HS256, access 15m + refresh 7d httpOnly cookie). **W1엔 ENV seed 단일 사용자**, 회원가입/리셋/SMTP는 W2 |
| W1 파서 형식 | **삼성카드 XLSX** 한 종류. `■ 국내이용내역` 시트만 처리. 인코딩 이슈 없음(XLSX는 binary) |
| W1 파서 의존성 | `pandas` + `openpyxl` |
| 시드 페르소나 | 30대 서울 직장인 1인 가구 (김지출). 6개월치 30~60건. essential_reason 사람이 미리 채움 |
| W1 카테고리 처리 | 5~10개 키워드 매핑 룰만 (스타벅스→커피, 김밥천국→식비 등). 본격 룰북·LLM은 W2 |
| dedup 키 | `sha256(user_id + source_type + 승인번호)`. 승인번호가 비어 있으면 fallback `sha256(user_id + source_type + "fb:" + date + amount + merchant_raw)` |
| 카드번호 처리 | 파싱 시 즉시 마스킹. `card_last4`(TEXT, 4자) 컬럼에 마지막 4자리만 보존. `raw_row` JSONB의 카드번호 키도 `****-****-****-NNNN`으로 저장 |
| 도메인 | `suim-app.store` (가비아). 서브도메인: `spendlens.suim-app.store` (web), `api.spendlens.suim-app.store` (api) |
| CI/CD | GitHub Actions: lint+test 매트릭스 → GHCR 이미지 push → SSH로 `docker compose pull && up -d`. Vercel은 git 연동 |

## 4. Architecture

```
┌─────────────────┐                              ┌──────────────────────┐
│   사용자 브라우저  │                              │   GitHub (main)      │
└────────┬────────┘                              └──────────┬───────────┘
         │                                                   │ push
         │ HTTPS                                             ▼
         │                                          ┌────────────────┐
         │                                          │ GitHub Actions │
         │                                          │ - lint/test    │
         │                                          │ - build image  │
         │                                          │ - push to GHCR │
         │                                          │ - ssh deploy   │
         │                                          └────┬─────┬─────┘
         │                                               │     │
         │                                       deploy ▼      ▼ Vercel git 연동
         │                                ┌─────────────────┐ ┌────────────────┐
         ├──► spendlens.suim-app.store ──►│ Vercel (web)    │ │ (apps/web 빌드)│
         │                                └────────┬────────┘ └────────────────┘
         │                                         │
         │                                         │ JWT (Bearer)
         │                                         ▼
         ├──► api.spendlens.suim-app.store ──► ┌────────────────┐
         │                                     │ Lightsail VPS  │
         │                                     │ ┌────────────┐ │
         │                                     │ │ Caddy      │ │  TLS + reverse proxy
         │                                     │ └─────┬──────┘ │
         │                                     │       │        │
         │                                     │ ┌─────▼──────┐ │
         │                                     │ │ FastAPI    │─┼──► Supabase Postgres
         │                                     │ │ + pandas   │ │    (Tokyo, asyncpg)
         │                                     │ │ + openpyxl │ │
         │                                     │ └────────────┘ │
         │                                     └────────────────┘
         │
         ├── POST /auth/login {email, password} ──► FastAPI ──► users (argon2 검증)
         │                          ◄── access JWT(15m) + refresh cookie(7d) ─
         │
         └── POST /auth/refresh (httpOnly cookie) ──► FastAPI ──► refresh_tokens 회전
```

**구성 요소**:
- **Frontend**: Vercel(apps/web). Vite + React + TS. axios + 401 시 refresh interceptor.
- **Backend**: Lightsail Instance 1대. `docker compose`로 `caddy` + `api` 두 컨테이너만. Postgres는 외부 위임.
- **DB**: Supabase Postgres. FastAPI는 `asyncpg`로 connection string 접속. Supabase 전용 SDK 미사용.
- **Parser**: `apps/api`에 `pandas` + `openpyxl` 의존성. XLSX는 binary 포맷이라 인코딩 자동 감지 불필요.
- **Secrets**: Lightsail 인스턴스의 `/opt/spendlens/.env` (root 600 권한). Git에 절대 미포함.

**Caddyfile** (예시):
```Caddyfile
api.spendlens.suim-app.store {
    reverse_proxy api:8000
    encode gzip zstd
    log {
        output file /var/log/caddy/access.log
        format json
    }
}
```

## 5. Components / 디렉토리 구조

```
spendlens/
├── apps/
│   ├── web/                        # Vite + React + TS (pnpm workspace)
│   │   ├── src/
│   │   │   ├── routes/
│   │   │   │   ├── index.tsx       # 랜딩 (W1엔 minimal, W4 본격)
│   │   │   │   ├── guest.tsx       # 게스트 모드: 시드 거래 리스트
│   │   │   │   ├── login.tsx       # /auth/login 폼
│   │   │   │   └── app.tsx         # 본인 모드 (보호): 업로드 + 거래 리스트
│   │   │   ├── lib/
│   │   │   │   ├── api.ts          # axios 인스턴스 + refresh interceptor
│   │   │   │   ├── auth.ts         # 토큰 보관/검증/로그아웃
│   │   │   │   └── upload.ts       # multipart .xlsx 업로드 helper
│   │   │   ├── stores/auth.ts      # Zustand: 토큰/유저 상태
│   │   │   ├── components/
│   │   │   │   ├── TransactionList.tsx
│   │   │   │   ├── UploadDropzone.tsx   # accept=".xlsx" only
│   │   │   │   └── ProtectedRoute.tsx
│   │   │   └── main.tsx
│   │   ├── package.json
│   │   ├── vite.config.ts
│   │   └── tsconfig.json
│   │
│   └── api/                        # FastAPI (uv, 독립 Python 3.12)
│       ├── pyproject.toml          # pandas, openpyxl, asyncpg, argon2-cffi, pyjwt, ...
│       ├── Dockerfile
│       ├── app/
│       │   ├── main.py             # FastAPI 앱, lifespan(seed_admin_user), CORS
│       │   ├── settings.py         # pydantic-settings, .env 로드
│       │   ├── db.py               # asyncpg pool (Supabase)
│       │   ├── auth/
│       │   │   ├── routes.py       # /auth/login, /refresh, /logout
│       │   │   ├── jwt.py          # HS256 발급/검증 (JWT_SECRET)
│       │   │   ├── password.py     # argon2id 해시/검증
│       │   │   └── deps.py         # current_user 의존성
│       │   ├── transactions/
│       │   │   ├── routes.py       # POST /transactions/upload, GET /transactions
│       │   │   ├── service.py      # 업로드 처리, dedup, 저장
│       │   │   └── schemas.py      # Pydantic 모델
│       │   ├── parsers/
│       │   │   ├── __init__.py     # registry: source_type → parser
│       │   │   ├── samsung_card.py # XLSX 파서 (■ 국내이용내역 시트)
│       │   │   └── simple_rules.py # 5~10개 키워드 → 카테고리 매핑
│       │   ├── seed/
│       │   │   ├── routes.py       # GET /seed/transactions (공개)
│       │   │   └── kim_jichul.py   # seed/kim_jichul/transactions.json 로드
│       │   └── migrations/         # Alembic
│       └── tests/
│           ├── parsers/test_samsung_card.py
│           ├── auth/test_password.py
│           ├── auth/test_jwt.py
│           ├── auth/test_login.py
│           └── transactions/test_upload.py
│
├── packages/
│   └── parser-shared/              # TS, 카테고리 enum 공유 (W1엔 stub)
│       ├── src/categories.ts
│       └── package.json
│
├── seed/
│   └── kim_jichul/
│       └── transactions.json       # 30~60건 시드 (essential_reason 채움)
│
├── samples/                        # .gitignore (개인정보)
│   ├── .gitkeep
│   └── samsung-card-sample.xlsx    # 사용자 본인 다운로드 파일
│
├── infra/
│   ├── docker-compose.yml          # 로컬: api + (postgres-test optional)
│   ├── docker-compose.prod.yml     # Lightsail: caddy + api
│   ├── Caddyfile                   # api.spendlens.suim-app.store
│   ├── lightsail-bootstrap.sh      # 인스턴스 첫 셋업 스크립트
│   └── README.md                   # 배포·운영 메모
│
├── scripts/
│   ├── hash_password.py            # 비번 → argon2id 해시 (로컬에서 1회)
│   └── seed_db.py                  # (선택) 시드 DB INSERT
│
├── .github/workflows/
│   ├── ci.yml                      # lint + test (web matrix + api matrix)
│   └── deploy-api.yml              # build → GHCR push → ssh deploy
│
├── docs/superpowers/specs/         # 본 spec 위치
├── pnpm-workspace.yaml
├── package.json
├── .env.example                    # 모든 ENV 키 (값은 빈 칸) — git 포함
├── .gitignore
└── README.md
```

## 6. Data Model (Postgres, W1 범위만)

```sql
CREATE EXTENSION IF NOT EXISTS citext;
CREATE EXTENSION IF NOT EXISTS pgcrypto;  -- gen_random_uuid

-- 사용자: ENV seed로 1명 보장. W2에서 회원가입으로 확장 가능
CREATE TABLE users (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email         CITEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,                 -- argon2id
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 업로드된 명세서 메타 (파일 자체는 저장 안 함, 거래만 저장)
CREATE TABLE source_files (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id        UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  source_type    TEXT NOT NULL,                -- 'samsung_card_xlsx'
  filename       TEXT NOT NULL,
  rows_total     INTEGER NOT NULL,
  rows_inserted  INTEGER NOT NULL,
  rows_skipped   INTEGER NOT NULL,
  uploaded_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE transactions (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  source_file_id      UUID REFERENCES source_files(id) ON DELETE SET NULL,
  source_type         TEXT NOT NULL,           -- 'samsung_card_xlsx'

  -- 거래 핵심
  txn_date            DATE NOT NULL,           -- '승인일자'
  txn_time            TIME,                    -- '승인시각' (있으면 채움)
  amount              NUMERIC(12,2) NOT NULL,  -- '승인금액(원)'. 음수=환불
  merchant_raw        TEXT NOT NULL,           -- '가맹점명' 원본
  merchant_normalized TEXT,                    -- W2 룰북에서 채움

  -- 삼성카드 XLSX 특화
  approval_no         TEXT,                    -- '승인번호'. dedup 1순위 키
  card_last4          TEXT,                    -- '카드번호' 마지막 4자리만 (PAN 미저장)
  installment_months  INTEGER,                 -- '할부개월'. 일시불=0, NULL=데이터 누락
  is_canceled         BOOLEAN NOT NULL DEFAULT false,  -- '취소여부' = 'Y'면 true. W1 UI는 리스트에 보존하되 'Canceled' 라벨 표시

  -- 카테고리·필수성
  category            TEXT NOT NULL DEFAULT 'unknown',  -- W1: simple_rules 결과 또는 'unknown'
  essential           BOOLEAN,                 -- W1엔 NULL (시드 제외), W2 LLM 후 채움
  essential_reason    TEXT,                    -- W1: 시드만 채움, 본인 데이터엔 NULL

  -- 메타
  dedup_hash          TEXT NOT NULL,           -- §7-D 정의
  raw_row             JSONB NOT NULL,          -- XLSX 1행. 카드번호는 마스킹된 형태
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (user_id, dedup_hash)
);

CREATE INDEX idx_transactions_user_date ON transactions(user_id, txn_date DESC);
CREATE INDEX idx_transactions_approval ON transactions(user_id, approval_no) WHERE approval_no IS NOT NULL;

-- refresh 토큰 회전/무효화
CREATE TABLE refresh_tokens (
  jti        UUID PRIMARY KEY,                 -- JWT ID
  user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  expires_at TIMESTAMPTZ NOT NULL,
  revoked_at TIMESTAMPTZ                       -- NULL이면 유효
);
CREATE INDEX idx_refresh_user ON refresh_tokens(user_id);
```

W2 이후 추가 예정 (W1엔 미생성): `categories`, `user_overrides`, `llm_cache`, `monthly_insights`.

## 7. Data Flow

### 7-A. 본인 모드 — 로그인 → XLSX 업로드 → 거래 리스트

```
1. 사용자 → /app
2. ProtectedRoute: 메모리 access 토큰 확인
   - 없음/만료 → /login 리디렉트
3. /login 폼 제출 → POST /auth/login {email, password}
   - FastAPI: users 조회 → argon2id 검증 → access(15m) 발급
   - refresh JWT 발급 → refresh_tokens 테이블에 jti 저장 → httpOnly cookie 세팅
4. /app 복귀 → GET /transactions (Bearer access)
5. UploadDropzone로 .xlsx 선택 → POST /transactions/upload (multipart, Bearer access)
   - 확장자/MIME 검증 (.xlsx, application/vnd.openxmlformats-officedocument.spreadsheetml.sheet)
   - parsers/samsung_card.parse(file_bytes):
       a. openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
       b. 시트 선택 정책: sheetnames 중 '국내이용내역'을 부분 문자열로 포함하는 첫 시트
       c. pandas.read_excel(..., sheet_name=<found>, dtype=str) → DataFrame
       d. 헤더 행 자동 감지: 컬럼 후보 ['카드번호','승인일자','가맹점명','승인금액(원)',
          '승인번호'] 가 모두 존재하는 첫 행을 헤더로
       e. 각 행 → TransactionIn (날짜/금액/시간 파싱, 카드번호 즉시 마스킹)
   - parsers/simple_rules.classify(merchant_raw) → category
   - service.py: dedup_hash 계산 → INSERT ... ON CONFLICT(user_id, dedup_hash) DO NOTHING
   - source_files 메타 기록
6. 응답 { uploaded: N, skipped: M, parse_errors: [...] } → 토스트
7. GET /transactions 재조회 → 리스트 갱신
```

### 7-B. 게스트 모드 — 시드 데이터 보기

```
1. 사용자 → /guest (인증 불필요)
2. GET /seed/transactions
3. seed/kim_jichul.py가 seed/kim_jichul/transactions.json 로드 후 그대로 반환
   (DB 미저장, 매 요청 메모리 직렬화 — 1인 데모 차원에서 충분)
4. TransactionList 컴포넌트로 렌더 (본인 모드와 동일 컴포넌트, 업로드 버튼 hidden)
```

### 7-C. 토큰 갱신

```
1. axios interceptor가 401 감지 → POST /auth/refresh (httpOnly refresh cookie 자동 동봉)
2. FastAPI: refresh JWT 검증 → refresh_tokens.revoked_at NULL 확인
   → 기존 jti revoked_at = now()
   → 새 jti 발급 → refresh_tokens INSERT → 새 refresh cookie 세팅
   → 새 access JWT 응답
3. 원 요청 자동 재시도
4. refresh도 만료/회전 실패 → 로그아웃 처리, /login 이동
```

### 7-D. dedup_hash 계산

```python
import hashlib

def compute_dedup_hash(
    user_id: UUID,
    source_type: str,
    approval_no: str | None,
    *,
    fallback_date: date,
    fallback_amount: Decimal,
    fallback_merchant: str,
) -> str:
    if approval_no:
        payload = f"{user_id}|{source_type}|approval:{approval_no}"
    else:
        payload = (
            f"{user_id}|{source_type}|fb:"
            f"{fallback_date.isoformat()}|{fallback_amount}|{fallback_merchant}"
        )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
```

**선택 근거**: 카드사가 발급하는 `승인번호`는 거래의 unique ID라, 같은 가맹점에 같은 금액 두 번 결제도 별개로 보존됨. 같은 파일 두 번 업로드 → 같은 승인번호 → 자동 멱등. 승인번호가 비어 있는 edge case(취소된 거래 등 일부 명세서 패턴)에선 fallback으로 `(date + amount + merchant_raw)` 사용 — 약하지만 깨지지 않음.

### 7-E. 카드번호 마스킹

```python
def mask_pan(pan: str) -> tuple[str, str]:
    """카드번호 → ('****-****-****-1234', '1234')"""
    digits = re.sub(r"\D", "", pan)
    last4 = digits[-4:] if len(digits) >= 4 else ""
    masked = f"****-****-****-{last4}" if last4 else "****-****-****-****"
    return masked, last4
```

파서가 행 처리 시 즉시 호출 → `card_last4` 컬럼 + `raw_row['카드번호']` 둘 다 마스킹된 값으로 저장. 풀 PAN은 메모리·DB 어디에도 남지 않음.

## 8. Error Handling

| 상황 | 처리 |
|---|---|
| 확장자/MIME 불일치 | 400 `{"error": "INVALID_FILE_TYPE", "expected": ".xlsx"}` |
| 파일 크기 > 10MB | 400 `{"error": "FILE_TOO_LARGE"}` |
| openpyxl 로드 실패 (손상된 파일) | 400 `{"error": "WORKBOOK_LOAD_FAILED"}` |
| `국내이용내역` 시트 없음 | 400 `{"error": "SHEET_NOT_FOUND", "looking_for": "국내이용내역", "found": [...]}` |
| 헤더 행 자동 감지 실패 (필수 컬럼 누락) | 400 `{"error": "HEADER_NOT_FOUND", "missing": [...]}` |
| 빈 시트 / 합계 행만 | 400 `{"error": "EMPTY_SHEET"}` |
| 행 단위 파싱 실패 (1행 날짜/금액 깨짐) | 그 행만 skip, 응답 `parse_errors[]`에 누적 |
| 승인번호 비어 있음 | 정상 흐름, fallback dedup 사용 |
| dedup으로 INSERT 안 됨 | 정상 흐름 (`skipped++`) |
| DB 연결 실패 | 503 `{"error": "DB_UNAVAILABLE"}` + Caddy access 로그 |
| JWT 만료 | 401 `{"error": "TOKEN_EXPIRED"}` → 클라가 자동 refresh |
| JWT 위조/잘못된 서명 | 401 `{"error": "INVALID_TOKEN"}` |
| 로그인 실패 | 401 + 동일 IP 5회 실패 시 1분 lockout (in-memory counter) |
| CORS | apps/web origin (`https://spendlens.suim-app.store`)만 allow, credentials 포함 |
| CSRF | refresh cookie `SameSite=Lax` + Origin 헤더 검증 |

## 9. Out of Scope (W2+로 명시 이관)

| 항목 | 이관 |
|---|---|
| **PDF 명세서 처리 (우리/하나 기본)** | W2 (`pdfplumber`/`camelot` 도입). 삼성 PDF가 추가로 필요해지면 같은 파이프라인에서 처리 (아래 행 참조) |
| **삼성 PDF 명세서** | 현재는 XLSX로 충분하므로 W1엔 미처리. 향후 필요 시(삼성 측 XLSX 다운로드 중단, PDF만 있는 항목 발견 등) 위 행의 PDF 파이프라인에 어댑터 추가 가능 |
| LLM 호출 (Claude Haiku) | W2 |
| Redis 캐시 (LLM 응답) | W2 |
| 카테고리 룰북 본격 (시드 100건 라벨링) | W2 |
| 우리은행/하나은행 파서 (XLSX/PDF) | W2 |
| 회원가입 + 비번 리셋 + SMTP (Resend/SES) | W2 |
| 사용자 오버라이드 UI (필수/비필수 토글) | W3 |
| 카테고리별 대시보드 (Tremor 차트) | W3 |
| 월간 인사이트 LLM 리포트 | W3 |
| Sandbox-Lite (브라우저 파서, IndexedDB) | W4 |
| Sandbox-Full (BYOK) | W4 |
| 랜딩 페이지 본격 디자인 (와이어프레임 → 구현) | W4 |
| Sentry / Plausible 모니터링 | W4 |
| 모바일 PWA 매니페스트 | W5 |
| 데모 GIF/비디오 | W5 |

## 10. Testing 전략

```
apps/api/tests/
├── parsers/
│   └── test_samsung_card.py    # samples/samsung-card-sample.xlsx 사용
│                                #  - 시트 선택 (■ 국내이용내역 부분 매칭)
│                                #  - 헤더 행 자동 감지
│                                #  - 12개 컬럼 매핑
│                                #  - 카드번호 마스킹 (last4 추출, raw_row 마스킹)
│                                #  - 일시불/할부 파싱 (installment_months)
│                                #  - 취소여부 'Y' → is_canceled=true
│                                #  - 빈 행/합계 행 무시
│                                #  - 승인번호 누락 행 → fallback dedup
├── auth/
│   ├── test_password.py        # argon2 round-trip, 잘못된 비번 fail
│   ├── test_jwt.py             # 발급/검증/만료/위조
│   └── test_login.py           # 통합: 테스트 DB → seed user → /auth/login
└── transactions/
    └── test_upload.py          # 통합: 업로드 → dedup → 재업로드 멱등 → /transactions

apps/web/src/**/*.test.ts(x)    # vitest: auth store, upload helper, ProtectedRoute
```

- **DB 통합 테스트**: GitHub Actions에서 `services: postgres:16` 임시 DB. 로컬은 docker-compose의 `postgres-test` 컨테이너.
- **샘플 픽스처**: `apps/api/tests/fixtures/samsung-card-fixture.xlsx` — 실제 명세서를 보고 만든 **익명화된 mini XLSX** (5~10행, 가맹점명 가짜, 카드번호 가짜). git에 포함. 실제 `samples/`는 git ignored.
- **E2E (Playwright)**: W1엔 미설치. W4-5 폴리시 단계에서 추가 검토.
- **CI matrix**: `lint+test` 잡이 `pnpm` (web)과 `uv`+`pytest` (api) 병렬 실행.

## 11. ENV 키 명세 (`.env.example`)

```bash
# DB (Supabase Postgres connection string)
DATABASE_URL=postgresql://postgres:<pwd>@db.<ref>.supabase.co:5432/postgres

# 본인 모드 단일 사용자 (ENV seed)
ADMIN_EMAIL=admin@example.com         # 본인 이메일로 교체 (운영 .env에만, .env.example은 placeholder 유지)
ADMIN_PASSWORD_HASH=                  # 로컬에서 scripts/hash_password.py로 생성

# JWT
JWT_SECRET=                           # openssl rand -base64 64
JWT_ACCESS_TTL_MINUTES=15
JWT_REFRESH_TTL_DAYS=7

# CORS
WEB_ORIGIN=https://spendlens.suim-app.store

# 운영
LOG_LEVEL=INFO
```

Vercel(web)에는 `VITE_API_BASE=https://api.spendlens.suim-app.store` 만 설정.

## 12. CI/CD 워크플로 (요약)

**`.github/workflows/ci.yml`** — main/PR 모두 실행
1. checkout
2. `pnpm install` (frozen lockfile) → `pnpm -r lint && pnpm -r test`
3. `uv sync` (apps/api) → `uv run ruff check && uv run pytest` (postgres 서비스 컨테이너 사용)

**`.github/workflows/deploy-api.yml`** — main push 시만
1. checkout
2. Docker buildx → `apps/api/Dockerfile` → GHCR `ghcr.io/<user>/spendlens-api:<sha>` + `:latest` push
3. SSH (`appleboy/ssh-action`) → Lightsail에서:
   ```bash
   cd /opt/spendlens
   docker compose pull api
   docker compose up -d --no-deps api
   docker image prune -f
   ```

Vercel(web)은 GitHub 연동으로 main push 자동 빌드/배포.

## 13. W1 검수 시나리오 (다른 사람에게 보여주기)

1. 면접관: `https://spendlens.suim-app.store/guest` 클릭 → 시드 거래 30~60건 + 카테고리 라벨 + essential_reason 코멘트가 5초 안에 보임
2. 본인: `https://spendlens.suim-app.store/app` → 로그인 → 실제 삼성카드 XLSX 업로드 → 거래 리스트 갱신, 카드번호 ****-****-****-1234 형태로 마스킹된 모습 확인
3. End-to-end가 라이브 URL에서 동작, README의 Live Demo 링크가 작동

## 14. Open Items (spec 외 — implementation plan 단계에서 해결)

1. **삼성카드 XLSX 정확 검증** — `samples/samsung-card-sample.xlsx`를 implementation plan 작성 직전에 한 번 분석해서: ① `■ 국내이용내역` 시트의 헤더 행 번호(예: 4행), ② 12개 컬럼의 정확한 헤더 문자열(공백/괄호 포함), ③ 합계 행 위치(맨 끝?), ④ 빈 행 처리 패턴, ⑤ 승인시각 포맷(HH:MM:SS vs HH:MM) 확인. 이 정보로 `parsers/samsung_card.py`의 정확한 매핑 코드 작성.
2. **Lightsail 인스턴스 플랜 ($5 vs $10)** — 256MB RAM에서 FastAPI + Caddy + Docker 구동 가능성 확인. 부족하면 $10 (1GB) 플랜으로.
3. **GHCR 인증** — Lightsail에서 `docker login ghcr.io`에 사용할 PAT 또는 deploy key 생성.
4. **가비아 DNS 레코드 등록 시점** — 첫 배포 직전. 적용까지 5분~몇 시간 대기.
5. **익명화 픽스처 XLSX 생성** — 실제 `samsung-card-sample.xlsx`를 참고해서 5~10행짜리 가짜 데이터 XLSX를 `apps/api/tests/fixtures/`에 생성. CI에서 사용할 수 있도록 git에 포함.

## 15. Next Step

본 spec 사용자 리뷰 → 승인 후 `superpowers:writing-plans` 스킬로 implementation plan 작성. plan은 본 spec의 §5 디렉토리 구조와 §12 CI/CD를 기준으로 step-by-step 빌드 순서를 정의한다.
