#!/usr/bin/env bash
# Restart API and Streamlit without running the pipeline.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

bash "$ROOT/scripts/stop_web.sh"
bash "$ROOT/scripts/start_web.sh"
