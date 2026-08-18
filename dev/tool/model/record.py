"""``devtool.record`` — the generic evidence record schema (#409, lock #9).

Grok's second brainstorm locked this in the first sidecar slice: Tauri, TUI,
and MCP all read ``devtool.record`` from day one rather than each shell
parsing raw telemetry JSONL (or any other evidence source) itself. Existing
telemetry becomes an *adapter* behind this schema, not a second on-disk
format the shells keep independently parsing.

A record is intentionally generic (kind/start_ms/end_ms/source/workspace/
payload) so future evidence producers (crash bundles, benchmark runs,
Investigation bookmarks, a non-Python plugin's own artifacts) can all be
represented the same way without inventing a new shape each time. ``payload``
carries whatever is kind-specific; nothing here interprets it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

SCHEMA = "devtool.record"
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class Record:
    """One generic evidence record.

    - ``kind``: what this is ("span", "event", "crash", ...). Open-ended;
      consumers filter/branch on it, producers invent new kinds freely.
    - ``start_ms`` / ``end_ms``: milliseconds since the Unix epoch.
      ``end_ms`` is ``None`` for an instantaneous or still-open record (an
      orphaned span, D52's pipeline scrubber (#418) reads exactly this pair
      for its ``t_ms`` evaluation window).
    - ``source``: which evidence producer created this record (e.g.
      ``"telemetry"``, a plugin name).
    - ``workspace``: the workspace root this record belongs to.
    - ``payload``: kind-specific data, opaque to this schema.
    """

    kind: str
    start_ms: float
    source: str
    workspace: str
    end_ms: Optional[float] = None
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema": SCHEMA,
            "schema_version": SCHEMA_VERSION,
            "kind": self.kind,
            "start_ms": self.start_ms,
            "end_ms": self.end_ms,
            "source": self.source,
            "workspace": self.workspace,
            "payload": self.payload,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Record":
        return cls(
            kind=d["kind"],
            start_ms=float(d["start_ms"]),
            end_ms=float(d["end_ms"]) if d.get("end_ms") is not None else None,
            source=d.get("source", ""),
            workspace=d.get("workspace", ""),
            payload=dict(d.get("payload") or {}),
        )

    @property
    def duration_ms(self) -> Optional[float]:
        if self.end_ms is None:
            return None
        return self.end_ms - self.start_ms


def records_to_dicts(records: List[Record]) -> List[Dict[str, Any]]:
    return [r.to_dict() for r in records]


__all__ = ["SCHEMA", "SCHEMA_VERSION", "Record", "records_to_dicts"]
