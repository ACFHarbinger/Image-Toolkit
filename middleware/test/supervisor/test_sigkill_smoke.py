"""SIGKILL the supervisor process; durable fakes survive and reattach (#877)."""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from middleware.src.constants.paths import ROOT_DIR
from middleware.src.supervisor.children import (
    CHILD_NAMES,
    CLOUD_JOBS,
    SIDECAR,
    SLIDESHOW,
    child_env,
    is_pid_alive,
    pid_path,
    read_pid,
)
from middleware.src.supervisor.supervisor import Supervisor


def _wait_pid_files(data_dir: Path, timeout_s: float = 5.0) -> dict[str, int]:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        pids = {}
        for name in CHILD_NAMES:
            try:
                pids[name] = int(pid_path(data_dir, name).read_text().strip())
            except (OSError, ValueError):
                pids = {}
                break
        if pids and all(is_pid_alive(pid) for pid in pids.values()):
            return pids
        time.sleep(0.05)
    raise AssertionError("child pid files not ready")


def test_supervisor_sigkill_reattach(tmp_path) -> None:
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "middleware.src.supervisor",
            "--data-dir",
            str(tmp_path),
            "--foreground",
        ],
        cwd=str(ROOT_DIR),
        env=child_env(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    try:
        pids = _wait_pid_files(tmp_path)
        os.kill(proc.pid, signal.SIGKILL)
        proc.wait(timeout=5)
        assert is_pid_alive(pids[CLOUD_JOBS])
        assert is_pid_alive(pids[SLIDESHOW])
        # sidecar may still be alive too; supervisor death must not reap siblings
        assert is_pid_alive(pids[SIDECAR])

        replacement = Supervisor(tmp_path, poll_interval_s=0.05)
        replacement.start()
        try:
            replacement.wait_until_ready(timeout_s=5)
            kids = replacement.children
            assert kids[CLOUD_JOBS].pid == pids[CLOUD_JOBS]
            assert kids[SLIDESHOW].pid == pids[SLIDESHOW]
            assert kids[SIDECAR].pid == pids[SIDECAR]
        finally:
            replacement.stop()
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=2)
        for name in CHILD_NAMES:
            leftover = read_pid(tmp_path, name)
            if leftover is None:
                continue
            with contextlib.suppress(OSError):
                os.kill(leftover, signal.SIGKILL)
