#!/usr/bin/env bash
# Generate a local website access key (separate from the API key) and store it on the server.
# This does NOT capture user-supplied credentials; it just creates a server-side key.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SECRET_DIR="$ROOT/secrets"
OUT_FILE="$SECRET_DIR/site_key.txt"

mkdir -p "$SECRET_DIR"
umask 077

generate_key() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 24
  else
    # Fallback to Python if openssl is unavailable
    python - <<'PY'
import secrets
print(secrets.token_hex(24))
PY
  fi
}

KEY="$(generate_key)"
echo "$KEY" > "$OUT_FILE"

echo "Site access key generated and saved to: $OUT_FILE"
echo "Key (copy now, file is 600): $KEY"
