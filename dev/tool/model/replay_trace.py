"""Omniscient-debug models (Track B Phase 7, issue #399).

Host attachment: optional later CrashBundle backend. gdb remains the v1
crash-capture path — this module does not wrap ``rr``, spawn Pernosco, or
replace :class:`CrashBundle`. It is a Pernosco-style *query layer* over
artifacts the host already has:

- :class:`ReplayTrace`: a time-ordered, queryable view of a telemetry
  ``Session`` (and, if present, a recorded ``rr`` sidecar JSON). Instruction-
  accurate recording stays with ``rr`` itself; we never invoke it.
- :class:`BugCapsule`: content-addressable digest of a crash bundle
  (event log + optional gdb text + notes). The CI "load the capsule"
  story attaches here later; the digest is the stable id.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .crash_bundle import CrashBundle
from .session import Session


@dataclass(frozen=True)
class ReplayEvent:
    """One queryable step on a replay timeline."""

    t: float
    kind: str  # "user" | "syscall" | "sched"
    name: str
    thread: Optional[int] = None
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "t": self.t,
            "kind": self.kind,
            "name": self.name,
            "thread": self.thread,
            "payload": dict(self.payload),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReplayEvent":
        return cls(
            t=float(data["t"]),
            kind=str(data.get("kind", "user")),
            name=str(data.get("name", "")),
            thread=data.get("thread"),
            payload=dict(data.get("payload") or {}),
        )

    @classmethod
    def from_telemetry(cls, raw: Dict[str, Any]) -> "ReplayEvent":
        auto = {"t", "wall", "pid", "tid", "tname", "category", "event"}
        return cls(
            t=float(raw.get("t", 0)),
            kind="user",
            name=str(raw.get("event", "")),
            thread=raw.get("tid"),
            payload={k: v for k, v in raw.items() if k not in auto},
        )


@dataclass
class ReplayTrace:
    """Queryable execution timeline. Backend is ``telemetry`` or ``rr``."""

    backend: str
    events: List[ReplayEvent] = field(default_factory=list)
    gdb_backtrace: Optional[str] = None
    sidecar_path: Optional[Path] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "backend": self.backend,
            "events": [e.to_dict() for e in self.events],
            "gdb_backtrace": self.gdb_backtrace,
            "sidecar_path": str(self.sidecar_path) if self.sidecar_path else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReplayTrace":
        sidecar = data.get("sidecar_path")
        return cls(
            backend=str(data["backend"]),
            events=[ReplayEvent.from_dict(e) for e in data.get("events") or []],
            gdb_backtrace=data.get("gdb_backtrace"),
            sidecar_path=Path(sidecar) if sidecar else None,
        )

    @classmethod
    def from_session(
        cls, session: Session, gdb_output: Optional[Path] = None
    ) -> "ReplayTrace":
        gdb_text = None
        if gdb_output is not None:
            path = Path(gdb_output)
            if path.is_file():
                gdb_text = path.read_text(encoding="utf-8", errors="replace")
        return cls(
            backend="telemetry",
            events=[ReplayEvent.from_telemetry(e) for e in session.events],
            gdb_backtrace=gdb_text,
        )

    @classmethod
    def from_crash_bundle(cls, bundle: CrashBundle) -> "ReplayTrace":
        return cls.from_session(bundle.session, gdb_output=bundle.gdb_output)

    @classmethod
    def from_rr_sidecar(cls, path: Path) -> "ReplayTrace":
        """Load a recorded rr sidecar. Never invokes the ``rr`` binary.

        Expected JSON::

            {"backend": "rr", "events": [{"t", "kind", "name", "thread?", "payload?"}]}
        """
        path = Path(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("backend") != "rr":
            raise ValueError(f"rr sidecar {path} has backend={data.get('backend')!r}")
        events = [ReplayEvent.from_dict(e) for e in data.get("events") or []]
        events.sort(key=lambda e: e.t)
        return cls(backend="rr", events=events, sidecar_path=path)


@dataclass(frozen=True)
class BugCapsule:
    """Content-addressable replayable bundle id (Phase 7.2).

    The digest covers the canonical event log, gdb text, and notes — not
    filesystem snapshots or packets (those attach when a real rr backend
    lands). Same inputs always yield the same digest.
    """

    digest: str
    backend: str
    pid: int
    n_events: int
    gdb_present: bool
    notes: tuple[str, ...] = ()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "digest": self.digest,
            "backend": self.backend,
            "pid": self.pid,
            "n_events": self.n_events,
            "gdb_present": self.gdb_present,
            "notes": list(self.notes),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BugCapsule":
        return cls(
            digest=str(data["digest"]),
            backend=str(data["backend"]),
            pid=int(data["pid"]),
            n_events=int(data["n_events"]),
            gdb_present=bool(data["gdb_present"]),
            notes=tuple(data.get("notes") or ()),
        )

    @classmethod
    def from_crash_bundle(cls, bundle: CrashBundle) -> "BugCapsule":
        gdb_text = ""
        if bundle.gdb_output is not None and Path(bundle.gdb_output).is_file():
            gdb_text = Path(bundle.gdb_output).read_text(encoding="utf-8", errors="replace")
        notes = tuple(bundle.notes)
        payload = {
            "events": bundle.session.events,
            "gdb": gdb_text,
            "notes": list(notes),
        }
        canonical = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return cls(
            digest=digest,
            backend="gdb" if gdb_text else "telemetry",
            pid=bundle.session.pid,
            n_events=len(bundle.session.events),
            gdb_present=bool(gdb_text),
            notes=notes,
        )


__all__ = ["BugCapsule", "ReplayEvent", "ReplayTrace"]
