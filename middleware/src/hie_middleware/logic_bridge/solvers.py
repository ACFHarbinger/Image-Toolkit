"""Thin adapter over ``base.hie`` (the pybind11 binding for ``logic/src/{exact_solvers,
metaheuristics}.cpp``, wired into Image-Toolkit's central `base` extension —
see ``base/src/bindings.cpp``'s ``register_hie_*`` calls).

``HAVE_NATIVE_HIE`` is False whenever `base` can't be imported (e.g. running
middleware tests without the compiled extension, or on a platform where it
hasn't been built) — callers should fall back to the pure-Python reference
implementations in ``jobs/exact_dp.py`` / ``jobs/metaheuristics.py`` in that
case, which is exactly what those modules do.

`solve_color_harmonization` is still NOT bridged: its `clamp_beta`
sequencing bug (stale `hi` read before the low-bound correction) is FIXED
as of 2026-08-12 — see `.agent/cache/claude/hie_exact_solver_clamp_bug_20260812.md`
for the original repro and `logic/test/test_solvers.cpp`'s
`test_color_harmonization_clamp_beta_sequencing` for the regression test —
but a genuine semantic mismatch remains: the native `solve_color_harmonization`
clamps `beta` into the valid Lab range (and, for `alpha` far enough from 1,
that clamp is unsatisfiable on both bounds at once — see the code comment on
`clamp_beta` in `exact_solvers.cpp`), while `jobs/exact_dp.py`'s
`_solve_color_harmonization` Python reference does not clamp at all and
`middleware/test/test_jobs.py::test_exact_solver_color_harmonization_matches_target_moments`
asserts that exact (unclamped) moment-matching as the reference's contract.
Swapping the dispatch to native as-is would silently change
`call_hie_exact_solver("color_harmonization", ...)`'s output distribution
for any caller whose stats produce an out-of-range alpha/beta, which is a
product decision (should the reference also clamp for parity, breaking that
test's documented contract, or should clamping stay native-only/opt-in?)
worth its own pass, not a side effect of bridging.

`solve_seam` has no such mismatch (masked-cell DP is identical on both
sides) and IS bridged below as `native_solve_seam` — available to callers
that want it, but not wired into `jobs/exact_dp.py`'s default dispatch:
`call_hie_exact_solver("seam", ...)`'s tests depend on the pure-Python
reference's per-row `report(JobProgress(...))` calls, which a single
blocking native call can't provide (same reasoning as PSO/DE below).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Protocol

try:
    import base

    HAVE_NATIVE_HIE = hasattr(base, "hie")
except ImportError:
    base = None  # type: ignore[assignment]
    HAVE_NATIVE_HIE = False

Bounds = Sequence[tuple[float, float]]
ObjectiveFn = Callable[[list[float]], float]


class SeamPixelLike(Protocol):
    energy: float
    masked: bool


def native_solve_seam(energy_grid: Sequence[Sequence[SeamPixelLike]]):
    """Call `base.hie.solve_seam`. Raises if `HAVE_NATIVE_HIE` is False — check first.

    `energy_grid` is row-major (`energy_grid[row][col]`), matching
    `jobs/exact_dp.py`'s `SeamPixel`/`_solve_seam` convention — flattened
    here since the native signature takes a flat vector plus explicit
    `rows`/`cols`. Returns the native `base.hie.SeamResult` directly (same
    field names — `seam_x`, `total_energy`, `success`, `error` — as the
    Python reference's `SeamResult` dataclass, so callers can use either
    interchangeably without an adapter).
    """
    if not HAVE_NATIVE_HIE:
        raise RuntimeError("native HIE bindings are not available (base.hie not found)")
    rows = len(energy_grid)
    cols = len(energy_grid[0]) if rows else 0
    flat = [base.hie.SeamPixel(px.energy, px.masked) for row in energy_grid for px in row]
    return base.hie.solve_seam(flat, rows, cols)


def native_pso_solve(
    objective_fn: ObjectiveFn,
    bounds: Bounds,
    n_particles: int,
    max_iter: int,
) -> list[float]:
    """Call `base.hie.pso_solve`. Raises if `HAVE_NATIVE_HIE` is False — check first."""
    if not HAVE_NATIVE_HIE:
        raise RuntimeError("native HIE bindings are not available (base.hie not found)")
    native_bounds = [base.hie.ParamBound(lo, hi) for lo, hi in bounds]
    config = base.hie.PSOConfig()
    config.n_particles = n_particles
    config.max_iter = max_iter
    result = base.hie.pso_solve(objective_fn, native_bounds, config)
    return list(result.best_params)


def native_de_solve(
    objective_fn: ObjectiveFn,
    bounds: Bounds,
    population_size: int,
    max_iter: int,
) -> list[float]:
    """Call `base.hie.de_solve`. Raises if `HAVE_NATIVE_HIE` is False — check first."""
    if not HAVE_NATIVE_HIE:
        raise RuntimeError("native HIE bindings are not available (base.hie not found)")
    native_bounds = [base.hie.ParamBound(lo, hi) for lo, hi in bounds]
    config = base.hie.DEConfig()
    config.popsize = population_size
    config.max_iter = max_iter
    result = base.hie.de_solve(objective_fn, native_bounds, config)
    return list(result.best_params)
