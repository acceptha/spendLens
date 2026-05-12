# Lightsail Amazon Linux 2023 첫 배포 가이드

> 본 문서는 **W1 plan**과 별도로, 실제 사용된 **Amazon Linux 2023** 환경의 setup 절차를 줄별 설명과 함께 정리한 것이다.
> 원래 plan(`docs/superpowers/plans/2026-04-30-w1-skeleton-and-samsung-xlsx-parser.md`)은 Ubuntu 22.04를 가정했으나, Lightsail 인스턴스가 AL2023으로 생성되었기 때문에 명령어가 달라진다.

## 환경 정보

| 항목 | 값 |
|---|---|
| OS | Amazon Linux 2023 |
| 정적 IP | `3.38.103.25` |
| 플랜 | $10/mo (2 vCPUs, 2GB RAM, 60GB SSD) |
| 리전 | `ap-northeast-2` (Seoul) |
| 기본 SSH 사용자 | `ec2-user` (Ubuntu의 `ubuntu` 와 다름) |
| 패키지 매니저 | `dnf` (Ubuntu의 `apt-get` 대체) |
| Docker 그룹 | `docker` (자동 생성됨, ec2-user 추가 필요) |

## 사전 조건

- [ ] Lightsail 인스턴스 부팅 완료
- [ ] 정적 IP 할당
- [ ] 방화벽: 22 (SSH, 가능하면 본인 IP만), 80, 443 개방
- [ ] `.pem` SSH 키 다운로드 + `chmod 400`
- [ ] 가비아 DNS A 레코드: `api.spendlens` → `3.38.103.25`
- [ ] GitHub PAT (`read:packages` scope) 발급 — Lightsail에서 GHCR pull 용

---

## Step 1: SSH 접속

로컬에서:
```bash
ssh -i <KEY_PATH> ec2-user@3.38.103.25
```

| 토큰 | 의미 |
|---|---|
| `ssh` | SSH 클라이언트 명령 |
| `-i <KEY_PATH>` | 사용할 private key 경로 (Lightsail에서 다운로드한 `.pem` 파일) |
| `ec2-user` | AL2023의 기본 사용자명. Ubuntu라면 `ubuntu`, AL2023은 `ec2-user` |
| `3.38.103.25` | Lightsail 정적 IP |

> 만약 `[root@ip-... ec2-user]#` 프롬프트가 보이면 어떤 단계에서 `sudo su` 한 것 — `exit` 한 번 쳐서 ec2-user 셸로 돌아올 것. 이후 명령은 모두 ec2-user로.

---

## Step 2: Docker 및 Compose v2 설치

```bash
# 2.1
sudo dnf update -y

# 2.2
sudo dnf install -y docker

# 2.3
sudo systemctl enable --now docker

# 2.4
sudo usermod -aG docker ec2-user

# 2.5
sudo mkdir -p /usr/libexec/docker/cli-plugins

# 2.6
sudo curl -SL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64 \
     -o /usr/libexec/docker/cli-plugins/docker-compose

# 2.7
sudo chmod +x /usr/libexec/docker/cli-plugins/docker-compose
```

| Line | 설명 |
|---|---|
| **2.1** `dnf update -y` | 시스템 패키지 인덱스 갱신 + 기존 설치 패키지 업그레이드. `-y`로 모든 prompt에 yes. AL2023의 `apt-get update && apt-get upgrade -y` 대응. |
| **2.2** `dnf install -y docker` | AL2023 기본 repo에서 docker 엔진 설치. `docker-ce` (Docker 공식)이 아니라 Amazon이 maintain하는 docker 빌드. 실용상 동일. |
| **2.3** `systemctl enable --now docker` | `enable`로 부팅 시 자동시작 등록 + `--now`로 즉시 시작. 두 명령(`systemctl enable docker && systemctl start docker`)을 합친 것. |
| **2.4** `usermod -aG docker ec2-user` | ec2-user를 `docker` 그룹에 추가 → 이후 `sudo` 없이 `docker` 커맨드 가능. `-a`(append) 없이 `-G`만 쓰면 다른 그룹에서 빠지므로 위험. **이 변경은 새 셸 세션부터 적용** (재로그인 필요). |
| **2.5** `mkdir -p /usr/libexec/docker/cli-plugins` | Docker Compose v2 플러그인이 위치할 표준 디렉토리. `-p`는 부모 디렉토리도 자동 생성. AL2023은 `docker-compose-plugin` 패키지가 dnf에 없어 수동으로 binary 가져옴. |
| **2.6** `curl -SL .../docker-compose-linux-x86_64 -o ...` | GitHub Releases의 최신 docker compose v2 binary 다운로드. `-S`(silent except error), `-L`(follow redirect — GitHub 다운로드는 redirect됨). `-o`로 저장 경로 지정. |
| **2.7** `chmod +x ...` | 다운로드한 binary에 실행 권한 부여. 없으면 `Permission denied`. |

### 2.x 검증 (선택)

```bash
sudo docker --version
sudo docker compose version
```

`docker compose version` → `Docker Compose version v2.xx.x` 가 보이면 성공. (`docker-compose` 와 `docker compose`는 다름. v2는 `docker compose`라는 sub-command 형식.)

---

## Step 3: 작업 디렉토리 + 파일 배치

```bash
# 3.1
sudo mkdir -p /opt/spendlens

# 3.2
sudo chown ec2-user:ec2-user /opt/spendlens

# 3.3 (이전에 scp로 /tmp/에 올려둔 경우)
sudo mv /tmp/Caddyfile /tmp/docker-compose.prod.yml /opt/spendlens/
sudo chown ec2-user:ec2-user /opt/spendlens/Caddyfile /opt/spendlens/docker-compose.prod.yml
```

| Line | 설명 |
|---|---|
| **3.1** | 운영 파일들을 모아둘 디렉토리 생성. 관례적으로 `/opt/<app>` 사용 (system service의 표준). |
| **3.2** | 소유권을 ec2-user로 → 이후 `sudo` 없이 파일 작성/수정 가능. |
| **3.3** | 로컬에서 미리 scp `infra/Caddyfile`, `infra/docker-compose.prod.yml`을 `/tmp/`로 보낸 경우, 작업 디렉토리로 이동 + 소유권 정정. |

### 만약 scp를 아직 안 했다면

로컬에서:
```bash
cd /d/git/acceptha/spendLens
scp -i <KEY_PATH> infra/Caddyfile infra/docker-compose.prod.yml ec2-user@3.38.103.25:/opt/spendlens/
```
이러면 바로 `/opt/spendlens/`에 떨어짐 (소유권은 ec2-user). Step 3.3 불필요.

---

## Step 4: docker 그룹 적용 위해 재로그인

```bash
exit
# 로컬 셸로 복귀
ssh -i <KEY_PATH> ec2-user@3.38.103.25
```

| 설명 |
|---|
| `exit` 후 새로 SSH 접속하면 ec2-user의 그룹 멤버십이 다시 읽힘. 이전 세션에서는 `docker` 그룹이 안 잡혀 있어서 `docker ps` 실행 시 권한 에러. |
| 빠른 대안: `newgrp docker` 명령 — 현재 셸에서 docker 그룹을 활성화. 단, 새 sub-shell이 열려서 일부 환경변수 잃음. 재로그인이 안전. |

### 4.x 검증

```bash
docker --version          # sudo 없이 실행되어야 함
docker compose version    # 마찬가지
ls -la /opt/spendlens/    # Caddyfile, docker-compose.prod.yml 보여야 함
```

---

## Step 5: `.env` 작성 (운영 secrets)

```bash
cat > /opt/spendlens/.env << 'ENV_EOF'
DATABASE_URL=postgresql://postgres:72PCPY3qmdH7leYdfkqoOcpNAH4aM7KL@postgres:5432/spendlens
POSTGRES_PASSWORD=72PCPY3qmdH7leYdfkqoOcpNAH4aM7KL
ADMIN_EMAIL=acceptha@gmail.com
ADMIN_PASSWORD_HASH='$argon2id$v=19$m=65536,t=3,p=4$plZ7rEpdRbiDT0DT6iwfkQ$i00o0RulIq1MNXxGEGlriWMUxqLLZ2C7UohBQDq5nNc'
JWT_SECRET=37a63d8f513b80ec131dab916162c1d08fce4feea00ba6dbcce3cb64301ad59f
WEB_ORIGIN=https://spendlens.suim-app.store
GHCR_USER=acceptha
ENV_EOF
chmod 600 /opt/spendlens/.env
```

### 5.x 줄별 의미

| Line | 설명 |
|---|---|
| `cat > .env << 'ENV_EOF'` | "ENV_EOF가 나올 때까지의 입력을 .env로 redirect"라는 heredoc 구문. **`'ENV_EOF'` (single-quoted)** 가 핵심: 내부의 `$argon2id` 같은 토큰을 bash가 변수 확장하지 않도록 함. double-quote `"EOF"` 또는 quote 없이 `EOF` 쓰면 `$argon2id` 가 빈 문자열로 대체되어 hash가 깨짐. |
| `DATABASE_URL=postgresql://postgres:<pwd>@postgres:5432/spendlens` | 운영 DB 접속 URL. 호스트가 **`postgres`** (compose 서비스 이름) — Lightsail의 같은 docker compose 안에 postgres 컨테이너가 떠 있고, compose가 만든 내부 네트워크에서 서비스 이름으로 DNS 가능. 외부 DB가 아니라 **자체 호스팅**. |
| `POSTGRES_PASSWORD=...` | postgres 컨테이너 초기화 시 사용. compose의 `postgres` service가 `env_file`로 이 파일 읽음 → `POSTGRES_PASSWORD` 환경변수 발견 → `postgres` 사용자 비번 설정. |
| `ADMIN_EMAIL=acceptha@gmail.com` | 단일 사용자 데모의 로그인 식별자. 컨테이너 시작 시 `ensure_admin_user`이 `users` 테이블에 INSERT. |
| `ADMIN_PASSWORD_HASH='$argon2id$...'` | argon2id 해시. **single quote 필수** — compose가 `.env` 파일 파싱할 때 `${VAR}`/`$VAR` 패턴을 변수 치환으로 해석하므로, `$argon2id`가 빈 값으로 변하면 hash 깨짐. single quote는 compose가 literal 값으로 인식하게 함. |
| `JWT_SECRET=37a6...` | HS256 서명 키 (32 bytes hex = 256 bits entropy). access/refresh JWT 모두 이 키로 서명. 노출되면 누구나 토큰 위조 가능 → 절대 git에 X. |
| `WEB_ORIGIN=https://spendlens.suim-app.store` | CORS allow_origins에 들어감. 프론트(Vercel) 도메인 정확히 일치해야 브라우저가 요청 허용. trailing slash 없음. |
| `GHCR_USER=acceptha` | `docker-compose.prod.yml`의 `image: ghcr.io/${GHCR_USER}/spendlens-api:latest` 변수 치환에 사용. 우리 GitHub 조직/사용자명. |
| `ENV_EOF` | heredoc 종료 마커. 시작 시 `'ENV_EOF'` (quoted) 였더라도 종료는 quote 없이. |
| `chmod 600 /opt/spendlens/.env` | 소유자만 읽기/쓰기. ec2-user 이외 사용자(또는 누가 root 권한 얻으면 모르겠지만)는 읽지 못함. secrets 파일의 표준 권한. |

---

## Step 6: GHCR 로그인 (이미지 pull용)

```bash
# 6.1 PAT를 환경변수로 (history에 안 남게 read 사용 권장)
read -s GHCR_TOKEN
# 입력: ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx (안 보임)

# 6.2 로그인
echo "$GHCR_TOKEN" | docker login ghcr.io -u acceptha --password-stdin

# 6.3 (선택) 환경변수 정리
unset GHCR_TOKEN
```

| Line | 설명 |
|---|---|
| **6.1** `read -s GHCR_TOKEN` | `-s`(silent)로 입력이 화면에 안 보임. 비밀번호 입력 모드. shell history에도 토큰 자체가 안 남음 (값은 변수에만). |
| **6.2** `echo "$GHCR_TOKEN" \| docker login ghcr.io -u acceptha --password-stdin` | `--password-stdin`은 stdin에서 비번 읽음. command-line argument로 PAT 노출 안 시키는 안전한 방법 (`ps -ef` 결과에 안 보임). `-u acceptha`는 GitHub 사용자/조직 이름. 성공 시 `Login Succeeded`. 토큰은 `~/.docker/config.json`에 base64로 저장됨 (ec2-user 홈). |
| **6.3** `unset GHCR_TOKEN` | 더 이상 필요 없는 환경변수 제거. |

### PAT 발급 (안 했다면)

GitHub → 우상단 프로필 → Settings → 좌측 하단 Developer settings → Personal access tokens → Tokens (classic) → Generate new token (classic):
- Note: `spendlens-ghcr-pull`
- Expiration: 90 days
- Scopes: **`read:packages`** (pull만 필요. write는 GitHub Actions의 자동 토큰이 처리)

`ghp_...` 발급되면 한 번만 보임 → 즉시 복사 → 위 read 입력에 붙여넣기.

---

## Step 7: 첫 배포

```bash
# 7.1
cd /opt/spendlens

# 7.2
docker compose -f docker-compose.prod.yml pull

# 7.3
docker compose -f docker-compose.prod.yml up -d

# 7.4
docker compose -f docker-compose.prod.yml ps
```

| Line | 설명 |
|---|---|
| **7.1** | compose가 cwd의 `.env`를 자동 로드해 `${GHCR_USER}` 같은 변수 치환에 사용. compose 파일 자체는 `-f` 로 명시. |
| **7.2** `compose pull` | 3개 image 다운로드: `postgres:16-alpine`, `caddy:2-alpine`, `ghcr.io/acceptha/spendlens-api:latest`. api는 GHCR 로그인 안 되어 있으면 여기서 401 에러 — Step 6 다시 확인. |
| **7.3** `compose up -d` | `-d`(detached)로 백그라운드 시작. 첫 부팅 순서: postgres 시작 → 헬스체크 통과 → api 시작 (`alembic upgrade head` → `uvicorn`) → caddy 시작 → Let's Encrypt에 TLS 인증서 요청. |
| **7.4** `compose ps` | 컨테이너 상태 확인. 3개 모두 `running`이고 postgres는 `healthy`이면 정상. |

### 첫 부팅 시 보이는 흐름 (대기 30초~3분)

1. `postgres-1`: 초기화 + DB 생성 + healthcheck 통과
2. `api-1`: alembic 마이그레이션 (`Running upgrade -> 0001, initial schema`) → `startup complete; admin seeded` → uvicorn listening on 0.0.0.0:8000
3. `caddy-1`: Let's Encrypt에 ACME challenge → 인증서 받음 → 443 listening

### 7.x 로그 확인

```bash
docker compose -f docker-compose.prod.yml logs -f api      # api 로그 실시간 (Ctrl-C로 종료)
docker compose -f docker-compose.prod.yml logs caddy | grep -i certificate  # TLS 발급 확인
```

---

## Step 8: 외부 검증 (로컬에서)

```bash
# 8.1
curl -i https://api.spendlens.suim-app.store/healthz

# 8.2
curl -s https://api.spendlens.suim-app.store/seed/transactions | head -c 300
```

| Line | 설명 |
|---|---|
| **8.1** | `-i`로 HTTP 응답 헤더 포함. 기대: `HTTP/2 200`, body `{"status":"ok"}`. TLS 첫 발급 직후엔 `connection refused` 또는 `tls handshake error` 가능 — 30초~3분 대기 후 재시도. |
| **8.2** | `/seed/transactions`는 인증 없이 호출 가능. 김지출 시드 거래 43건 JSON 배열 반환. `head -c 300`로 처음 300바이트만 출력 (전체는 길어서 잘림). |

브라우저로도 확인:
- https://spendlens.suim-app.store (Vercel 프론트)
- https://api.spendlens.suim-app.store/healthz
- https://api.spendlens.suim-app.store/seed/transactions

---

## Troubleshooting

### Docker login 실패: `denied: denied`
- `<GHCR_TOKEN>` 자리에 literal 그대로 입력함 → 실제 PAT 값으로 교체
- PAT scope에 `read:packages` 없음 → 새로 발급
- 사용자명 오타 (`-u acceptha`)

### `compose pull` 401 Unauthorized
- GHCR 로그인 안 됨 → Step 6 재실행
- PAT 만료됨 → 새 PAT 발급 후 재로그인

### `compose up`은 됐는데 api 컨테이너 즉시 종료
- `docker compose logs api` 확인 필요
- 흔한 원인:
  - DATABASE_URL의 host가 `localhost`로 잘못됨 (compose 내부에선 `postgres`로!)
  - postgres healthcheck 실패 → POSTGRES_PASSWORD 미설정 또는 깨짐 (single quote 누락)
  - JWT_SECRET 빈 문자열 → pydantic-settings가 ValidationError

### TLS 발급 실패 (Caddy 로그에 `obtain failed`)
- `api.spendlens.suim-app.store` DNS 전파 미완료 → `nslookup api.spendlens.suim-app.store 8.8.8.8`로 확인
- 80/443 방화벽 차단 → Lightsail networking 설정에서 두 포트 모두 Anywhere로 열려 있는지 확인
- Caddy가 80번 포트로 ACME challenge 받아야 → 다른 process가 80 점유 중인지 확인 (`sudo ss -tlnp | grep :80`)

### `ADMIN_PASSWORD_HASH` 가 깨짐 (로그인 시 항상 401)
- `.env`에서 single quote `'` 빠짐 → compose가 `$argon2id` 등을 변수 치환 → 빈 값. single quote로 감싸기.
- 해시 자체에 줄바꿈 들어감 (특히 `pbcopy`/Windows clipboard) → 한 줄로 정리.

---

## Post-First-Deploy: 자동 배포 활성화

첫 배포가 성공한 뒤, 다음 push부터 GitHub Actions가 자동으로 배포하도록 하려면:

1. **GitHub Secrets 등록** (Repo Settings → Secrets and variables → Actions):
   - `LIGHTSAIL_HOST` = `3.38.103.25`
   - `LIGHTSAIL_SSH_KEY` = `.pem` 파일 전체 내용

2. **`.github/workflows/deploy-api.yml` 의 `username: ubuntu`를 `username: ec2-user`로 수정** (W1 plan은 Ubuntu 가정이라 ubuntu로 되어 있음). 별도 commit + push.

3. **이후 흐름:** main branch에 `apps/api/**` 또는 `infra/Caddyfile` / `infra/docker-compose.prod.yml` 변경 push → GitHub Actions:
   - 새 api image build → GHCR push
   - SSH로 Lightsail 접속 → `docker compose pull api && up -d` → 무중단 업데이트

---

## 참고

- **`.env` 백업:** `/opt/spendlens/.env`는 git에 없음. 인스턴스 통째로 날아가면 secrets 잃음. 1Password 등에 보관 권장.
- **Postgres 데이터 백업:** named volume `postgres_data`에 저장. `docker run --rm -v spendlens_postgres_data:/data -v $(pwd):/backup alpine tar czf /backup/pg-backup.tgz /data` 같은 방식으로 주기 백업 가능 (W2+에서 cron 추가 권장).
- **메모리:** 2GB 인스턴스는 postgres + api + caddy를 띄우기에 적당. swap은 굳이 필요 없음. RSS 확인은 `docker stats`.
- **로그 로테이션:** Docker는 기본적으로 무한 로그 누적. `daemon.json`에 `log-opts`로 max-size/max-file 설정 권장 (별도 작업).
