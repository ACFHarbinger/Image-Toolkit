"""Telemetry JSONL -> ``devtool.record`` adapter (#409, lock #9).

The generic Record schema (:mod:`.record`) is what Tauri/TUI/MCP read from
day one; this module is the *only* place that still knows telemetry JSONL's
own shape (auto fields, ``<event>.start``/``.end``/``.error`` span markers).
Everything downstream of :func:`records_from_session` sees Records, never
raw telemetry dicts.
"""

from __future__ import annotations

from typing import List

from .record import Record
from .session import _SPAN_SUFFIXES, Session, Span

DEFAULT_SOURCE = "telemetry"


def _span_to_record(span: Span, workspace: str, source: str) -> Record:
    return Record(
        kind="span",
        start_ms=span.start * 1000.0,
        end_ms=span.end * 1000.0 if span.end is not None else None,
        source=source,
        workspace=workspace,
        payload={
            "name": span.name,
            "category": span.category,
            "tid": span.tid,
            "span_id": span.span_id,
            "parent_span_id": span.parent_span_id,
            "ended_ok": span.ended_ok,
        },
    )


def _is_span_marker(event_name: str) -> bool:
    return isinstance(event_name, str) and event_name.endswith(_SPAN_SUFFIXES)


def _event_to_record(event: dict, workspace: str, source: str) -> Record:
    return Record(
        kind="event",
        start_ms=float(event.get("t", 0)) * 1000.0,
        end_ms=None,
        source=source,
        workspace=workspace,
        payload=dict(event),
    )


def records_from_session(session: Session, workspace: str, source: str = DEFAULT_SOURCE) -> List[Record]:
    """Adapt one telemetry :class:`Session` into ``devtool.record`` records.

    Reconstructed spans become ``kind="span"`` records (this is what the 4D
    pipeline scrubber, #418, and the 3D flame/flow views read). Events that
    are not part of any span's start/end/error markers become standalone
    ``kind="event"`` records so nothing in the JSONL is silently dropped.
    """
    records: List[Record] = [_span_to_record(span, workspace, source) for span in session.spans()]
    for event in session.events:
        if not _is_span_marker(event.get("event", "")):
            records.append(_event_to_record(event, workspace, source))
    records.sort(key=lambda r: r.start_ms)
    return records


__all__ = ["DEFAULT_SOURCE", "records_from_session"]
