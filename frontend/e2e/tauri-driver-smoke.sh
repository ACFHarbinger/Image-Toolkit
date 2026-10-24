#!/bin/sh
# Per-release WebDriver smoke (#883). `--check` only proves the script is wired.
# A real run starts tauri-driver, opens a session against the packaged shell,
# and fails when that session does not return a window title.
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

ROOT=$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)
APP=${TAURI_DRIVER_APP:-}
if [ -z "$APP" ]; then
  for candidate in \
    "$ROOT/target/release/image-toolkit" \
    "$ROOT/frontend/src-tauri/target/release/image-toolkit"
  do
    if [ -x "$candidate" ]; then
      APP=$candidate
      break
    fi
  done
fi

if [ -z "$APP" ] || [ ! -x "$APP" ]; then
  echo "tauri-driver smoke: packaged shell was not found."
  if [ "${TAURI_DRIVER_REQUIRED:-}" = "1" ]; then
    exit 1
  fi
  exit 0
fi

PORT=${TAURI_DRIVER_PORT:-4444}
tauri-driver --port "$PORT" >/tmp/tauri-driver-smoke.log 2>&1 &
DRIVER_PID=$!
cleanup() {
  kill "$DRIVER_PID" >/dev/null 2>&1 || true
  wait "$DRIVER_PID" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

python3 - "$PORT" "$APP" <<'PY'
import json
import sys
import time
import urllib.error
import urllib.request

port, app = sys.argv[1], sys.argv[2]
base = f"http://127.0.0.1:{port}"

def call(method, path, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(base + path, data=data, method=method)
    if data is not None:
        request.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(request, timeout=10) as response:
        body = response.read().decode()
        return response.status, json.loads(body) if body else {}

deadline = time.time() + 10
last = "driver did not accept a session"
while time.time() < deadline:
    try:
        status, body = call(
            "POST",
            "/session",
            {
                "capabilities": {
                    "alwaysMatch": {
                        "browserName": "wry",
                        "tauri:options": {"application": app},
                    }
                }
            },
        )
        if status != 200:
            raise SystemExit(f"tauri-driver session status {status}")
        session = body.get("value", {}).get("sessionId")
        if not session:
            raise SystemExit(f"tauri-driver session has no id: {body}")
        title_status, title_body = call("GET", f"/session/{session}/title")
        call("DELETE", f"/session/{session}")
        title = title_body.get("value", "")
        if title_status != 200 or not isinstance(title, str) or not title.strip():
            raise SystemExit(f"tauri-driver returned no window title: {title_body}")
        print(f"tauri-driver smoke: session opened, title {title!r}")
        raise SystemExit(0)
    except urllib.error.URLError as exc:
        last = str(exc)
        time.sleep(0.2)
    except SystemExit:
        raise
    except Exception as exc:
        raise SystemExit(f"tauri-driver smoke failed: {exc}") from exc
raise SystemExit(f"tauri-driver smoke failed: {last}")
PY
