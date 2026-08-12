"""Reproducibility guarantees for the seeded metaheuristic jobs.

Called out as remaining Track 02 work in AGENT_BUS.md / the tracking issues
alongside benchmarks. Distinct from test_jobs.py's convergence-quality
checks ("does it find something close to the known optimum"): these verify
the stronger, narrower property that a given seed always produces the exact
same trajectory — required for reproducible cache keys / undo-redo replay
per the document model's determinism goals (see
hie_phase1_implementation_20260812.md's "reproducible cache keys").
"""

from hie_middleware.jobs import call_hie_de, call_hie_pso


def _quadratic(p: list[float]) -> float:
    x, y = p
    return (x - 3.0) ** 2 + (y + 2.0) ** 2


def test_pso_same_seed_is_bit_identical_across_runs():
    bounds = [(-10.0, 10.0), (-10.0, 10.0)]
    results = [
        call_hie_pso({}, _quadratic, bounds, n_particles=12, max_iter=15, seed=42).result(timeout=5)
        for _ in range(3)
    ]
    assert all(r.ok for r in results)
    first = results[0].value
    for other in results[1:]:
        assert other.value == first  # exact equality, not approx — same seed must replay identically


def test_pso_different_seeds_are_free_to_diverge():
    bounds = [(-10.0, 10.0), (-10.0, 10.0)]
    a = call_hie_pso({}, _quadratic, bounds, n_particles=12, max_iter=15, seed=1).result(timeout=5).value
    b = call_hie_pso({}, _quadratic, bounds, n_particles=12, max_iter=15, seed=2).result(timeout=5).value
    # Not a strict requirement that they differ (a coincidence is possible for
    # a trivial objective), but for this bounded random walk it's true in
    # practice and catches a seed parameter being silently ignored.
    assert a != b


def test_de_same_seed_is_bit_identical_across_runs():
    bounds = [(-10.0, 10.0), (-10.0, 10.0)]
    results = [
        call_hie_de({}, _quadratic, bounds, population_size=12, max_iter=15, seed=7).result(timeout=5)
        for _ in range(3)
    ]
    assert all(r.ok for r in results)
    first = results[0].value
    for other in results[1:]:
        assert other.value == first


def test_de_different_seeds_are_free_to_diverge():
    bounds = [(-10.0, 10.0), (-10.0, 10.0)]
    a = call_hie_de({}, _quadratic, bounds, population_size=12, max_iter=15, seed=1).result(timeout=5).value
    b = call_hie_de({}, _quadratic, bounds, population_size=12, max_iter=15, seed=2).result(timeout=5).value
    assert a != b
