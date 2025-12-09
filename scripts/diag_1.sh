#!/usr/bin/env bash
# Comprehensive site probe for mvospette.com + app.mvospette.com

set -euo pipefail

DOMAIN="${DOMAIN:-mvospette.com}"
APP_DOMAIN="${APP_DOMAIN:-app.mvospette.com}"
ROOT="${ROOT:-/opt/mvospette}"
LOG="/tmp/site_probe_$(date -Is).log"

exec > >(tee "$LOG") 2>&1

echo "=== TIMESTAMP ==="
date -Is

echo -e "\n=== FILE CHECKS ==="
for f in "$ROOT/static_site/index.html" "$ROOT/proxy/Caddyfile"; do
  if [ -f "$f" ]; then
    echo "[OK] $f"
  else
    echo "[MISS] $f not found"
  fi
done

echo -e "\n=== SERVICE STATUS (systemd) ==="
for svc in caddy streamlit api oauth2-proxy; do
  if systemctl list-unit-files | grep -q "^${svc}.service"; then
    systemctl status "$svc" --no-pager | sed 's/\x1b\[[0-9;]*[a-zA-Z]//g' | head -n 8
    echo
  else
    echo "$svc: not installed"
  fi
done

echo -e "\n=== PORTS LISTENING ==="
ss -tuln

echo -e "\n=== CADDY VALIDATE (optional) ==="
if command -v caddy >/dev/null 2>&1; then
  caddy validate --config /etc/caddy/Caddyfile || true
else
  echo "caddy not found in PATH"
fi

echo -e "\n=== HTTP/HTTPS CHECKS ==="
curl -I -L "http://$DOMAIN" || true
curl -I -L "https://$DOMAIN" || true
curl -I -L "http://$APP_DOMAIN" || true
curl -I -L "https://$APP_DOMAIN" || true
curl -I -L "http://$APP_DOMAIN/api/health" || true
curl -I -L "https://$APP_DOMAIN/api/health" || true

echo -e "\n=== TLS CERT (SNI) ==="
if command -v openssl >/dev/null 2>&1; then
  echo "Certificate for $DOMAIN:"
  echo | openssl s_client -connect "$DOMAIN:443" -servername "$DOMAIN" 2>/dev/null | openssl x509 -noout -dates -issuer -subject || true
  echo "Certificate for $APP_DOMAIN:"
  echo | openssl s_client -connect "$APP_DOMAIN:443" -servername "$APP_DOMAIN" 2>/dev/null | openssl x509 -noout -dates -issuer -subject || true
else
  echo "openssl not found."
fi

echo -e "\n=== API/STREAMLIT LOCAL (loopback) ==="
curl -I "http://127.0.0.1:8000/health" || true
curl -I "http://127.0.0.1:8501" || true

echo -e "\n=== ENV SUMMARY (redacted) ==="
echo "TERRITORY_API_TOKEN set: ${TERRITORY_API_TOKEN:+yes}"
echo "PYTHON_BIN: ${PYTHON_BIN:-system default}"

echo -e "\nLog written to: $LOG"
