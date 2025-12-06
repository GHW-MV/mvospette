#!/usr/bin/env bash
# Reload/restart app-related services (systemd + caddy). Adjust names if different.

set -euo pipefail

SERVICES=(
  streamlit
  oauth2-proxy
  api
)

echo "Reloading caddy..."
sudo systemctl reload caddy || echo "caddy reload failed (is it installed?)"

for svc in "${SERVICES[@]}"; do
  if systemctl list-unit-files | grep -q "^${svc}.service"; then
    echo "Restarting ${svc}..."
    sudo systemctl restart "$svc"
    sudo systemctl status "$svc" --no-pager | sed 's/\x1b\[[0-9;]*[a-zA-Z]//g' | head -n 5
  else
    echo "Service ${svc} not found, skipping."
  fi
done

echo "Done."
