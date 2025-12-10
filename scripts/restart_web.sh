#!/usr/bin/env bash
# Restart API and Streamlit without running the pipeline.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

"$ROOT/scripts/stop_web.sh"
"$ROOT/scripts/start_web.sh"
