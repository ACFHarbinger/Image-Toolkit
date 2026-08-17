"""Typed event model.

A telemetry JSONL line is a flat dict with auto fields (t, wall, pid, tid,
tname, category, event) plus arbitrary caller fields. :class:`Event` is a
frozen, immutable view over one such line: the host/plugins read events
through this instead of raw dicts so the schema contract lives in one place.
Unknown fields are preserved verbatim, never dropped.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

_AUTO_FIELDS = ("t", "wall", "pid", "tid", "tname", "category", "event")


@dataclass(frozen=True)
class Event:
    """One telemetry event (immutable)."""

    t: float
    category: str
    event: str
    pid: Optional[int] = None
    tid: Optional[int] = None
    tname: Optional[str] = None
    fields: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Event":
        """Build an Event from a raw telemetry line, splitting auto fields
        from caller fields."""
        return cls(
            t=float(d.get("t", 0)),
            category=d.get("category", "?"),
            event=d.get("event", ""),
            pid=d.get("pid"),
            tid=d.get("tid"),
            tname=d.get("tname"),
            fields={k: v for k, v in d.items() if k not in _AUTO_FIELDS},
        )

    def get(self, key: str, default: Any = None) -> Any:
        """Look up a caller field (auto fields live on the dataclass)."""
        return self.fields.get(key, default)


__all__ = ["Event"]
