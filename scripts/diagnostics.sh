#!/usr/bin/env bash
# Lightweight system diagnostic to capture host + app state.
# Usage: sudo bash scripts/diagnostics.sh [/path/to/output.txt]

set -euo pipefail

OUT="${1:-/tmp/territory_diag.txt}"
exec > >(tee "$OUT") 2>&1

echo "=== TIMESTAMP ==="
date -Is

echo -e "\n=== OS RELEASE ==="
cat /etc/os-release || true
uname -a

echo -e "\n=== HOST INFO ==="
hostnamectl || true

echo -e "\n=== CPU ==="
lscpu | head -n 20 || true

echo -e "\n=== MEMORY ==="
free -h || true

echo -e "\n=== DISK ==="
df -hT || true

echo -e "\n=== NETWORK (IPv4) ==="
ip -4 addr || true
echo -e "\nDefault route:"
ip -4 route show default || true

echo -e "\n=== LISTENING PORTS ==="
ss -tuln || true

echo -e "\n=== PYTHON ==="
command -v python3 || true
python3 --version || true
pip3 --version || true

echo -e "\n=== SERVICES (if present) ==="
systemctl status streamlit --no-pager 2>/dev/null | sed 's/\x1b\\[[0-9;]*[a-zA-Z]//g' || echo "streamlit: n/a"
systemctl status oauth2-proxy --no-pager 2>/dev/null | sed 's/\x1b\\[[0-9;]*[a-zA-Z]//g' || echo "oauth2-proxy: n/a"
systemctl status caddy --no-pager 2>/dev/null | sed 's/\x1b\\[[0-9;]*[a-zA-Z]//g' || echo "caddy: n/a"

echo -e "\n=== LOG TAILS (if present) ==="
for f in /var/log/territory/*.log; do
  [ -f "$f" ] && { echo "-- $f"; tail -n 50 "$f"; }
done

echo -e "\n=== ENV CHECK (redacted) ==="
echo "TERRITORY_API_TOKEN set: ${TERRITORY_API_TOKEN:+yes}"
echo "OAUTH2_PROXY_CLIENT_ID set: ${OAUTH2_PROXY_CLIENT_ID:+yes}"
echo "OAUTH2_PROXY_REDIRECT_URL: ${OAUTH2_PROXY_REDIRECT_URL:-n/a}"

echo -e "\nDiagnostics written to: $OUT"
