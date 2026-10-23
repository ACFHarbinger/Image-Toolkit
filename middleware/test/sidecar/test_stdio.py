from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from middleware.src.supervisor import Supervisor
from middleware.src.supervisor.children import SIDECAR, is_pid_alive, sidecar_argv

ROOT_DIR = Path(__file__).resolve().parents[3]


def _env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT_DIR)
    return env


def test_sidecar_module_import_does_not_import_torch() -> None:
    code = "import sys; import middleware.src.sidecar; raise SystemExit(1 if 'torch' in sys.modules else 0)"
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT_DIR,
        env=_env(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr


def test_sidecar_stdio_handshake_and_ping() -> None:
    frames = [
        {
            "jsonrpc": "2.0",
            "id": "handshake",
            "method": "system.handshake",
            "params": {
                "protocol": "image-toolkit-bridge",
                "client": {"name": "pytest", "version": "1.0.0"},
            },
        },
        {"jsonrpc": "2.0", "id": "ping", "method": "system.ping", "params": {}},
    ]
    proc = subprocess.run(
        [sys.executable, "-m", "middleware.src.sidecar"],
        cwd=ROOT_DIR,
        env=_env(),
        input="".join(json.dumps(frame) + "\n" for frame in frames),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=10,
    )
    assert proc.returncode == 0, proc.stderr
    lines = proc.stdout.splitlines()
    assert len(lines) == 2
    decoded = [json.loads(line) for line in lines]
    assert decoded[0]["result"]["protocol"] == "image-toolkit-bridge"
    assert decoded[1] == {"jsonrpc": "2.0", "id": "ping", "result": {"ok": True}}
    assert proc.stderr == ""


def test_supervisor_can_start_real_sidecar(tmp_path: Path) -> None:
    supervisor = Supervisor(
        tmp_path,
        poll_interval_s=0.05,
        use_real_sidecar=True,
        python_executable=sys.executable,
    )
    supervisor.start()
    try:
        supervisor.wait_until_ready(timeout_s=5)
        sidecar = supervisor.children[SIDECAR]
        assert is_pid_alive(sidecar.pid)
        command = sidecar_argv(tmp_path, python_executable=sys.executable)
        assert command[0] == sys.executable
        assert command[1:3] == ["-m", "middleware.src.sidecar"]
    finally:
        supervisor.stop()
