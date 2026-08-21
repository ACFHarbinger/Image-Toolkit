"""Git provenance for Session / Investigation manifests (D2).

Records commit, branch, and a dirty-tree hash. No new telemetry event
fields — this is manifest metadata only.
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional


def _git(cwd: Path, *args: str) -> Optional[str]:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or ""


def git_state(cwd: Optional[Path] = None) -> Dict[str, Any]:
    """Return ``{commit, branch, dirty, dirty_hash}`` for *cwd* (or repo root)."""
    root = Path(cwd) if cwd is not None else Path.cwd()
    commit = _git(root, "rev-parse", "HEAD")
    if commit is None:
        return {
            "commit": None,
            "branch": None,
            "dirty": False,
            "dirty_hash": None,
        }
    branch = _git(root, "rev-parse", "--abbrev-ref", "HEAD") or None
    porcelain = _git(root, "status", "--porcelain") or ""
    dirty = bool(porcelain.strip())
    dirty_hash = None
    if dirty:
        dirty_hash = hashlib.sha256(porcelain.encode("utf-8")).hexdigest()[:12]
    return {
        "commit": commit,
        "branch": branch,
        "dirty": dirty,
        "dirty_hash": dirty_hash,
    }


def write_session_manifest(session_path: Path, extra: Optional[Dict[str, Any]] = None) -> Path:
    """Write ``<session>.manifest.json`` next to a telemetry JSONL file."""
    import json

    path = Path(session_path)
    dest = path.with_suffix(path.suffix + ".manifest.json")
    payload: Dict[str, Any] = {
        "format": "tool.session",
        "version": 1,
        "session": str(path),
        "git": git_state(path.parent),
    }
    if extra:
        payload.update(extra)
    dest.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return dest


__all__ = ["git_state", "write_session_manifest"]
