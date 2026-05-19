# Changelog

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
