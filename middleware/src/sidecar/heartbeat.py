"""Supervisor heartbeat for the sidecar.

Writes ``<data_dir>/supervisor/sidecar.heartbeat`` with the same payload
shape as ``supervisor.fake_child`` — the supervisor's readiness gate
(``bridge.ready`` after a restart) waits on this file matching the child
pid it spawned.
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path


class Heartbeat:
    def __init__(self, data_dir: Path, *, role: str = "sidecar", interval_s: float = 0.1) -> None:
        self._path = data_dir / "supervisor" / f"{role}.heartbeat"
        self._role = role
        self._interval_s = interval_s
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._thread = threading.Thread(target=self._run, name="itk-sidecar-heartbeat", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def _run(self) -> None:
        seq = 0
        while not self._stop.is_set():
            payload = {"role": self._role, "pid": os.getpid(), "seq": seq, "ts": time.time()}
            tmp = self._path.with_suffix(".heartbeat.tmp")
            tmp.write_text(json.dumps(payload), encoding="utf-8")
            tmp.replace(self._path)
            seq += 1
            self._stop.wait(self._interval_s)
