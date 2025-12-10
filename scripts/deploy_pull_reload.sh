#!/usr/bin/env bash
# Pull latest main, reload caddy, restart API/UI (systemd).
set -euo pipefail

cd /opt/mvospette
echo "Pulling latest from origin/main..."
git pull origin main

echo "Reloading Caddy..."
sudo caddy fmt --overwrite /etc/caddy/Caddyfile
sudo systemctl reload caddy

echo "Restarting API and Streamlit..."
sudo systemctl restart api streamlit

echo "Done."
