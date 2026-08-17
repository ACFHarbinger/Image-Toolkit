"""RSS trajectory query (A5).

Scans a session's events for RSS-bearing caller fields (rss_mb / rss / rss_bytes)
and returns the (t, rss_mb) trajectory in time order. Used to chart memory
growth across an Investigation.
"""

from __future__ import annotations

from typing import List, Tuple

from debugtool import Session


def rss_trajectory(session: Session) -> List[Tuple[float, float]]:
    """Return [(t, rss_mb)] for every event carrying an RSS field."""
    out: List[Tuple[float, float]] = []
    for e in session.events:
        value = None
        for key in ("rss_mb", "rss", "rss_bytes"):
            if key in e:
                value = e[key]
                break
        if value is None:
            continue
        try:
            mb = float(value)
        except (TypeError, ValueError):
            continue
        if key == "rss_bytes":
            mb /= 1024 * 1024
        out.append((float(e.get("t", 0)), mb))
    return out


def rss_peak(session: Session) -> float:
    traj = rss_trajectory(session)
    return max((mb for _, mb in traj), default=0.0)


__all__ = ["rss_trajectory", "rss_peak"]
