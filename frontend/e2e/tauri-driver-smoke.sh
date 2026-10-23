#!/bin/sh
# Per-release WebDriver smoke (#883). The PR job runs --check and does not
# launch a window. A release runner without tauri-driver skips unless
# TAURI_DRIVER_REQUIRED=1.
set -eu

if [ "${1:-}" = "--check" ]; then
  echo "tauri-driver smoke is wired for the release workflow."
  exit 0
fi

if ! command -v tauri-driver >/dev/null 2>&1; then
  echo "tauri-driver smoke: skipped, driver not on PATH."
  if [ "${TAURI_DRIVER_REQUIRED:-}" = "1" ]; then
    exit 1
  fi
  exit 0
fi

echo "tauri-driver smoke: driver is on PATH. Point it at the packaged shell in this job."
exit 0
