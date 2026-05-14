# SpendLens — Claude 작업 컨벤션

이 프로젝트(FastAPI 백엔드)에서 코드를 작성할 때 **반드시** 따라야 하는 규칙. 새 코드는 이미 존재하는 패턴과 일관되어야 한다.

## 0. 기술 스택

- Python 3.12+ / Pydantic v2 / FastAPI
- DB: PostgreSQL 16 + **asyncpg raw SQL** (SQLAlchemy ORM 사용 금지)
- 마이그레이션: Alembic **raw SQL** (`--autogenerate` 금지)
- 패키지 매니저: **uv** + `pyproject.toml` (pip / requirements.txt 금지)
- 모노레포: `apps/api` (FastAPI), `apps/web` (React + Vite)

---

## 1. 프로젝트 구조 — 모듈 기반 수직 슬라이스

`apps/api/app/` 아래 각 디렉토리가 하나의 모듈. 모듈은 **자기에게 필요한 파일만** 소유한다. 모든 모듈에 동일한 파일 세트를 강제하지 않는다.

### 모듈 유형 3가지

| 유형 | 예시 | 소유 파일 |
|---|---|---|
| **도메인 모듈** | `auth/`, `transactions/` | `routes.py` + `schemas.py` + 비즈니스 로직 (`service.py`, `deps.py`, `jwt.py` 등 필요시) |
| **인프라 모듈** | `parsers/` | 라우트 없음. 공유 로직 + registry 패턴으로 등록 |
| **피처 모듈** | `seed/` | 특정 기능 전용. `routes.py` + 데이터 생성기 |

### 실제 디렉토리 트리

```
apps/api/app/
├── main.py
├── db.py
├── settings.py
├── auth/                # 도메인
│   ├── routes.py
│   ├── schemas.py
│   ├── deps.py
│   ├── jwt.py
│   ├── password.py
│   └── seed.py
├── transactions/        # 도메인
│   ├── routes.py
│   ├── schemas.py
│   └── service.py
├── parsers/             # 인프라 (라우트 없음)
│   ├── simple_rules.py
│   └── samsung_card.py
└── seed/                # 피처
    ├── routes.py
    └── kim_jichul.py
```

- **DO**: 모듈이 자기에게 필요한 파일만 소유
- **DON'T**: 새 모듈 만들 때 `repository.py`, `models.py` 자동 생성 (이 프로젝트에서는 사용하지 않음)

---

## 2. DB 접근 패턴

asyncpg raw SQL만 사용한다. SQLAlchemy ORM 모델 정의 절대 금지.

```python
from app.db import acquire

async def list_transactions(user_id: UUID):
    async with acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, amount, occurred_at FROM transactions WHERE user_id = $1",
            user_id,
        )
        return [dict(r) for r in rows]
```

서비스 함수가 DB를 사용해야 하면 `conn`을 인자로 받는다:

```python
async def insert_transactions(conn, user_id: UUID, items: list[TransactionIn]) -> int:
    ...
```

- **DO**: `async with acquire() as conn:` → `conn.fetch / fetchrow / execute`
- **DON'T**: SQLAlchemy 모델 정의, `Depends(get_db)` 패턴

---

## 3. 네이밍 규칙

- **파일명**: `snake_case`
- **클래스명**: `PascalCase`
- **라우터 함수명**: 동사 또는 동사_명사 (`login`, `upload`, `list_transactions`)
- **URL 경로**: 모듈별 prefix + 액션 기반. **버저닝 없음**.
  - 예: `/auth/login`, `/auth/refresh`, `/transactions/upload`, `/healthz`
- **스키마 네이밍**:
  - API 요청/응답: `{도메인}{Request|Response}` — `LoginRequest`, `LoginResponse`, `UploadResponse`
  - 내부 데이터 전달: `{도메인}{In|Out}` — `TransactionIn`, `TransactionOut`
  - 결과/에러: `{도메인}{Result|Error}` — `ParseResult`, `ParseError`

- **DO**: `LoginRequest`, `TransactionOut`, `/auth/login`
- **DON'T**: `CreateUserRequest`, `/api/v1/users`

---

## 4. 에러 핸들링

라우터에서 `HTTPException`을 **직접 raise**한다. 전역 `exception_handler` 사용 금지.

`detail`은 문자열 코드 또는 dict:

```python
raise HTTPException(status_code=401, detail="INVALID_CREDENTIALS")
raise HTTPException(status_code=400, detail={"error": "INVALID_FILE_TYPE", "expected": ".xlsx"})
```

파서 등 인프라 모듈만 커스텀 예외(`ParseError(code, **details)`)를 사용. 라우터에서 catch 후 `HTTPException`으로 변환한다.

에러 코드는 `UPPER_SNAKE_CASE` 상수.

- **DO**: `raise HTTPException(status_code=401, detail="INVALID_CREDENTIALS")`
- **DON'T**: `NotFoundException` 같은 커스텀 HTTP 예외 클래스 생성

---

## 5. 의존성 주입(DI)

`Depends()`는 **인증에만** 사용한다.

```python
from app.auth.deps import current_user_id

@router.get("/transactions")
async def list_transactions(user_id: UUID = Depends(current_user_id)):
    async with acquire() as conn:
        ...
```

- DB는 `Depends`로 주입하지 않는다. `acquire()`를 직접 호출.
- 서비스 함수는 일반 `async` 함수이며 `conn`, `user_id` 등을 인자로 받는다.
- 중첩 DI / 서비스 클래스 DI 패턴 없음.

- **DO**: `user_id = Depends(current_user_id)` + `async with acquire() as conn:`
- **DON'T**: `Depends(get_service)`, 서비스 클래스에 repository 주입

---

## 6. 환경변수 / 설정

`pydantic-settings`의 `BaseSettings`. 모듈 레벨 싱글톤으로 노출한다.

```python
# app/settings.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    jwt_secret: str
    ...

settings = Settings()  # 모듈 레벨 싱글톤
```

```python
# 다른 파일에서
from app.settings import settings
secret = settings.jwt_secret
```

- 모든 시크릿/URL은 `.env`. 코드에 하드코딩 금지.
- **DO**: `from app.settings import settings`
- **DON'T**: `os.getenv("JWT_SECRET")`, `@lru_cache` + `get_settings()`

---

## 7. 테스트 컨벤션

`pytest` + `pytest-asyncio` (`asyncio_mode = "auto"`) + `httpx.ASGITransport`.

`tests/`는 `app/` 구조를 미러링한다: `tests/auth/`, `tests/parsers/`, `tests/transactions/`.

핵심 픽스처(`tests/conftest.py`):

- `test_db_pool` — **session-scoped** asyncpg 풀
- `_init_app_pool` — `app.db._pool`을 테스트 풀로 교체
- `reset_tables` — 매 테스트 전 `TRUNCATE ... CASCADE`로 전체 초기화

테스트 데이터 파일은 `tests/fixtures/`.

테스트 함수명: `test_{대상}_{시나리오}` — `test_login_with_invalid_credentials`, `test_parse_workbook_empty_sheet`.

- **DO**: session-scoped DB 풀 + 테스트 전 `TRUNCATE CASCADE`
- **DON'T**: SQLite in-memory, 매 테스트마다 DB 새로 생성

---

## 8. 커밋 컨벤션

**Conventional Commits 필수**. 스코프 포함.

- 타입: `feat`, `fix`, `chore`, `test`, `docs`, `ci`, `refactor`
- 스코프: `api`, `web`, `infra`
- 하나의 논리적 변경 = 하나의 커밋

- **DO**: `feat(api): add budget module routes and schemas`
- **DON'T**: `update files`, `fix stuff`

---

## 9. 패키지 매니저

- **백엔드**: `uv` + `pyproject.toml`. 추가 시 `uv add <package>`.
- **프론트**: `pnpm` (모노레포). 추가 시 `pnpm add <package>`.

- **DO**: `uv add httpx`
- **DON'T**: `pip install httpx`, `requirements.txt` 수동 편집
