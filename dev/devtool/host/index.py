"""Telemetry sidecar index (A2).

A single JSON index over discovered sessions: pid -> {path, events, start,
end, categories, orphaned_spans}. Written to index.json next to the telemetry
files (default ~/.image-toolkit/telemetry/index.json), so tools and agents can
discover sessions without re-parsing every JSONL.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from debugtool import TELEMETRY_DIR, Session

from .store import WorkspaceStore

INDEX_FILENAME = "index.json"


def index_path(store: WorkspaceStore) -> Path:
    base = store.telemetry_dir or TELEMETRY_DIR
    return Path(base) / INDEX_FILENAME


def build_index(store: WorkspaceStore) -> Dict[int, Dict[str, Any]]:
    """Map pid -> session summary for every discovered session."""
    index: Dict[int, Dict[str, Any]] = {}
    for path in store.sessions():
        session = Session.open(path)
        index[session.pid] = {
            "path": str(path),
            "events": len(session.events),
            "start": session.start_time,
            "end": session.end_time,
            "duration": session.duration,
            "categories": session.category_counts(),
            "orphaned_spans": len(session.orphaned_spans()),
        }
    return index


def write_index(store: WorkspaceStore) -> Path:
    """Write the sidecar index; returns the path written."""
    path = index_path(store)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(build_index(store), indent=2), encoding="utf-8")
    return path


__all__ = ["INDEX_FILENAME", "build_index", "index_path", "write_index"]
