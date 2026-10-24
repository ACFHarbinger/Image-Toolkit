"""Header badge for the cloud.jobs shell (#847).

The count is jobs in the active lifecycle states. Reserved spend is the
amount still held on jobs that have not reached a terminal state. This
module does not open ``cloud_jobs.db``; the sealed store reader arrives
with the daemon lease.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from middleware.src.cloud.state import ACTIVE, TERMINAL

_ACTIVE = {state.value for state in ACTIVE}
_TERMINAL = {state.value for state in TERMINAL}


def header_badge(rows: Iterable[tuple[str, float]]) -> tuple[int, float]:
    """Project ``(state, reserved_usd)`` rows into the header pair."""
    running = 0
    reserved = 0.0
    for state, amount in rows:
        if state in _ACTIVE:
            running += 1
        if state not in _TERMINAL:
            reserved += max(0.0, float(amount))
    return running, reserved


def summary_result(rows: Iterable[tuple[str, float]] | None) -> dict[str, Any]:
    """Bridge payload. ``rows is None`` means no projection is attached."""
    if rows is None:
        return {"running": 0, "reserved_usd": 0.0, "available": False}
    running, reserved = header_badge(rows)
    return {"running": running, "reserved_usd": reserved, "available": True}
