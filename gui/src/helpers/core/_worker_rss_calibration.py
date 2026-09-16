"""Rolling self-calibration of parallel-extraction child peak RSS (#484).

#483 shipped a static `PER_WORKER_RAM_MIB = 4096` estimate (validated
once against ~4 GiB real workers) that the resource simulator and the
settings spinbox cap use to decide how many pool children fit in RAM.
This module replaces the constant with a measurement: every parallel
run stamps each child's true peak RSS into its result dict (see
:func:`run_extraction_in_process`), the parent feeds the run's max
here, and consumers read :func:`effective_per_worker_mib`.

Semantics, deliberately conservative (the whole point of #483/#485 is
never green-lighting an OOM configuration):

- Rolling window: the last ``WINDOW`` run peaks are kept; old peaks
  age out, so the estimate tracks the current workload instead of one
  heavy run from months ago.
- Upward-only vs the validated floor: the effective value is
  ``max(STATIC_FLOOR_MIB, observed max)``. A small test clip measuring
  200 MiB must not talk the simulator into allowing more workers than
  the validated 4 GiB floor — downward adaptation needs its own safety
  analysis and is explicitly out of scope.
- Lock-guarded: records happen on pool threads, reads on the GUI
  thread. Pure stdlib, no Qt, no psutil — importable from any layer.
"""

from __future__ import annotations

import threading
from collections import deque
from typing import Deque, List, Optional

# Validated once against real extraction workers (#483). Never estimate
# below this no matter how small the observed runs are.
STATIC_FLOOR_MIB = 4096

# Run peaks kept; older measurements age out of the rolling max.
WINDOW = 20

_lock = threading.Lock()
_history: Deque[float] = deque(maxlen=WINDOW)


def record_run_peak_mb(peak_mb: float, workers: int) -> None:
    """Record one parallel run's max child peak RSS.

    ``workers`` is accepted for future per-count normalization and
    validated (a nonsensical count means the measurement is suspect);
    the stored value is the per-child peak as observed.
    """
    if not (peak_mb > 0) or not (workers >= 1):
        return
    with _lock:
        _history.append(float(peak_mb))


def run_peak_samples() -> List[float]:
    """Copy of the current rolling window (introspection/tests)."""
    with _lock:
        return list(_history)


def effective_per_worker_mib() -> int:
    """Per-worker MiB estimate consumers should use.

    Rolling max of observed run peaks, floored at the validated static
    constant; the static value itself when nothing has been observed yet.
    """
    with _lock:
        observed = max(_history) if _history else 0.0
    return int(max(STATIC_FLOOR_MIB, observed) + 0.999)


def record_completed_run(results: object, workers: int) -> None:
    """Feed a naturally-completed parallel run's max child peak in.

    Cancelled/error exits return early in the worker and never reach
    here, so partial data can't calibrate. No-op when no child stamped
    a peak (e.g. every item failed before the wrapper ran).
    """
    peak = run_peak_from_results(results)
    if peak is not None:
        record_run_peak_mb(peak, workers)


def run_peak_from_results(results: object) -> Optional[float]:
    """Max `worker_peak_rss_mb` across a run's result dicts, if any.

    Pure function over the stamped results so the aggregation rule is
    unit-testable without spawning a pool. Ignores non-dict entries,
    missing keys, and non-positive values (a child that failed before
    stamping carries no peak).
    """
    if not isinstance(results, (list, tuple)):
        return None
    peaks = [
        res["worker_peak_rss_mb"]
        for res in results
        if isinstance(res, dict)
        and isinstance(res.get("worker_peak_rss_mb"), (int, float))
        and res["worker_peak_rss_mb"] > 0
    ]
    return max(peaks) if peaks else None


def clear() -> None:
    """Empty the window (tests)."""
    with _lock:
        _history.clear()


__all__ = [
    "STATIC_FLOOR_MIB",
    "WINDOW",
    "clear",
    "effective_per_worker_mib",
    "record_completed_run",
    "record_run_peak_mb",
    "run_peak_from_results",
    "run_peak_samples",
]
