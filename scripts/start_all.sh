#!/usr/bin/env bash
# Start pipeline, API, and Streamlit locally (no Docker). Best run under systemd for permanence.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT/logs"
mkdir -p "$LOG_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"
export PYTHONPATH="${PYTHONPATH:-$ROOT}"

ZIP_MASTER="${ZIP_MASTER:-$ROOT/static/uszips.csv}"
REP_ACTIVITY="${REP_ACTIVITY:-$ROOT/static/Zipcodes_Deal_Count_By_Rep.csv}"
DB_PATH="${DB_PATH:-$ROOT/data/territory.db}"
CSV_PATH="${CSV_PATH:-$ROOT/data/territory_assignments.csv}"
API_HOST="${API_HOST:-127.0.0.1}"
API_PORT="${API_PORT:-8000}"
UI_HOST="${UI_HOST:-127.0.0.1}"
UI_PORT="${UI_PORT:-8501}"

# Auto-generate API token if not provided, using md5(hostname+timestamp) for quick testing.
if [ -z "${TERRITORY_API_TOKEN:-}" ]; then
  if command -v md5sum >/dev/null 2>&1; then
    TERRITORY_API_TOKEN="$(printf '%s' "$(hostname)-$(date +%s)" | md5sum | awk '{print $1}')"
  else
    TERRITORY_API_TOKEN="$("$PYTHON_BIN" - <<'PY'
import hashlib, socket, time
print(hashlib.md5(f"{socket.gethostname()}-{int(time.time())}".encode()).hexdigest())
PY
)"
  fi
  echo "Generated TERRITORY_API_TOKEN=${TERRITORY_API_TOKEN}"
fi
export TERRITORY_API_TOKEN

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python not found at $PYTHON_BIN. Set PYTHON_BIN to your venv python (e.g., /root/.pyenv/versions/territory-env/bin/python)."
  exit 1
fi

echo "Running pipeline..."
$PYTHON_BIN -m src.territory_pipeline \
  --zip-master "$ZIP_MASTER" \
  --rep-activity "$REP_ACTIVITY" \
  --db-path "$DB_PATH" \
  --export-path "$CSV_PATH"

echo "Starting API on $API_HOST:$API_PORT ..."
nohup "$PYTHON_BIN" -m uvicorn src.api:app --host "$API_HOST" --port "$API_PORT" \
  >> "$LOG_DIR/api.log" 2>&1 &
echo $! > "$LOG_DIR/api.pid"

echo "Starting Streamlit on $UI_HOST:$UI_PORT ..."
nohup "$PYTHON_BIN" -m streamlit run "$ROOT/src/streamlit_app.py" --server.address "$UI_HOST" --server.port "$UI_PORT" \
  >> "$LOG_DIR/ui.log" 2>&1 &
echo $! > "$LOG_DIR/ui.pid"

echo "Done. Logs in $LOG_DIR."
