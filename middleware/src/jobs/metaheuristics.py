"""Swarm/evolutionary optimization jobs (PSO and Differential Evolution).

`call_hie_pso` mirrors the ``pso_tune(params, objective_fn, bounds, n_particles,
max_iter)`` signature agreed in ``.agent/cache/AGENT_BUS.md``'s Gemini -> Chat
note. Until ``logic/src/metaheuristics.cpp``'s ``pso_tune`` is exposed through
Image-Toolkit's central ``base`` pybind11 module (see
``hie_claude_handoff_20260812.md``'s open question), this ships a real,
self-contained Python reference implementation rather than a bare stub — it's
correct and testable today, and the C++ path can replace this function body
without changing the job contract once the binding lands.
"""

from __future__ import annotations

import random
from collections.abc import Callable, Sequence

from .base import CancelToken, JobHandle, JobProgress, ReportFn, submit_job

Bounds = Sequence[tuple[float, float]]
ObjectiveFn = Callable[[list[float]], float]


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _pso_body(
    objective_fn: ObjectiveFn,
    bounds: Bounds,
    n_particles: int,
    max_iter: int,
    *,
    inertia: float = 0.6,
    cognitive: float = 1.5,
    social: float = 1.5,
    seed: int | None = None,
) -> Callable[[CancelToken, ReportFn], list[float]]:
    rng = random.Random(seed)
    dim = len(bounds)

    def body(token: CancelToken, report: ReportFn) -> list[float]:
        positions = [[rng.uniform(lo, hi) for lo, hi in bounds] for _ in range(n_particles)]
        velocities = [[0.0] * dim for _ in range(n_particles)]
        personal_best = [list(p) for p in positions]
        personal_best_score = [objective_fn(p) for p in positions]

        best_idx = min(range(n_particles), key=lambda i: personal_best_score[i])
        global_best = list(personal_best[best_idx])
        global_best_score = personal_best_score[best_idx]

        for iteration in range(max_iter):
            token.raise_if_cancelled()
            for i in range(n_particles):
                for d in range(dim):
                    r1, r2 = rng.random(), rng.random()
                    velocities[i][d] = (
                        inertia * velocities[i][d]
                        + cognitive * r1 * (personal_best[i][d] - positions[i][d])
                        + social * r2 * (global_best[d] - positions[i][d])
                    )
                    lo, hi = bounds[d]
                    positions[i][d] = _clamp(positions[i][d] + velocities[i][d], lo, hi)

                score = objective_fn(positions[i])
                if score < personal_best_score[i]:
                    personal_best[i] = list(positions[i])
                    personal_best_score[i] = score
                    if score < global_best_score:
                        global_best = list(positions[i])
                        global_best_score = score

            report(
                JobProgress(
                    fraction=(iteration + 1) / max_iter,
                    message=f"iteration {iteration + 1}/{max_iter}",
                    payload={"best_score": global_best_score, "best_params": list(global_best)},
                )
            )

        return global_best

    return body


def call_hie_pso(
    params: dict[str, float],
    objective_fn: ObjectiveFn,
    bounds: Bounds,
    n_particles: int = 24,
    max_iter: int = 40,
    *,
    seed: int | None = None,
) -> JobHandle[list[float]]:
    """Autotune a multi-parameter filter stack via Particle Swarm Optimization.

    `params` is accepted for API-shape parity with the eventual C++ binding
    (initial-guess / warm-start hint) but the reference implementation below
    seeds particles uniformly across `bounds` rather than around it — swap
    this for a warm-started init once real filter-stack objectives exist.

    Returns a `JobHandle` immediately; the swarm runs on a background thread.
    """
    del params  # reserved for warm-start parity with the C++ signature; unused by the reference impl
    body = _pso_body(objective_fn, bounds, n_particles, max_iter, seed=seed)
    return submit_job(body)


def _de_body(
    objective_fn: ObjectiveFn,
    bounds: Bounds,
    population_size: int,
    max_iter: int,
    *,
    differential_weight: float = 0.8,
    crossover_rate: float = 0.9,
    seed: int | None = None,
) -> Callable[[CancelToken, ReportFn], list[float]]:
    """Return a deterministic, bounded ``DE/rand/1/bin`` job body."""
    rng = random.Random(seed)
    dim = len(bounds)

    def body(token: CancelToken, report: ReportFn) -> list[float]:
        population = [[rng.uniform(lo, hi) for lo, hi in bounds] for _ in range(population_size)]
        scores = [objective_fn(candidate) for candidate in population]

        for generation in range(max_iter):
            token.raise_if_cancelled()
            for index, target in enumerate(population):
                choices = [i for i in range(population_size) if i != index]
                a, b, c = rng.sample(choices, 3)
                mutant = [
                    population[a][dimension]
                    + differential_weight * (population[b][dimension] - population[c][dimension])
                    for dimension in range(dim)
                ]
                forced = rng.randrange(dim)
                trial = [
                    _clamp(mutant[dimension], *bounds[dimension])
                    if dimension == forced or rng.random() < crossover_rate
                    else target[dimension]
                    for dimension in range(dim)
                ]
                trial_score = objective_fn(trial)
                if trial_score <= scores[index]:
                    population[index] = trial
                    scores[index] = trial_score

            best_index = min(range(population_size), key=scores.__getitem__)
            report(JobProgress(
                fraction=(generation + 1) / max_iter,
                message=f"generation {generation + 1}/{max_iter}",
                payload={"best_score": scores[best_index], "best_params": list(population[best_index])},
            ))

        return list(population[min(range(population_size), key=scores.__getitem__)])

    return body


def call_hie_de(
    params: dict[str, float],
    objective_fn: ObjectiveFn,
    bounds: Bounds,
    population_size: int = 24,
    max_iter: int = 60,
    *,
    differential_weight: float = 0.8,
    crossover_rate: float = 0.9,
    seed: int | None = None,
) -> JobHandle[list[float]]:
    """Optimize composition/layout parameters with Differential Evolution."""
    del params  # reserved for parity with the eventual central binding
    if len(bounds) == 0:
        raise ValueError("call_hie_de requires at least one parameter bound")
    if population_size < 4:
        raise ValueError("call_hie_de requires a population of at least four candidates")
    if max_iter < 1:
        raise ValueError("call_hie_de requires at least one generation")
    body = _de_body(
        objective_fn,
        bounds,
        population_size,
        max_iter,
        differential_weight=differential_weight,
        crossover_rate=crossover_rate,
        seed=seed,
    )
    return submit_job(body)
