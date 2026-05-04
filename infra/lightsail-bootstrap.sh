#!/usr/bin/env bash
# Run once on a fresh Lightsail Ubuntu 22.04 instance.
# Prereq: SSH'd in as ubuntu user.
set -euo pipefail

echo "==> Updating apt"
sudo apt-get update -y
sudo apt-get upgrade -y

echo "==> Installing docker"
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker ubuntu

echo "==> Installing docker compose plugin (already in get.docker.com but verify)"
docker compose version

echo "==> Creating /opt/spendlens"
sudo mkdir -p /opt/spendlens
sudo chown ubuntu:ubuntu /opt/spendlens

echo "==> Done. Now:"
echo "  1) scp Caddyfile and docker-compose.prod.yml to /opt/spendlens/"
echo "  2) Create /opt/spendlens/.env (chmod 600) with:"
echo "       DATABASE_URL=postgresql://postgres:<POSTGRES_PASSWORD>@postgres:5432/spendlens"
echo "       POSTGRES_PASSWORD=<강력한 랜덤>"
echo "       ADMIN_EMAIL=<your email>"
echo "       ADMIN_PASSWORD_HASH=<run scripts/hash_password.py>"
echo "       JWT_SECRET=<openssl rand -hex 32>"
echo "       WEB_ORIGIN=https://spendlens.suim-app.store"
echo "       GHCR_USER=<github username/org>"
echo "  3) docker login ghcr.io  (use GHCR_TOKEN PAT)"
echo "  4) export \$(grep -v '^#' /opt/spendlens/.env | xargs) && cd /opt/spendlens && docker compose -f docker-compose.prod.yml up -d"
echo "  5) Log out and back in for docker group to take effect"
