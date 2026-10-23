"""Spawn, reattach and poll sibling child processes."""

from __future__ import annotations

import contextlib
import json
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

# Keep process startup light: importing middleware.src.constants.paths through
# the package executes every constants module, including NumPy-backed animation
# constants. The supervisor and bridge children need only the checkout root.
ROOT_DIR = Path(__file__).resolve().parents[3]

SIDECAR = "sidecar"
CLOUD_JOBS = "cloud_jobs"
SLIDESHOW = "slideshow"
CHILD_NAMES = (SIDECAR, CLOUD_JOBS, SLIDESHOW)
DURABLE = frozenset({CLOUD_JOBS, SLIDESHOW})


@dataclass
class ChildHandle:
    name: str
    pid: int
    durable: bool
    proc: subprocess.Popen[bytes] | subprocess.Popen[str] | None
    lease_stdin: object | None = None


def child_dir(data_dir: Path) -> Path:
    path = data_dir / "supervisor"
    path.mkdir(parents=True, exist_ok=True)
    return path


def pid_path(data_dir: Path, name: str) -> Path:
    return child_dir(data_dir) / f"{name}.pid"


def heartbeat_path(data_dir: Path, name: str) -> Path:
    return child_dir(data_dir) / f"{name}.heartbeat"


def fake_child_argv(role: str, data_dir: Path) -> list[str]:
    return [
        sys.executable,
        "-m",
        "middleware.src.supervisor.fake_child",
        "--role",
        role,
        "--data-dir",
        str(data_dir),
    ]


def sidecar_argv(data_dir: Path, *, python_executable: str | None = None) -> list[str]:
    """Real #876 sidecar command with an explicit installed runtime."""
    return [
        python_executable or sys.executable,
        "-m",
        "middleware.src.sidecar",
        "--data-dir",
        str(data_dir),
    ]


def child_env() -> dict[str, str]:
    env = os.environ.copy()
    root = str(ROOT_DIR)
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = root if not existing else os.pathsep.join([root, existing])
    return env


def is_pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return not _is_zombie(pid)


def _is_zombie(pid: int) -> bool:
    try:
        text = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
    except OSError:
        return False
    rparen = text.rfind(")")
    if rparen == -1 or rparen + 2 >= len(text):
        return False
    return text[rparen + 2] == "Z"


def child_running(handle: ChildHandle) -> bool:
    if handle.proc is not None and handle.proc.poll() is not None:
        return False
    return is_pid_alive(handle.pid)


def read_pid(data_dir: Path, name: str) -> int | None:
    path = pid_path(data_dir, name)
    try:
        pid = int(path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None
    return pid if is_pid_alive(pid) else None


def write_pid(data_dir: Path, name: str, pid: int) -> None:
    path = pid_path(data_dir, name)
    tmp = path.with_suffix(".pid.tmp")
    tmp.write_text(str(pid), encoding="utf-8")
    tmp.replace(path)


def spawn(
    name: str,
    data_dir: Path,
    argv: list[str] | None = None,
    *,
    use_real_sidecar: bool = False,
    python_executable: str | None = None,
    lease_wait: bool = False,
    supervisor_session: str | None = None,
) -> ChildHandle:
    real_sidecar = name == SIDECAR and use_real_sidecar and argv is None
    if argv is not None:
        cmd = argv
    elif real_sidecar:
        cmd = sidecar_argv(data_dir, python_executable=python_executable)
    else:
        cmd = fake_child_argv(name, data_dir)
    env = child_env()
    if supervisor_session:
        env["ITK_SUPERVISOR_SESSION"] = supervisor_session
    if lease_wait:
        env["IMAGE_TOOLKIT_WAIT_LEASE"] = "1"
    proc = subprocess.Popen(
        cmd,
        start_new_session=True,
        env=env,
        cwd=str(ROOT_DIR),
        # A supervisor-owned real sidecar waits on an open stdin pipe; protocol
        # clients own a separate piped sidecar process until the shell attach
        # path is wired. Lease delivery uses the same private pipe and never argv.
        stdin=subprocess.PIPE if real_sidecar or lease_wait else None,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=lease_wait,
    )
    write_pid(data_dir, name, proc.pid)
    return ChildHandle(
        name=name,
        pid=proc.pid,
        durable=name in DURABLE,
        proc=proc,
        lease_stdin=proc.stdin if lease_wait else None,
    )


def reattach(name: str, data_dir: Path) -> ChildHandle | None:
    pid = read_pid(data_dir, name)
    if pid is None:
        return None
    return ChildHandle(name=name, pid=pid, durable=name in DURABLE, proc=None)


def terminate(handle: ChildHandle, timeout_s: float = 2.0) -> None:
    if handle.lease_stdin is not None:
        with contextlib.suppress(OSError):
            handle.lease_stdin.close()
        handle.lease_stdin = None
    if not is_pid_alive(handle.pid):
        return
    try:
        os.kill(handle.pid, signal.SIGTERM)
    except OSError:
        return
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if not is_pid_alive(handle.pid):
            return
        if handle.proc is not None and handle.proc.poll() is not None:
            return
        time.sleep(0.02)
    try:
        os.kill(handle.pid, signal.SIGKILL)
    except OSError:
        return


def heartbeat(data_dir: Path, name: str) -> dict[str, object] | None:
    path = heartbeat_path(data_dir, name)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
