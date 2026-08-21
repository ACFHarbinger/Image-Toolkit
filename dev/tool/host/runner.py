"""D1 runner integration: launch a named workflow under telemetry.

Each explicit verb (build/test/app/bench/repro) runs a fixed command with
IMAGE_TOOLKIT_TELEMETRY=1 and records a Session manifest carrying the
command, cwd, env snapshot, and exit status -- so a crash/hang/failure is
attributable to a specific command + environment, not an orphan JSONL.

No arbitrary shell execution (D27): only the named workflows wired here.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..model import list_sessions
from .git import git_state

# Env keys worth recording in a manifest (no secrets, no large blobs).
_ENV_ALLOWLIST = (
    "HOME",
    "PATH",
    "DISPLAY",
    "WAYLAND_DISPLAY",
    "XDG_SESSION_TYPE",
    "QT_QPA_PLATFORM",
    "QT_FFMPEG_DECODING_HW_DEVICE_TYPES",
    "PYTHONPATH",
    "VIRTUAL_ENV",
)


def env_snapshot(env: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """Curated subset of the environment (allowlist only)."""
    src = env if env is not None else os.environ
    return {key: src[key] for key in _ENV_ALLOWLIST if key in src}


@dataclass
class RunRecord:
    """One attributable workflow run."""

    verb: str
    command: List[str]
    cwd: str
    exit_code: int
    started_at: float
    ended_at: float
    env: Dict[str, str] = field(default_factory=dict)
    git: Dict[str, Any] = field(default_factory=dict)
    session_path: Optional[str] = None
    manifest_path: Optional[str] = None
    stdout: str = ""
    stderr: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "format": "tool.run",
            "version": 1,
            "verb": self.verb,
            "command": self.command,
            "cwd": self.cwd,
            "exit_code": self.exit_code,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "duration_s": round(self.ended_at - self.started_at, 3),
            "env": self.env,
            "git": self.git,
            "session": self.session_path,
        }


def _newest_session(after: float, directory: Optional[Path] = None) -> Optional[Path]:
    """Newest telemetry JSONL modified at/after *after* (the run's session)."""
    sessions = [s for s in list_sessions(directory) if s.stat().st_mtime >= after]
    return max(sessions, key=lambda p: p.stat().st_mtime) if sessions else None


def run_workflow(
    verb: str,
    command: List[str],
    *,
    cwd: Optional[Path] = None,
    env_extra: Optional[Dict[str, str]] = None,
    telemetry_dir: Optional[Path] = None,
    capture_output: bool = True,
    check: bool = False,
) -> RunRecord:
    """Run *command* under telemetry and record an attributable RunRecord.

    Writes a <session>.manifest.json (well, a .run.json sidecar) when the run
    produced a telemetry session, so command/cwd/env/exit-status ride
    alongside the JSONL.
    """
    cwd = Path(cwd) if cwd is not None else Path.cwd()
    env = os.environ.copy()
    env["IMAGE_TOOLKIT_TELEMETRY"] = "1"
    if env_extra:
        env.update(env_extra)

    started = time.time()
    if capture_output:
        proc = subprocess.run(
            command, cwd=str(cwd), env=env, capture_output=True, text=True
        )
        stdout, stderr = proc.stdout, proc.stderr
    else:
        proc = subprocess.run(command, cwd=str(cwd), env=env, check=check)
        stdout = stderr = ""
    ended = time.time()

    session_path = _newest_session(started, directory=telemetry_dir)
    record = RunRecord(
        verb=verb,
        command=list(command),
        cwd=str(cwd),
        exit_code=proc.returncode,
        started_at=started,
        ended_at=ended,
        env=env_snapshot(env),
        git=git_state(cwd),
        session_path=str(session_path) if session_path else None,
        stdout=stdout,
        stderr=stderr,
    )

    if session_path is not None:
        record.manifest_path = str(_write_run_manifest(session_path, record))
    return record


def _write_run_manifest(session_path: Path, record: RunRecord) -> Path:
    dest = session_path.with_suffix(session_path.suffix + ".run.json")
    payload = {
        "format": "tool.session",
        "version": 1,
        "session": str(session_path),
        "run": record.to_dict(),
    }
    dest.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return dest


__all__ = ["RunRecord", "env_snapshot", "run_workflow"]
