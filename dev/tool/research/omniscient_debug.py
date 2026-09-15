"""Omniscient-debug research queries (Track B Phase 7, #399).

Pure-Python analyses over a :class:`ReplayTrace` / telemetry ``Session``.
Nothing here records a process (no ``rr``, no Pernosco):

- :func:`occurrences`: Pernosco-style "every time this line/event fired".
- :func:`state_at`: in-flight spans + prefix of the timeline at time ``t``.
- :func:`reverse_watch`: last write of a field at or before ``t``.
- :func:`suspicious_interleavings`: overlapping worker windows + orphans.
- :func:`delta_debug_events`: ddmin over the event list for a predicate.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Sequence

from ..model.replay_trace import ReplayEvent, ReplayTrace
from ..model.session import Session


def occurrences(trace: ReplayTrace, needle: str) -> List[ReplayEvent]:
    """Every step whose name or payload values contain ``needle``."""
    if not needle:
        return []
    found: List[ReplayEvent] = []
    for event in trace.events:
        if needle in event.name:
            found.append(event)
            continue
        if any(needle in str(v) for v in event.payload.values()):
            found.append(event)
    return found


def state_at(session: Session, t: float) -> Dict[str, Any]:
    """Queryable 'current point in time': in-flight spans and events ≤ t."""
    prefix = [e for e in session.events if float(e.get("t", 0)) <= t]
    in_flight = session.in_flight_at(t)
    return {
        "t": t,
        "n_events": len(prefix),
        "in_flight": [
            {
                "event": s.name,
                "start": s.start,
                "end": s.end,
            }
            for s in in_flight
        ],
        "last_event": prefix[-1] if prefix else None,
    }


def reverse_watch(
    trace: ReplayTrace, field: str, *, at_t: float, value: Any = None
) -> ReplayEvent | None:
    """Last event at or before ``at_t`` that wrote ``field`` (optional value)."""
    last: ReplayEvent | None = None
    for event in trace.events:
        if event.t > at_t:
            break
        if field not in event.payload:
            continue
        if value is not None and event.payload[field] != value:
            continue
        last = event
    return last


def suspicious_interleavings(session: Session) -> Dict[str, Any]:
    """Overlapping worker windows and orphaned spans — the flaky-test lead."""
    overlaps = [
        {
            "a": a_label,
            "b": b_label,
            "a_start": a_start,
            "a_end": a_end,
            "b_start": b_start,
            "b_end": b_end,
        }
        for a_label, b_label, a_start, a_end, b_start, b_end in session.overlapping_windows()
    ]
    orphans = [
        {
            "event": s.name,
            "start": s.start,
        }
        for s in session.orphaned_spans()
    ]
    return {"overlaps": overlaps, "orphans": orphans}


def delta_debug_events(
    events: Sequence[Dict[str, Any]],
    predicate: Callable[[List[Dict[str, Any]]], bool],
) -> List[Dict[str, Any]]:
    """Minimize ``events`` while ``predicate`` stays true (classic ddmin).

    If the full list fails the predicate, return it unchanged. Granularity
    starts at 2 subsets and doubles until a 1-event complement is tried.
    """
    items = list(events)
    current = list(range(len(items)))

    def pick(idxs: List[int]) -> List[Dict[str, Any]]:
        return [items[i] for i in idxs]

    if not current or not predicate(pick(current)):
        return items
    n = 2
    while True:
        size = max(1, len(current) // n)
        chunks = [current[i : i + size] for i in range(0, len(current), size)]
        reduced = False
        for chunk in chunks:
            drop = set(chunk)
            complement = [i for i in current if i not in drop]
            if complement and predicate(pick(complement)):
                current = complement
                n = max(n - 1, 2)
                reduced = True
                break
        if reduced:
            continue
        if n >= len(current):
            return pick(current)
        n = min(len(current), n * 2)


__all__ = [
    "delta_debug_events",
    "occurrences",
    "reverse_watch",
    "state_at",
    "suspicious_interleavings",
]
