"""App lifecycle RSS instrumentation (roadmap development_tool.md
§12.5, issue #70).

A tiny, dependency-light phase-tagged memory logger for `app.py`'s startup
sequence -- mirrors the pattern already established for the ASP pipeline's
per-stage instrumentation (`_log_resource()` in
`backend/benchmark/bench_anime_stitch.py`), but for the GUI app's own
lifecycle rather than a single pipeline run: JVM start, Qt init, first
window shown, gallery load.

Each call to `snapshot(phase)` records the process RSS and prints a single
line; if the delta from the *previous* snapshot exceeds
`LIFECYCLE_RSS_ALERT_MB` (default 200, matching this item's own spec), it's
flagged with a warning marker so a phase that regresses RSS is visible in
plain console output without needing to diff two JSON files by hand.
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional

import psutil

from backend.src.core import telemetry
from backend.src.constants.core import LIFECYCLE_RSS_ALERT_MB, _HISTORY

# The roadmap item names this threshold explicitly ("Alert when any phase
# increases RSS by >200 MB relative to the previous measurement"). Kept
# overridable via env var for local tuning without a code change.

# Module-level history for the current process — one process launches one
# app instance, so a process-global list (not a class the caller has to
# thread through app.py's closures) is the simplest fit here.


def snapshot(phase: str) -> Dict:
    """Record RSS at *phase*, print it, and warn if it grew >LIFECYCLE_RSS_ALERT_MB
    since the previous phase. Returns the snapshot dict (also appended to
    the process-lifetime `_HISTORY`, retrievable via `history()`)."""
    rss_mb = round(psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024), 1)
    prev_rss = _HISTORY[-1]["rss_mb"] if _HISTORY else None
    delta_mb = None if prev_rss is None else round(rss_mb - prev_rss, 1)

    entry = {"phase": phase, "rss_mb": rss_mb, "delta_mb": delta_mb}
    _HISTORY.append(entry)
    telemetry.emit("startup", "lifecycle.snapshot", phase=phase, rss_mb=rss_mb, delta_mb=delta_mb)

    if delta_mb is None:
        print(f"[Lifecycle/{phase}] RSS={rss_mb}MB (baseline)")
    else:
        marker = " ⚠️ ALERT" if delta_mb > LIFECYCLE_RSS_ALERT_MB else ""
        print(f"[Lifecycle/{phase}] RSS={rss_mb}MB (Δ{delta_mb:+.1f}MB){marker}")
        if delta_mb > LIFECYCLE_RSS_ALERT_MB:
            print(
                f"    ⚠️  Phase '{phase}' grew RSS by {delta_mb:.1f}MB, over the "
                f"{LIFECYCLE_RSS_ALERT_MB:.0f}MB alert threshold (LIFECYCLE_RSS_ALERT_MB)."
            )
    return entry


def history() -> List[Dict]:
    """The full phase/RSS/delta history recorded this process, in order."""
    return list(_HISTORY)


def alerts() -> List[Dict]:
    """Subset of `history()` whose delta exceeded the alert threshold."""
    return [e for e in _HISTORY if e["delta_mb"] is not None and e["delta_mb"] > LIFECYCLE_RSS_ALERT_MB]


def reset() -> None:
    """Clear history — for tests, and for any long-lived host process that
    wants to start a fresh lifecycle window (not used by app.py itself,
    which snapshots once per process)."""
    _HISTORY.clear()


def find(phase: str) -> Optional[Dict]:
    for e in _HISTORY:
        if e["phase"] == phase:
            return e
    return None
