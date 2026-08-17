"""Session abstraction over telemetry JSONL files.

A Session is one process launch's telemetry (a single telemetry-<pid>.jsonl
file), parsed into a typed, queryable model. This is the foundation the whole
debugtool builds on: the analyzer's logic (orphaned spans, thread-window
overlaps) becomes queries over a Session, and the CLI / export surface /
visual timeline are consumers of the same model.

Design notes (mirroring the telemetry module's invariants):

- JSONL files are the source of truth; nothing here writes them.
- A truncated final line (process died mid-write, e.g. SIGABRT moments
  after the last completed event) is expected, not an error: every
  completed line is still exactly as reliable as before.
- Events are flat JSON with auto fields (t, wall, pid, tid, tname,
  category, event) plus arbitrary caller fields. Unknown fields/events are
  preserved verbatim, never dropped.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

TELEMETRY_DIR = Path.home() / ".image-toolkit" / "telemetry"

# A span's lifecycle markers: <event>.start / <event>.end / <event>.error.
_SPAN_SUFFIXES = (".start", ".end", ".error")


def discover_sessions(directory: Optional[Path] = None) -> List[Path]:
    """Return all telemetry-*.jsonl files under directory (default: the
    telemetry dir), sorted by mtime (oldest first)."""
    root = directory or TELEMETRY_DIR
    if not root.exists():
        return []
    return sorted(root.glob("telemetry-*.jsonl"), key=lambda p: p.stat().st_mtime)


def session_path_for_pid(pid: int, directory: Optional[Path] = None) -> Optional[Path]:
    """Return the telemetry file for a specific pid, if one exists."""
    for path in discover_sessions(directory):
        match = re.search(r"telemetry-(\d+)\.jsonl$", path.name)
        if match and int(match.group(1)) == pid:
            return path
    return None


@dataclass
class Session:
    """One process launch's parsed telemetry.

    Access the raw timeline via events (time-ordered) and the derived
    structures via the query methods (spans, orphaned spans, overlaps).
    """

    path: Path
    pid: int
    events: List[Dict[str, Any]] = field(default_factory=list)
    truncated_final_line: bool = False

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    @classmethod
    def open(cls, path: Path) -> "Session":
        """Parse one telemetry JSONL file into a Session.

        Silently drops a truncated final line (expected when the process
        crashed mid-write) and records that it happened; malformed lines in
        the middle are skipped with a warning collected on the instance.
        """
        path = Path(path)
        events: List[Dict[str, Any]] = []
        truncated = False
        malformed: List[int] = []
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                if i == len(lines) - 1:
                    truncated = True
                else:
                    malformed.append(i + 1)
        events.sort(key=lambda e: e.get("t", 0))
        pid = cls._pid_from_path(path)
        session = cls(path=path, pid=pid, events=events, truncated_final_line=truncated)
        session.malformed_lines = malformed
        return session

    @staticmethod
    def _pid_from_path(path: Path) -> int:
        match = re.search(r"telemetry-(\d+)\.jsonl$", path.name)
        return int(match.group(1)) if match else 0

    @classmethod
    def open_pid(cls, pid: int, directory: Optional[Path] = None) -> Optional["Session"]:
        path = session_path_for_pid(pid, directory)
        return cls.open(path) if path is not None else None

    # ------------------------------------------------------------------
    # Derived metadata
    # ------------------------------------------------------------------

    @property
    def start_time(self) -> Optional[float]:
        return self.events[0].get("t") if self.events else None

    @property
    def end_time(self) -> Optional[float]:
        return self.events[-1].get("t") if self.events else None

    @property
    def duration(self) -> float:
        if not self.events:
            return 0.0
        return self.end_time - self.start_time  # type: ignore[operator]

    def category_counts(self) -> Dict[str, int]:
        return dict(Counter(e.get("category", "?") for e in self.events))

    def thread_ids(self) -> List[tuple]:
        """Sorted list of (tid, tname) pairs observed."""
        return sorted({(e["tid"], e.get("tname", "?")) for e in self.events})

    def events_for(
        self, category: Optional[str] = None, event: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Filter the timeline by category and/or exact event name."""
        result = self.events
        if category is not None:
            result = [e for e in result if e.get("category") == category]
        if event is not None:
            result = [e for e in result if e.get("event") == event]
        return result

    # ------------------------------------------------------------------
    # Span reconstruction
    # ------------------------------------------------------------------

    def spans(self) -> List["Span"]:
        """Reconstruct spans from <event>.start/.end/.error markers.

        A span is keyed by (tid, category, base-name). Nested .start events
        within an open span (rare but legal) are tracked so orphan detection
        reports the innermost in flight. Returns spans in start order.
        """
        open_stack: Dict[tuple, List["Span"]] = defaultdict(list)
        spans: List[Span] = []
        for e in self.events:
            event_name = e.get("event", "")
            if not isinstance(event_name, str):
                continue
            for suffix in _SPAN_SUFFIXES:
                if event_name.endswith(suffix):
                    base = event_name[: -len(suffix)]
                    key = (e["tid"], e.get("category", ""), base)
                    if suffix == ".start":
                        span = Span(
                            tid=e["tid"],
                            category=e.get("category", ""),
                            name=base,
                            start=e["t"],
                            start_event=e,
                        )
                        open_stack[key].append(span)
                        spans.append(span)
                    elif suffix in (".end", ".error"):
                        stack = open_stack.get(key)
                        if stack:
                            span = stack.pop()
                            span.end = e["t"]
                            span.end_event = e
                            span.ended_ok = suffix == ".end"
                    break
        return spans

    def orphaned_spans(self) -> List["Span"]:
        """Spans whose .start never got a matching .end/.error.

        If the run crashed, this is direct evidence of what was in flight at
        the moment of the fault -- the query the gallery-crash investigation
        kept needing (previously find_orphaned_spans in telemetry_analyzer).
        """
        return [s for s in self.spans() if s.end is None]

    def in_flight_at(self, t: float) -> List["Span"]:
        """Spans that started before or at t and ended after t (or never
        ended) -- the what-was-happening-at-this-moment query."""
        return [s for s in self.spans() if s.start <= t and (s.end is None or s.end > t)]

    # ------------------------------------------------------------------
    # Thread-window overlap detection (generalized)
    # ------------------------------------------------------------------

    def overlapping_windows(self) -> List[tuple]:
        """Any pair of worker/lifecycle windows that overlap in time.

        Generalizes the analyzer's scanner-only detector to any
        <something>.start ... <something>.wait.end / .end / .error window
        pair. Returns (label_a, label_b, a_start, a_end, b_start, b_end).
        """
        intervals: List[tuple] = []
        open_by_worker: Dict[Any, Dict[str, Any]] = {}
        for e in self.events:
            event_name = e.get("event", "")
            worker_key = e.get("img_thread") or e.get("vid_worker") or e.get("worker")
            if (
                ".start" in event_name and worker_key is not None
            ):
                open_by_worker[worker_key] = e
            elif worker_key is not None and (
                event_name.endswith(".end")
                or event_name.endswith(".error")
                or event_name.endswith("wait.end")
                or event_name == "process_video_task.end"
            ):
                start_e = open_by_worker.pop(worker_key, None)
                if start_e is not None:
                    label = (
                        f"{start_e.get('event')} panel={start_e.get('panel')} "
                        f"worker={worker_key} [{start_e['t']:.3f}-{e['t']:.3f}]"
                    )
                    intervals.append((start_e["t"], e["t"], label))

        overlaps: List[tuple] = []
        for i in range(len(intervals)):
            for j in range(i + 1, len(intervals)):
                a_start, a_end, a_label = intervals[i]
                b_start, b_end, b_label = intervals[j]
                if a_start < b_end and b_start < a_end:
                    overlaps.append((a_label, b_label, a_start, a_end, b_start, b_end))
        return overlaps


@dataclass
class Span:
    """One reconstructed span: a <name>.start ... <name>.end/.error pair."""

    tid: int
    category: str
    name: str
    start: float
    start_event: Dict[str, Any]
    end: Optional[float] = None
    end_event: Optional[Dict[str, Any]] = None
    ended_ok: Optional[bool] = None

    @property
    def duration_ms(self) -> Optional[float]:
        if self.end is None:
            return None
        return (self.end - self.start) * 1000.0

    @property
    def orphaned(self) -> bool:
        return self.end is None

    def __repr__(self) -> str:
        status = "orphaned" if self.orphaned else ("ok" if self.ended_ok else "error")
        return f"Span(tid={self.tid} {self.category}/{self.name} t={self.start:.3f} {status})"


__all__ = [
    "TELEMETRY_DIR",
    "Session",
    "Span",
    "discover_sessions",
    "session_path_for_pid",
]
