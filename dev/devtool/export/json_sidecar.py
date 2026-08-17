"""JSON sidecar export: a Session serialized as a stable dict.

The sidecar is the machine-readable summary of one session -- pid, path,
event/thread counts, category counts, spans (with duration + orphaned flag),
and orphaned spans. It is the format the sidecar index and downstream
consumers (web, MCP, diff) read.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from debugtool import Session


def span_to_dict(span) -> Dict[str, Any]:
    return {
        "tid": span.tid,
        "category": span.category,
        "name": span.name,
        "start": span.start,
        "end": span.end,
        "ended_ok": span.ended_ok,
        "duration_ms": span.duration_ms,
        "orphaned": span.orphaned,
        "span_id": span.span_id,
        "parent_span_id": span.parent_span_id,
    }


def session_to_dict(session: Session) -> Dict[str, Any]:
    """Stable sidecar dict for a session."""
    spans = session.spans()
    return {
        "pid": session.pid,
        "path": str(session.path),
        "events": len(session.events),
        "start_time": session.start_time,
        "end_time": session.end_time,
        "duration": session.duration,
        "truncated_final_line": session.truncated_final_line,
        "categories": session.category_counts(),
        "threads": [{"tid": tid, "name": name} for tid, name in session.thread_ids()],
        "spans": [span_to_dict(s) for s in spans],
        "orphaned_spans": [span_to_dict(s) for s in spans if s.orphaned],
    }


def write_sidecar(session: Session, path: Path) -> Path:
    """Write the sidecar JSON; returns the path written."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(session_to_dict(session), indent=2), encoding="utf-8")
    return path


__all__ = ["session_to_dict", "span_to_dict", "write_sidecar"]
