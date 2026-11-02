#!/usr/bin/env bash
# Start the Qt app and the Tauri dev app side by side for migration parity checks.
# Qt and Tauri hold separate single-instance gates by default; closing
# the Tauri dev run (Ctrl+C) also closes Qt. Both share ~/.image-toolkit data.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=".venv/bin/python"
[ -x "$PY" ] || { echo "missing .venv; see AGENTS.md" >&2; exit 1; }
scripts/clean-snap-env.sh "$PY" middleware/main.py gui &
qt=$!
trap 'kill "$qt" 2>/dev/null || true' EXIT INT TERM
npm run dev
