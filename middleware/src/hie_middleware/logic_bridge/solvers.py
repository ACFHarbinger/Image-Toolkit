"""Thin adapter over ``base.hie`` (the pybind11 binding for ``logic/src/{exact_solvers,
metaheuristics}.cpp``, wired into Image-Toolkit's central `base` extension —
see ``base/src/bindings.cpp``'s ``register_hie_*`` calls).

``HAVE_NATIVE_HIE`` is False whenever `base` can't be imported (e.g. running
middleware tests without the compiled extension, or on a platform where it
hasn't been built) — callers should fall back to the pure-Python reference
implementations in ``jobs/exact_dp.py`` / ``jobs/metaheuristics.py`` in that
case, which is exactly what those modules do.

`solve_color_harmonization`'s `clamp_beta` sequencing bug (stale `hi` read
before the low-bound correction) is FIXED as of 2026-08-12 — see
`.agent/cache/claude/hie_exact_solver_clamp_bug_20260812.md` for the
original repro and `logic/test/test_solvers.cpp`'s
`test_color_harmonization_clamp_beta_sequencing` for the regression test.
The remaining semantic question — the native path clamps `beta` into the
valid Lab range (a non-clipping guarantee), the naive unclamped transfer
reproduces the target's mean/std moments exactly, and for `alpha` far
enough from 1 the two are mathematically incompatible (clamp is
unsatisfiable on both bounds at once — see the code comment on
`clamp_beta` in `exact_solvers.cpp`) — was resolved as a product decision
(2026-08-12): **both are available, opt-in, defaulting to exact moments**.
`jobs/exact_dp.py`'s `_solve_color_harmonization` takes an
`enforce_bounds` flag; when `True` it either delegates to
`native_solve_color_harmonization` below (if `base.hie` is available) or
replicates the same fixed `clamp_beta` logic in pure Python (so the
behavior is identical whether or not the native extension is present).
Default (`enforce_bounds=False`) preserves the pre-existing exact-moment
contract `middleware/test/test_jobs.py::test_exact_solver_color_harmonization_matches_target_moments`
already asserted.

`solve_seam` has no such mismatch (masked-cell DP is identical on both
sides) and IS bridged below as `native_solve_seam` — available to callers
that want it, but not wired into `jobs/exact_dp.py`'s default dispatch:
`call_hie_exact_solver("seam", ...)`'s tests depend on the pure-Python
reference's per-row `report(JobProgress(...))` calls, which a single
blocking native call can't provide (same reasoning as PSO/DE below).
Color harmonization has no such progress-reporting concern (it was never
incremental — a single closed-form computation), which is why it CAN be
wired into the default dispatch path when `enforce_bounds=True`, unlike
seam/PSO/DE.
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


class LayerColorStatsLike(Protocol):
    mean_l: float
    mean_a: float
    mean_b: float
    std_l: float
    std_a: float
    std_b: float


def native_solve_color_harmonization(source: LayerColorStatsLike, target: LayerColorStatsLike):
    """Call `base.hie.solve_color_harmonization` (clamps `beta` into the valid
    Lab range — a non-clipping guarantee). Raises if `HAVE_NATIVE_HIE` is
    False. See the module docstring for how this relates to
    `jobs/exact_dp.py`'s `enforce_bounds` flag. Returns the native
    `base.hie.ColorHarmonizationResult` directly (same field names —
    `alpha_l`/`beta_l`/.../`success`/`error` — as the Python reference's
    `ColorHarmonizationResult` dataclass).
    """
    if not HAVE_NATIVE_HIE:
        raise RuntimeError("native HIE bindings are not available (base.hie not found)")
    native_source = base.hie.LayerColorStats(
        source.mean_l, source.mean_a, source.mean_b, source.std_l, source.std_a, source.std_b
    )
    native_target = base.hie.LayerColorStats(
        target.mean_l, target.mean_a, target.mean_b, target.std_l, target.std_a, target.std_b
    )
    return base.hie.solve_color_harmonization(native_source, native_target)


class CorrespondenceLike(Protocol):
    src_x: float
    src_y: float
    dst_x: float
    dst_y: float


def native_solve_alignment_gnc(
    correspondences: Sequence[CorrespondenceLike],
    gnc_iterations: int = 8,
    inlier_threshold: float = 3.0,
):
    """Call `base.hie.solve_alignment_gnc`. Raises if `HAVE_NATIVE_HIE` is False.

    Unlike `solve_seam`/PSO/DE, there is no pure-Python reference to fall
    back to — `jobs/exact_dp.py` deliberately never stubbed GNC-TLS
    alignment, since a meaningful implementation needs a real
    feature-correspondence pipeline, not something worth maintaining in
    parallel with the C++ version. This is the only way to run it.
    Returns the native `base.hie.AlignmentResult` directly (`model.tx/ty/scale`,
    `residual`, `inlier_count`, `success`, `error`).
    """
    if not HAVE_NATIVE_HIE:
        raise RuntimeError("native HIE bindings are not available (base.hie not found)")
    native_correspondences = [
        base.hie.Correspondence(c.src_x, c.src_y, c.dst_x, c.dst_y) for c in correspondences
    ]
    return base.hie.solve_alignment_gnc(native_correspondences, gnc_iterations, inlier_threshold)


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
