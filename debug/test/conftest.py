"""Shared fixtures for debugtool tests.

Creates synthetic telemetry JSONL files in a temp dir so tests never touch
the real ~/.image-toolkit/telemetry/.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def telemetry_dir(tmp_path):
    """A temp telemetry directory with a few synthetic session files."""
    root = tmp_path / "telemetry"
    root.mkdir()
    return root


def write_session(root: Path, pid: int, events: list) -> Path:
    """Write a telemetry-<pid>.jsonl file with the given event dicts."""
    path = root / f"telemetry-{pid}.jsonl"
    with open(path, "w", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")
    return path


def event(t, category, name, tid=1, tname="MainThread", **fields):
    """Build a telemetry event dict matching the real schema."""
    base = {
        "t": t,
        "wall": 1786567965.0 + t,
        "pid": 999,
        "tid": tid,
        "tname": tname,
        "category": category,
        "event": name,
    }
    base.update(fields)
    return base
