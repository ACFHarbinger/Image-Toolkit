"""Human-readable analysis report over a telemetry Session.

This is the generalized successor to the original telemetry_analyzer.py
script (Phase 1 of the debug workbench roadmap): same report shape (counts
by category, threads, orphaned spans, overlapping scanner windows, last
events) plus the Session model's queries. dev/telemetry_analyzer.py
remains as a compatibility shim pointing here.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from ..model.session import Session


def format_event(e: Dict) -> str:
    fields = {
        k: v
        for k, v in e.items()
        if k not in ("t", "wall", "pid", "tid", "tname", "category", "event")
    }
    field_str = " ".join(f"{k}={v!r}" for k, v in fields.items())
    return f"t={e['t']:9.3f} tid={e['tid']} {e['category']}/{e['event']} {field_str}"


def print_report(session: Session, path=None) -> List[str]:
    """Return the full report as a list of lines (the original analyzer
    printed them; this returns them so the CLI can own output)."""
    path = path or session.path
    out = []
    out.append(f"=== {path.name} ({len(session.events)} events) ===")
    out.append("")

    if not session.events:
        out.append("No events in this file.")
        return out

    by_category = session.category_counts()
    out.append("Event counts by category:")
    for cat, count in sorted(by_category.items(), key=lambda kv: -kv[1]):
        out.append(f"  {cat:20s} {count}")
    out.append("")

    threads = session.thread_ids()
    out.append(f"Threads observed: {len(threads)}")
    for tid, tname in threads:
        out.append(f"  tid={tid} name={tname!r}")
    out.append("")

    orphaned = session.orphaned_spans()
    if orphaned:
        out.append(f"  {len(orphaned)} ORPHANED SPAN(S) -- .start with no matching .end/.error.")
        out.append("    If this run crashed, this is almost certainly what was in flight:")
        for span in orphaned:
            out.append(f"    {format_event(span.start_event)}")
    else:
        out.append("No orphaned spans (every .start had a matching .end/.error).")
    out.append("")

    overlaps = session.overlapping_windows()
    if overlaps:
        out.append(f"  {len(overlaps)} OVERLAPPING WORKER-WINDOW PAIR(S):")
        for (a_label, b_label, *_rest) in overlaps:
            out.append(f"  OVERLAP:\n    {a_label}\n    {b_label}")
    else:
        out.append("No overlapping worker-thread windows detected.")
    out.append("")

    out.append("Last 15 events (crash-adjacent, if this run crashed):")
    for e in session.events[-15:]:
        out.append(f"  {format_event(e)}")
    return out


def tail(session: Session, n: int = 40, category: Optional[str] = None) -> List[str]:
    """Return the last n events (optionally filtered by category) as lines."""
    events = session.events_for(category=category) if category else session.events
    return [format_event(e) for e in events[-n:]]


__all__ = ["format_event", "print_report", "tail"]
