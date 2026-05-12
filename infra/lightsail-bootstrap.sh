#!/usr/bin/env bash
# Run once on a fresh Lightsail Amazon Linux 2023 instance.
# Prereq: SSH'd in as ec2-user.
# 자세한 단계별 설명은 infra/lightsail-al2023-setup.md 참고.
set -euo pipefail

echo "==> Updating system packages"
sudo dnf update -y

echo "==> Installing docker"
sudo dnf install -y docker
sudo systemctl enable --now docker
sudo usermod -aG docker ec2-user

echo "==> Installing docker compose v2 plugin (AL2023 dnf에 없어 수동 install)"
sudo mkdir -p /usr/libexec/docker/cli-plugins
sudo curl -SL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64 \
     -o /usr/libexec/docker/cli-plugins/docker-compose
sudo chmod +x /usr/libexec/docker/cli-plugins/docker-compose

echo "==> Creating /opt/spendlens"
sudo mkdir -p /opt/spendlens
sudo chown ec2-user:ec2-user /opt/spendlens

echo "==> Verifying docker compose (sudo로 — 그룹 적용 전이라)"
sudo docker --version
sudo docker compose version

echo ""
echo "==> Done. Next steps:"
echo "  1) exit & re-SSH so docker group takes effect (no more sudo for docker)"
echo "  2) scp Caddyfile + docker-compose.prod.yml to /opt/spendlens/"
echo "  3) Create /opt/spendlens/.env (chmod 600) with required vars:"
echo "       DATABASE_URL=postgresql://postgres:<POSTGRES_PASSWORD>@postgres:5432/spendlens"
echo "       POSTGRES_PASSWORD=<32+ char random>"
echo "       ADMIN_EMAIL=<your email>"
echo "       ADMIN_PASSWORD_HASH='\$argon2id\$...'   # quotes required! run scripts/hash_password.py"
echo "       JWT_SECRET=<openssl rand -hex 32>"
echo "       WEB_ORIGIN=https://spendlens.suim-app.store"
echo "       GHCR_USER=<github username/org>"
echo "  4) read -s GHCR_TOKEN && echo \"\$GHCR_TOKEN\" | docker login ghcr.io -u <USER> --password-stdin"
echo "  5) cd /opt/spendlens && docker compose -f docker-compose.prod.yml pull && docker compose -f docker-compose.prod.yml up -d"
