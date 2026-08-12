#!/usr/bin/env python3
"""Timing + convergence report for the metaheuristic jobs (Track 02).

Deliberately dependency-free (no pytest-benchmark) — this is a report script
run on demand, not part of the pytest suite (see test_reproducibility.py for
the correctness properties that *are* asserted in CI).

Compares the pure-Python reference implementation against the native
`base.hie` binding when available (see `logic_bridge/solvers.py`), on a
handful of standard optimization test functions of increasing dimension.

Usage:
    cd middleware && python3 scripts/benchmark_jobs.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from hie_middleware.jobs import call_hie_de, call_hie_pso  # noqa: E402
from hie_middleware.logic_bridge.solvers import (  # noqa: E402
    HAVE_NATIVE_HIE,
    native_de_solve,
    native_pso_solve,
)


def sphere(p: list[float]) -> float:
    """Convex, separable — the easy case."""
    return sum(x * x for x in p)


def rosenbrock(p: list[float]) -> float:
    """Non-convex, narrow curved valley — the hard case for PSO/DE alike."""
    return sum(100.0 * (p[i + 1] - p[i] ** 2) ** 2 + (1 - p[i]) ** 2 for i in range(len(p) - 1))


PROBLEMS = [
    ("sphere-2d", sphere, [(-5.0, 5.0)] * 2, [0.0, 0.0]),
    ("sphere-6d", sphere, [(-5.0, 5.0)] * 6, [0.0] * 6),
    ("rosenbrock-2d", rosenbrock, [(-5.0, 5.0)] * 2, [1.0, 1.0]),
]


def rms_error(found: list[float], expected: list[float]) -> float:
    return (sum((f - e) ** 2 for f, e in zip(found, expected, strict=True)) / len(expected)) ** 0.5


def bench_reference_pso(objective, bounds, n_particles=30, max_iter=80, seed=0):
    start = time.perf_counter()
    result = call_hie_pso({}, objective, bounds, n_particles, max_iter, seed=seed).result(timeout=30)
    return result.value, time.perf_counter() - start


def bench_reference_de(objective, bounds, population_size=30, max_iter=120, seed=0):
    start = time.perf_counter()
    result = call_hie_de({}, objective, bounds, population_size, max_iter, seed=seed).result(timeout=30)
    return result.value, time.perf_counter() - start


def bench_native_pso(objective, bounds, n_particles=30, max_iter=80):
    start = time.perf_counter()
    best = native_pso_solve(objective, bounds, n_particles, max_iter)
    return best, time.perf_counter() - start


def bench_native_de(objective, bounds, population_size=30, max_iter=120):
    start = time.perf_counter()
    best = native_de_solve(objective, bounds, population_size, max_iter)
    return best, time.perf_counter() - start


def main() -> None:
    print(f"native base.hie available: {HAVE_NATIVE_HIE}\n")
    header = f"{'problem':<16}{'solver':<12}{'backend':<10}{'time (s)':<12}{'rms error':<12}"
    print(header)
    print("-" * len(header))

    for name, objective, bounds, expected in PROBLEMS:
        best, elapsed = bench_reference_pso(objective, bounds)
        print(f"{name:<16}{'pso':<12}{'reference':<10}{elapsed:<12.4f}{rms_error(best, expected):<12.4f}")

        best, elapsed = bench_reference_de(objective, bounds)
        print(f"{name:<16}{'de':<12}{'reference':<10}{elapsed:<12.4f}{rms_error(best, expected):<12.4f}")

        if HAVE_NATIVE_HIE:
            best, elapsed = bench_native_pso(objective, bounds)
            print(f"{name:<16}{'pso':<12}{'native':<10}{elapsed:<12.4f}{rms_error(best, expected):<12.4f}")

            best, elapsed = bench_native_de(objective, bounds)
            print(f"{name:<16}{'de':<12}{'native':<10}{elapsed:<12.4f}{rms_error(best, expected):<12.4f}")


if __name__ == "__main__":
    main()
