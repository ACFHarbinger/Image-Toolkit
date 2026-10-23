"""Test client for the live sidecar: subprocess over pipes, line queue.

Mirrors how the supervisor spawns children (``children.child_env`` /
``child_argv`` shape): cwd = repo root, ``PYTHONPATH`` = repo root,
``python -m middleware.src.sidecar``.
"""

from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURES = REPO_ROOT / "frontend" / "src" / "hostclient" / "__tests__" / "fixtures"


class SidecarClient:
    def __init__(self, *extra_argv: str) -> None:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(REPO_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "middleware.src.sidecar", *extra_argv],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=str(REPO_ROOT),
            env=env,
        )
        assert self.proc.stdin is not None and self.proc.stdout is not None
        self._lines: queue.Queue[str] = queue.Queue()
        self._reader = threading.Thread(target=self._pump, daemon=True)
        self._reader.start()

    def _pump(self) -> None:
        assert self.proc.stdout is not None
        for line in self.proc.stdout:
            self._lines.put(line)

    def send(self, frame: dict[str, Any]) -> None:
        assert self.proc.stdin is not None
        self.proc.stdin.write(json.dumps(frame) + "\n")
        self.proc.stdin.flush()

    def send_raw(self, line: str) -> None:
        assert self.proc.stdin is not None
        self.proc.stdin.write(line + "\n")
        self.proc.stdin.flush()

    def read_line(self, timeout_s: float = 10.0) -> str:
        return self._lines.get(timeout=timeout_s)

    def read_frame(self, timeout_s: float = 10.0) -> dict[str, Any]:
        return json.loads(self.read_line(timeout_s))

    def read_response(self, skip_events: bool = True, timeout_s: float = 10.0) -> dict[str, Any]:
        """Next response frame; event frames (``channel`` key) are collected."""
        while True:
            frame = self.read_frame(timeout_s)
            if "channel" in frame and skip_events:
                continue
            return frame

    def handshake(self, version: str = "1.0.0", protocol: str = "image-toolkit-bridge") -> dict[str, Any]:
        self.send(
            {
                "jsonrpc": "2.0",
                "id": "handshake",
                "method": "system.handshake",
                "params": {"protocol": protocol, "client": {"name": "pytest", "version": version}},
            }
        )
        return self.read_response()

    def close(self) -> None:
        if self.proc.stdin is not None:
            self.proc.stdin.close()
        self.proc.wait(timeout=10.0)

    def kill(self) -> None:
        self.proc.kill()
        self.proc.wait(timeout=10.0)

    def stderr_text(self, timeout_s: float = 10.0) -> str:
        assert self.proc.stderr is not None
        self.proc.wait(timeout=timeout_s)
        return self.proc.stderr.read()
