# W2 운영 배포 메모

W2 머지 후 Lightsail에 반영해야 하는 변경 사항.

## 새 ENV 변수 (`/opt/spendlens/.env`)

W2가 다음 3개 ENV를 사용한다. Lightsail에 SSH로 들어가 `/opt/spendlens/.env`에 추가:

```bash
ssh -i ~/.ssh/lightsail.pem ec2-user@$LIGHTSAIL_HOST
sudo nano /opt/spendlens/.env
```

추가할 라인:

```
# Redis (rate limit + categorization cache + budget counter)
REDIS_URL=redis://redis:6379/0

# Anthropic Claude Haiku — 카테고리 분류 폴백
ANTHROPIC_API_KEY=sk-ant-...   # ← 본인 실 키
ANTHROPIC_MONTHLY_BUDGET_USD=5.0
```

## docker-compose.prod.yml에 redis 추가

`deploy-api.yml` 워크플로가 `infra/docker-compose.prod.yml`을 Lightsail로 SCP한다. main 머지 후 자동 반영되며, `redis_data` named volume이 자동 생성된다.

## 운영 적용

PR 머지 → GitHub Actions가 GHCR 이미지 push + SCP + SSH deploy 자동 실행. 수동으로 한 번만:

```bash
ssh -i ~/.ssh/lightsail.pem ec2-user@$LIGHTSAIL_HOST
cd /opt/spendlens
sudo docker compose -f docker-compose.prod.yml pull
sudo docker compose -f docker-compose.prod.yml up -d
sudo docker compose -f docker-compose.prod.yml ps
```

전 서비스가 `healthy` 상태여야 OK:
- `postgres` (W1)
- `redis` (W2 신규)
- `api` (W1, redis 의존 추가)
- `caddy` (W1)

## 검수 시나리오

1. `https://spendlens.suim-app.store/signup` → 새 이메일로 가입 → `/app` 진입
2. 동일 이메일 재가입 → 409 EMAIL_ALREADY_EXISTS
3. 본인 우리카드 또는 하나은행 명세서 업로드 → 거래에 카테고리 표시
4. 6회/시간 가입 시도 → 6회째 429 TOO_MANY_REQUESTS + Retry-After
5. Lightsail에서 `redis-cli` 확인:
   ```
   sudo docker compose -f docker-compose.prod.yml exec redis redis-cli GET llm_budget:$(date -u +%Y-%m)
   ```
   0 또는 그 이상 (LLM 호출이 한 번이라도 있으면 cost USD)

## Rollback

api 컨테이너만 W1 이미지 SHA로 회귀하면 W2 코드 제거. redis 컨테이너는 정지/제거해도 데이터 손실 없음 (cache는 재구성 가능).

```bash
# 특정 SHA로 rollback
sudo docker compose -f docker-compose.prod.yml pull api
sudo docker compose -f docker-compose.prod.yml up -d api
```
