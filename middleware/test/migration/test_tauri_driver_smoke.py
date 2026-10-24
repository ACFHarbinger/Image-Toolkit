"""The release smoke opens a WebDriver session instead of exiting on driver presence."""

from __future__ import annotations

import os
import stat
import subprocess
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "frontend" / "e2e" / "tauri-driver-smoke.sh"

FAKE_DRIVER = textwrap.dedent(
    """\
    #!/usr/bin/env python3
    import json
    import sys
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    port = 4444
    args = sys.argv[1:]
    if "--port" in args:
        port = int(args[args.index("--port") + 1])

    class Handler(BaseHTTPRequestHandler):
        def _send(self, payload, status=200):
            body = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            length = int(self.headers.get("Content-Length", "0"))
            raw = json.loads(self.rfile.read(length) or b"{}")
            app = raw["capabilities"]["alwaysMatch"]["tauri:options"]["application"]
            if not app:
                self._send({"value": {"error": "missing application"}}, 500)
                return
            self._send({"value": {"sessionId": "s1", "capabilities": {}}})

        def do_GET(self):
            self._send({"value": "Image Database and Toolkit"})

        def do_DELETE(self):
            self._send({"value": None})

        def log_message(self, fmt, *args):
            return

    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
    """
)


def test_check_mode_does_not_launch_a_session() -> None:
    proc = subprocess.run([str(SCRIPT), "--check"], capture_output=True, text=True, timeout=10)
    assert proc.returncode == 0
    assert "wired" in proc.stdout


def test_required_driver_opens_a_session(tmp_path: Path) -> None:
    driver = tmp_path / "tauri-driver"
    driver.write_text(FAKE_DRIVER, encoding="utf-8")
    driver.chmod(driver.stat().st_mode | stat.S_IEXEC)
    app = tmp_path / "image-toolkit"
    app.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    app.chmod(app.stat().st_mode | stat.S_IEXEC)
    env = os.environ.copy()
    env["PATH"] = f"{tmp_path}{os.pathsep}{env.get('PATH', '')}"
    env["TAURI_DRIVER_LOG"] = str(tmp_path / "driver.log")
    env["TAURI_DRIVER_REQUIRED"] = "1"
    env["TAURI_DRIVER_APP"] = str(app)
    env["TAURI_DRIVER_PORT"] = "18787"
    proc = subprocess.run([str(SCRIPT)], capture_output=True, text=True, timeout=20, env=env)
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert "session opened" in proc.stdout


def test_a_missing_title_fails_the_smoke(tmp_path: Path) -> None:
    driver = tmp_path / "tauri-driver"
    driver.write_text(
        FAKE_DRIVER.replace('{"value": "Image Database and Toolkit"}', '{"value": ""}'),
        encoding="utf-8",
    )
    driver.chmod(driver.stat().st_mode | stat.S_IEXEC)
    app = tmp_path / "image-toolkit"
    app.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    app.chmod(app.stat().st_mode | stat.S_IEXEC)
    env = os.environ.copy()
    env["PATH"] = f"{tmp_path}{os.pathsep}{env.get('PATH', '')}"
    env["TAURI_DRIVER_LOG"] = str(tmp_path / "driver.log")
    env["TAURI_DRIVER_REQUIRED"] = "1"
    env["TAURI_DRIVER_APP"] = str(app)
    env["TAURI_DRIVER_PORT"] = "18788"
    proc = subprocess.run([str(SCRIPT)], capture_output=True, text=True, timeout=20, env=env)
    assert proc.returncode != 0


def test_release_workflow_requires_provisioned_driver_and_application() -> None:
    import yaml

    workflow = yaml.safe_load((ROOT / ".github/workflows/release.yml").read_text())
    job = workflow["jobs"]["tauri-driver"]
    assert job["env"]["TAURI_DRIVER_REQUIRED"] == "1"
    commands = "\n".join(step.get("run", "") for step in job["steps"])
    assert "cargo install tauri-driver --locked" in commands
    assert "webkit2gtk-driver" in commands and "xvfb" in commands
    assert "cargo build --release --locked -p app" in commands
    assert "cargo metadata" in commands and "TAURI_DRIVER_APP=" in commands
    assert "xvfb-run -a bash frontend/e2e/tauri-driver-smoke.sh" in commands
    assert "tauri-driver" in workflow["jobs"]["publish-release"]["needs"]


def test_required_missing_application_fails(tmp_path: Path) -> None:
    driver = tmp_path / "tauri-driver"
    driver.write_text("#!/bin/sh\nexit 0\n")
    driver.chmod(driver.stat().st_mode | stat.S_IEXEC)
    env = os.environ.copy()
    env.update(
        PATH=f"{tmp_path}{os.pathsep}{env.get('PATH', '')}",
        TAURI_DRIVER_REQUIRED="1",
        TAURI_DRIVER_APP=str(tmp_path / "missing-app"),
    )
    proc = subprocess.run([str(SCRIPT)], capture_output=True, text=True, env=env, timeout=10)
    assert proc.returncode != 0
    assert "packaged shell was not found" in proc.stdout
