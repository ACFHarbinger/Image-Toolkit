"""Thin adapter over ``base.hie`` (the pybind11 binding for ``logic/src/{exact_solvers,
metaheuristics}.cpp``, wired into Image-Toolkit's central `base` extension —
see ``base/src/bindings.cpp``'s ``register_hie_*`` calls).

``HAVE_NATIVE_HIE`` is False whenever `base` can't be imported (e.g. running
middleware tests without the compiled extension, or on a platform where it
hasn't been built) — callers should fall back to the pure-Python reference
implementations in ``jobs/exact_dp.py`` / ``jobs/metaheuristics.py`` in that
case, which is exactly what those modules do.

Only PSO/DE are wired through here. `solve_seam`/`solve_color_harmonization`
are intentionally NOT bridged yet: `solve_color_harmonization`'s C++
implementation has a confirmed bug in its non-clipping `clamp_beta` step (it
computes `hi` once and then applies both the lower- and upper-bound
correction sequentially without recomputing `hi` after the first
adjustment, double-correcting `beta` whenever both bounds are violated —
see `.agent/cache/claude/hie_exact_solver_clamp_bug_20260812.md` for the
full repro). Bridging it now would silently regress `call_hie_exact_solver`
from a correct Python reference to a buggy native one.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

try:
    import base

    HAVE_NATIVE_HIE = hasattr(base, "hie")
except ImportError:
    base = None  # type: ignore[assignment]
    HAVE_NATIVE_HIE = False

Bounds = Sequence[tuple[float, float]]
ObjectiveFn = Callable[[list[float]], float]


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
