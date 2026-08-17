"""Cross-session diff (A5 / A2's diff subcommand).

diff(a, b) compares two Sessions: event-set deltas (events present in one
but not the other, by (category, event)), per-category count deltas, timing
deltas (start/end/duration), and orphaned-span deltas. Pure and deterministic.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict

from debugtool import Session


def _event_key(e: Dict[str, Any]) -> tuple:
    return (e.get("category", "?"), e.get("event", ""))


def diff_sessions(a: Session, b: Session) -> Dict[str, Any]:
    """Compare b against a; returns a serializable diff dict."""
    a_keys = Counter(_event_key(e) for e in a.events)
    b_keys = Counter(_event_key(e) for e in b.events)
    only_a = {k: v for k, v in (a_keys - b_keys).items()}
    only_b = {k: v for k, v in (b_keys - a_keys).items()}

    a_cats = Counter(e.get("category", "?") for e in a.events)
    b_cats = Counter(e.get("category", "?") for e in b.events)
    cat_delta = {
        k: b_cats.get(k, 0) - a_cats.get(k, 0)
        for k in set(a_cats) | set(b_cats)
        if b_cats.get(k, 0) != a_cats.get(k, 0)
    }

    a_orphans = {s.name for s in a.orphaned_spans()}
    b_orphans = {s.name for s in b.orphaned_spans()}

    return {
        "a_pid": a.pid,
        "b_pid": b.pid,
        "a_events": len(a.events),
        "b_events": len(b.events),
        "event_count_delta": len(b.events) - len(a.events),
        "only_in_a": {f"{c}/{e}": n for (c, e), n in only_a.items()},
        "only_in_b": {f"{c}/{e}": n for (c, e), n in only_b.items()},
        "category_deltas": cat_delta,
        "timing": {
            "a_start": a.start_time,
            "b_start": b.start_time,
            "a_duration": a.duration,
            "b_duration": b.duration,
            "duration_delta": b.duration - a.duration,
        },
        "orphaned": {
            "a": sorted(a_orphans),
            "b": sorted(b_orphans),
            "new_in_b": sorted(b_orphans - a_orphans),
            "resolved_in_b": sorted(a_orphans - b_orphans),
        },
    }


def format_diff(diff: Dict[str, Any]) -> str:
    """Human-readable multi-line rendering of diff_sessions()."""
    lines = [
        f"diff pid {diff['a_pid']} -> {diff['b_pid']}",
        f"  events: {diff['a_events']} -> {diff['b_events']} (delta {diff['event_count_delta']:+d})",
        f"  duration: {diff['timing']['a_duration']:.3f}s -> {diff['timing']['b_duration']:.3f}s "
        f"(delta {diff['timing']['duration_delta']:+.3f}s)",
    ]
    if diff["only_in_a"]:
        lines.append("  only in a:")
        for k, n in sorted(diff["only_in_a"].items()):
            lines.append(f"    {k} x{n}")
    if diff["only_in_b"]:
        lines.append("  only in b:")
        for k, n in sorted(diff["only_in_b"].items()):
            lines.append(f"    {k} x{n}")
    if diff["category_deltas"]:
        lines.append("  category deltas:")
        for k, d in sorted(diff["category_deltas"].items()):
            lines.append(f"    {k}: {d:+d}")
    if diff["orphaned"]["new_in_b"]:
        lines.append(f"  new orphaned in b: {', '.join(diff['orphaned']['new_in_b'])}")
    if diff["orphaned"]["resolved_in_b"]:
        lines.append(f"  resolved in b: {', '.join(diff['orphaned']['resolved_in_b'])}")
    return "".join(lines)


__all__ = ["diff_sessions", "format_diff"]
