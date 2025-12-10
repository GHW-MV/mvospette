#!/usr/bin/env bash
# Simple health check for API/UI. Exits non-zero on failure.

set -euo pipefail

API_URL="${API_URL:-http://127.0.0.1:8000/health}"
UI_URL="${UI_URL:-http://127.0.0.1:8501/}"
API_TOKEN="${TERRITORY_API_TOKEN:-}"

check() {
  local name="$1"
  local url="$2"
  local extra=()
  if [ -n "$API_TOKEN" ] && [[ "$name" == "API" ]]; then
    extra=(-H "Authorization: Bearer ${API_TOKEN}")
  fi
  echo "Checking $name at $url ..."
  if curl -fsSL "${extra[@]}" "$url" >/dev/null; then
    echo "$name OK"
  else
    echo "$name FAILED" >&2
    return 1
  fi
}

fail=0
check "API" "$API_URL" || fail=1
check "UI" "$UI_URL" || fail=1

# Optional alert via notify_email.py if configured
if [ "$fail" -ne 0 ] && [ -n "${MAIL_TO:-}" ]; then
  python -m scripts.notify_email "Health check failed" "API/ UI health check failed on $(hostname) at $(date -Is)"
fi

exit $fail
