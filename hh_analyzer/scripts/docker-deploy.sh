#!/bin/bash
# Direct deploy without Coolify (Docker Compose on VPS)
# Prerequisites: git, docker, docker compose plugin
# Usage on server:
#   git clone https://github.com/Anton1Ushakov/hh.git /opt/hh
#   cd /opt/hh/hh_analyzer
#   cp .env.example .env   # edit secrets
#   docker compose up -d --build

set -euo pipefail

APP_DIR="${APP_DIR:-/opt/hh/hh_analyzer}"

if ! command -v docker >/dev/null 2>&1; then
  echo "==> Installing Docker..."
  curl -fsSL https://get.docker.com | sh
  systemctl enable docker
  systemctl start docker
fi

mkdir -p "$(dirname "$APP_DIR")"
if [ ! -d /opt/hh/.git ]; then
  git clone https://github.com/Anton1Ushakov/hh.git /opt/hh
fi

cd "$APP_DIR"
git pull origin main

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env — edit HH_* variables before starting!"
  exit 1
fi

docker compose up -d --build
echo "App running on http://$(curl -s ifconfig.me):8000"
