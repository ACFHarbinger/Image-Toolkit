"""Measured-peak calibration for #758 VRAM estimates.

The parametric formula in ``gpu_vram_estimate`` is the prior. After each
in-process job releases, its torch peak is compared to the estimate that
admitted it. The per-owner scale is ``max(1.0, measured / formula)`` —
upward-only, so a small smoke run cannot talk conservative admission into
allowing a heavier job. Seeded from one representative run per job type
on an RTX 4080 Laptop (2026-10-16). Comfy HTTP owners are not calibrated
here: their occupancy is another process.
"""
from __future__ import annotations

import math
import threading

# Measured/formula from one RTX 4080 Laptop run per in-process job type
# (2026-10-16). Owners whose peak was below the formula keep 1.0.
SEED_SCALE: dict[str, float] = {
    "upscale": 1.43,
    "gan-train": 2.24,
}

_lock = threading.Lock()
_live_scale: dict[str, float] = {}


def _finite_positive(value: float) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number <= 0:
        return None
    return number


def record_peak(owner: str, measured_gb: float, formula_gb: float) -> None:
    """Record one in-process peak. Raises the owner scale, never lowers it."""
    peak = _finite_positive(measured_gb)
    formula = _finite_positive(formula_gb)
    if not owner or peak is None or formula is None:
        return
    scale = peak / formula
    if not math.isfinite(scale) or scale <= 1.0:
        return
    with _lock:
        previous = _live_scale.get(owner, 0.0)
        if scale > previous:
            _live_scale[owner] = scale


def owner_scale(owner: str) -> float:
    """Scale applied to the parametric estimate. Always >= 1.0."""
    with _lock:
        live = _live_scale.get(owner, 0.0)
    seed = SEED_SCALE.get(owner, 1.0)
    return max(1.0, seed, live)


def apply_scale(owner: str, formula_gb: float) -> float:
    formula = _finite_positive(formula_gb)
    if formula is None:
        return 0.1
    return round(formula * owner_scale(owner), 2)


def live_scales() -> dict[str, float]:
    with _lock:
        return dict(_live_scale)


def clear() -> None:
    """Empty live peaks (tests). Seeds stay."""
    with _lock:
        _live_scale.clear()


__all__ = [
    "SEED_SCALE",
    "apply_scale",
    "clear",
    "live_scales",
    "owner_scale",
    "record_peak",
]
