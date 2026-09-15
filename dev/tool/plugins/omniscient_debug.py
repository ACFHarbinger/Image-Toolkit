"""Track B Phase 7 Omniscient Debug plugin: queryable replay over CrashBundle (#399).

Host attachment: optional later CrashBundle backend. gdb remains v1 — this
plugin never invokes ``rr`` or Pernosco. Channels carry derived query
results (occurrence lists, capsules, interleavings), never live traces.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from ..host.plugins import Artifact, Channel, PluginManifest, Surface
from ..model.crash_bundle import CrashBundle
from ..model.replay_trace import BugCapsule, ReplayTrace
from ..model.session import Session
from ..research.omniscient_debug import (
    occurrences,
    reverse_watch,
    state_at,
    suspicious_interleavings,
)

MANIFEST = PluginManifest(
    name="omniscient_debug",
    version="0.1.0",
    description=(
        "Omniscient debugging: Pernosco-style queries over recorded telemetry "
        "and optional rr sidecars; BugCapsule digests for CrashBundle (Track B Phase 7)."
    ),
    surfaces=(
        Surface("cli", "Occurrences, reverse-watch, interleavings, capsules"),
        Surface("web", "Queryable timeline, capsule list"),
        Surface("mcp", "Replay queries against a session or sidecar"),
    ),
    channels=(
        Channel("replay_trace", "Queryable replay timeline derived from telemetry or an rr sidecar", retention="30d"),
        Channel("bug_capsule", "Content-addressable CrashBundle digests", retention="forever"),
    ),
    entry_point="tool.plugins.omniscient_debug:plugin",
)


class OmniscientDebug:
    manifest = MANIFEST

    def artifacts(self, store: Any) -> List[Artifact]:
        return []

    def trace_from_events(
        self, events: List[Dict[str, Any]], *, pid: int = 0, gdb_text: Optional[str] = None
    ) -> Dict[str, Any]:
        session = Session(path=Path("."), pid=pid, events=list(events))
        trace = ReplayTrace.from_session(session)
        if gdb_text:
            trace.gdb_backtrace = gdb_text
        return trace.to_dict()

    def find_occurrences(self, events: List[Dict[str, Any]], needle: str) -> List[Dict[str, Any]]:
        trace = ReplayTrace.from_session(Session(path=Path("."), pid=0, events=list(events)))
        return [e.to_dict() for e in occurrences(trace, needle)]

    def watch(self, events: List[Dict[str, Any]], field: str, at_t: float, value: Any = None) -> Optional[Dict[str, Any]]:
        trace = ReplayTrace.from_session(Session(path=Path("."), pid=0, events=list(events)))
        hit = reverse_watch(trace, field, at_t=at_t, value=value)
        return None if hit is None else hit.to_dict()

    def snapshot(self, events: List[Dict[str, Any]], t: float) -> Dict[str, Any]:
        session = Session(path=Path("."), pid=0, events=list(events))
        return state_at(session, t)

    def interleavings(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        session = Session(path=Path("."), pid=0, events=list(events))
        return suspicious_interleavings(session)

    def capsule_from_events(
        self, events: List[Dict[str, Any]], *, pid: int = 0, notes: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        session = Session(path=Path("."), pid=pid, events=list(events))
        bundle = CrashBundle(session=session, notes=list(notes or []))
        return BugCapsule.from_crash_bundle(bundle).to_dict()

    def load_rr_sidecar(self, path: str) -> Dict[str, Any]:
        return ReplayTrace.from_rr_sidecar(Path(path)).to_dict()


plugin = OmniscientDebug()


def main(argv=None) -> int:
    """D52 command-plugin entry: python -m tool.plugins.<name> --stdio."""
    from ..host.command import run_plugin_stdio

    return run_plugin_stdio(plugin, argv=argv)


if __name__ == "__main__":
    import sys

    sys.exit(main())
