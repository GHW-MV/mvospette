#!/usr/bin/env bash
# Start API and Streamlit without running the territory pipeline.
# Uses pidfiles in logs/ so we can stop/restart cleanly.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT/logs"
mkdir -p "$LOG_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"
API_HOST="${API_HOST:-127.0.0.1}"
API_PORT="${API_PORT:-8000}"
UI_HOST="${UI_HOST:-127.0.0.1}"
UI_PORT="${UI_PORT:-8501}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python not found at $PYTHON_BIN. Set PYTHON_BIN to your venv python (e.g., /root/.pyenv/versions/territory-env/bin/python)."
  exit 1
fi

start_api() {
  if [ -f "$LOG_DIR/api.pid" ] && kill -0 "$(cat "$LOG_DIR/api.pid")" 2>/dev/null; then
    echo "API already running (pid $(cat "$LOG_DIR/api.pid")). Skipping."
    return
  fi
  echo "Starting API on $API_HOST:$API_PORT ..."
  nohup "$PYTHON_BIN" -m uvicorn src.api:app --host "$API_HOST" --port "$API_PORT" \
    >> "$LOG_DIR/api.log" 2>&1 &
  echo $! > "$LOG_DIR/api.pid"
}

start_ui() {
  if [ -f "$LOG_DIR/ui.pid" ] && kill -0 "$(cat "$LOG_DIR/ui.pid")" 2>/dev/null; then
    echo "UI already running (pid $(cat "$LOG_DIR/ui.pid")). Skipping."
    return
  fi
  echo "Starting Streamlit on $UI_HOST:$UI_PORT ..."
  nohup "$PYTHON_BIN" -m streamlit run "$ROOT/src/streamlit_app.py" \
    --server.address "$UI_HOST" --server.port "$UI_PORT" \
    >> "$LOG_DIR/ui.log" 2>&1 &
  echo $! > "$LOG_DIR/ui.pid"
}

start_api
start_ui

echo "Done. Logs in $LOG_DIR. PID files: $LOG_DIR/api.pid, $LOG_DIR/ui.pid."
