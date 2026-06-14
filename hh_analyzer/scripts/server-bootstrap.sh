#!/bin/bash
# Bootstrap VPS for HH Analytics + Coolify
# Run as root on Ubuntu 22.04/24.04:
#   curl -fsSL https://raw.githubusercontent.com/Anton1Ushakov/hh/main/hh_analyzer/scripts/server-bootstrap.sh | bash

set -euo pipefail

echo "==> Updating system..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get upgrade -y

echo "==> Installing basics..."
apt-get install -y curl ca-certificates ufw

echo "==> Configuring firewall..."
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 8000/tcp
echo "y" | ufw enable || true

if command -v coolify >/dev/null 2>&1 || [ -d /data/coolify ]; then
  echo "==> Coolify already present, skipping install."
else
  echo "==> Installing Coolify (5-15 min)..."
  curl -fsSL https://cdn.coollabs.io/coolify/install.sh | bash
fi

IP=$(curl -s ifconfig.me || hostname -I | awk '{print $1}')
echo ""
echo "=============================================="
echo " Server bootstrap done."
echo " Coolify panel: http://${IP}:8000"
echo " Next: open panel in browser, create admin account."
echo "=============================================="
