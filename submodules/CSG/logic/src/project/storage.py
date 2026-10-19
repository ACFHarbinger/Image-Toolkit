"""Atomic JSON persistence for portable projects and private learner profiles."""

from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Protocol

from .model import LearnerProfile, Project

MANIFEST_NAME = "project.json"
RECOVERY_DIR = ".recovery"


class _Serializable(Protocol):
    def to_dict(self) -> dict[str, Any]: ...


def _atomic_json_write(path: Path, value: _Serializable) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(value.to_dict(), handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    try:
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _snapshot(path: Path, revisions: int) -> None:
    if not path.exists():
        return
    recovery = path.parent / RECOVERY_DIR
    recovery.mkdir(exist_ok=True)
    for number in range(revisions, 1, -1):
        older = recovery / f"project.{number - 1}.json"
        newer = recovery / f"project.{number}.json"
        if older.exists():
            os.replace(older, newer)
    _atomic_json_write(recovery / "project.1.json", Project.from_dict(json.loads(path.read_text())))


def save_project(directory: str | Path, project: Project) -> Path:
    """Atomically save a project and maintain its configured recovery history."""
    root = Path(directory)
    manifest = root / MANIFEST_NAME
    if project.autosave.enabled:
        _snapshot(manifest, project.autosave.recovery_revisions)
    _atomic_json_write(manifest, project)
    return manifest


def load_project(directory: str | Path) -> Project:
    """Load and validate a portable project manifest."""
    payload = json.loads((Path(directory) / MANIFEST_NAME).read_text(encoding="utf-8"))
    return Project.from_dict(payload)


def save_profile(path: str | Path, profile: LearnerProfile) -> Path:
    """Atomically save the separate global learner profile."""
    destination = Path(path)
    _atomic_json_write(destination, profile)
    return destination


def load_profile(path: str | Path) -> LearnerProfile:
    """Load and validate a global learner profile."""
    return LearnerProfile.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
