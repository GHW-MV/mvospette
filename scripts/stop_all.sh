#!/usr/bin/env bash
# Stop API and Streamlit started by start_all.sh (uses pid files).

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT/logs"

stop_pid() {
  local name="$1"
  local pidfile="$LOG_DIR/${name}.pid"
  if [ -f "$pidfile" ]; then
    pid=$(cat "$pidfile")
    if kill -0 "$pid" 2>/dev/null; then
      echo "Stopping $name (pid $pid)..."
      kill "$pid" || true
    else
      echo "$name pid $pid not running."
    fi
    rm -f "$pidfile"
  else
    echo "No pidfile for $name."
  fi
}

stop_pid api
stop_pid ui

echo "Done."
