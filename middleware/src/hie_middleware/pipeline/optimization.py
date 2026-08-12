"""Explicit native/reference optimization selection for the HIE pipeline."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from ..jobs import JobHandle, JobProgress, call_hie_de, call_hie_pso, submit_job
from ..logic_bridge.solvers import HAVE_NATIVE_HIE, native_de_solve, native_pso_solve

Bounds = Sequence[tuple[float, float]]
ObjectiveFn = Callable[[list[float]], float]


class OptimizationUnavailable(RuntimeError):
    """Raised when an explicitly requested optimization backend is unavailable."""


class OptimizationPipeline:
    """Dispatch PSO/DE while preserving the shared cancellable job contract.

    The reference backend is the default because it reports per-iteration
    progress and remains available in middleware-only installations. Native
    execution is explicit and is intended for production workloads once the
    central `base.hie` extension is built.
    """

    @staticmethod
    def capabilities() -> dict[str, bool]:
        return {"reference": True, "native": HAVE_NATIVE_HIE}

    def pso(
        self,
        objective_fn: ObjectiveFn,
        bounds: Bounds,
        *,
        backend: str = "reference",
        params: dict[str, float] | None = None,
        n_particles: int = 24,
        max_iter: int = 40,
        seed: int | None = None,
    ) -> JobHandle[list[float]]:
        if backend == "reference":
            return call_hie_pso(params or {}, objective_fn, bounds, n_particles, max_iter, seed=seed)
        if backend == "native":
            self._require_native()
            return submit_job(
                lambda _token, report: self._native_body(
                    native_pso_solve, objective_fn, bounds, n_particles, max_iter, report
                )
            )
        raise ValueError(f"unknown optimization backend: {backend!r}")

    def differential_evolution(
        self,
        objective_fn: ObjectiveFn,
        bounds: Bounds,
        *,
        backend: str = "reference",
        params: dict[str, float] | None = None,
        population_size: int = 24,
        max_iter: int = 60,
        seed: int | None = None,
    ) -> JobHandle[list[float]]:
        if backend == "reference":
            return call_hie_de(
                params or {}, objective_fn, bounds, population_size, max_iter, seed=seed
            )
        if backend == "native":
            self._require_native()
            return submit_job(
                lambda _token, report: self._native_body(
                    native_de_solve, objective_fn, bounds, population_size, max_iter, report
                )
            )
        raise ValueError(f"unknown optimization backend: {backend!r}")

    @staticmethod
    def _native_body(solver, objective_fn, bounds, population_size, max_iter, report):
        result = solver(objective_fn, bounds, population_size, max_iter)
        report(JobProgress(1.0, "native optimization complete"))
        return result

    @staticmethod
    def _require_native() -> None:
        if not HAVE_NATIVE_HIE:
            raise OptimizationUnavailable(
                "native optimization requires Image-Toolkit's compiled base.hie extension"
            )
