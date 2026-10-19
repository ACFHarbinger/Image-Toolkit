import threading
import time

import pytest

from jobs import (
    Correspondence,
    JobStatus,
    LayerColorStats,
    SeamPixel,
    call_hie_alignment_gnc,
    call_hie_exact_solver,
    call_hie_de,
    call_hie_pso,
    submit_job,
)
from jobs.base import JobCancelled, JobProgress
from logic_bridge.solvers import HAVE_NATIVE_HIE


# ─── Job contract (base.py) ────────────────────────────────────────────────


def test_job_succeeds_and_reports_progress():
    def body(token, report):
        for i in range(3):
            token.raise_if_cancelled()
            report(JobProgress((i + 1) / 3))
        return "done"

    handle = submit_job(body)
    result = handle.result(timeout=5)

    assert result.ok
    assert result.status is JobStatus.SUCCEEDED
    assert result.value == "done"
    progress = handle.drain_progress()
    assert [round(p.fraction, 4) for p in progress] == [round(1 / 3, 4), round(2 / 3, 4), 1.0]


def test_job_captures_exceptions_as_failed_result_without_raising():
    def body(_token, _report):
        raise RuntimeError("boom")

    handle = submit_job(body)
    result = handle.result(timeout=5)

    assert not result.ok
    assert result.status is JobStatus.FAILED
    assert result.error == "boom"


def test_job_cancellation_is_cooperative():
    started = threading.Event()

    def body(token, _report):
        started.set()
        while not token.cancelled:
            time.sleep(0.01)
        token.raise_if_cancelled()
        return "unreachable"

    handle = submit_job(body)
    assert started.wait(timeout=2)
    handle.cancel()
    result = handle.result(timeout=5)

    assert result.status is JobStatus.CANCELLED
    assert result.value is None


def test_job_body_raising_jobcancelled_directly_is_treated_as_cancelled():
    def body(_token, _report):
        raise JobCancelled()

    result = submit_job(body).result(timeout=5)
    assert result.status is JobStatus.CANCELLED


# ─── call_hie_pso (metaheuristics.py) ──────────────────────────────────────


def test_pso_minimizes_simple_quadratic_bowl():
    # f(x, y) = (x - 3)^2 + (y + 2)^2, global minimum at (3, -2), f=0.
    def objective(p):
        x, y = p
        return (x - 3.0) ** 2 + (y + 2.0) ** 2

    handle = call_hie_pso(
        params={},
        objective_fn=objective,
        bounds=[(-10.0, 10.0), (-10.0, 10.0)],
        n_particles=20,
        max_iter=60,
        seed=1234,
    )
    result = handle.result(timeout=10)

    assert result.ok
    best_x, best_y = result.value
    assert best_x == pytest.approx(3.0, abs=0.5)
    assert best_y == pytest.approx(-2.0, abs=0.5)


def test_pso_progress_reports_monotonic_iteration_count():
    handle = call_hie_pso(
        params={},
        objective_fn=lambda p: p[0] ** 2,
        bounds=[(-5.0, 5.0)],
        n_particles=8,
        max_iter=5,
        seed=1,
    )
    handle.result(timeout=10)
    progress = handle.drain_progress()

    assert len(progress) == 5
    assert [round(p.fraction, 2) for p in progress] == [0.2, 0.4, 0.6, 0.8, 1.0]


def test_pso_respects_cancellation():
    def slow_objective(p):
        time.sleep(0.05)
        return p[0] ** 2

    handle = call_hie_pso(
        params={},
        objective_fn=slow_objective,
        bounds=[(-5.0, 5.0)],
        n_particles=4,
        max_iter=1000,
        seed=1,
    )
    time.sleep(0.1)
    handle.cancel()
    result = handle.result(timeout=10)

    assert result.status is JobStatus.CANCELLED


def test_de_minimizes_simple_quadratic_bowl():
    def objective(p):
        x, y = p
        return (x - 1.5) ** 2 + (y + 2.5) ** 2

    result = call_hie_de(
        params={}, objective_fn=objective, bounds=[(-5.0, 5.0), (-5.0, 5.0)],
        population_size=20, max_iter=80, seed=123,
    ).result(timeout=10)
    assert result.ok
    assert result.value[0] == pytest.approx(1.5, abs=0.35)
    assert result.value[1] == pytest.approx(-2.5, abs=0.35)


def test_de_reports_generations_and_rejects_small_population():
    handle = call_hie_de(
        params={}, objective_fn=lambda p: p[0] ** 2, bounds=[(-2.0, 2.0)],
        population_size=6, max_iter=4, seed=2,
    )
    handle.result(timeout=10)
    assert len(handle.drain_progress()) == 4
    with pytest.raises(ValueError, match="at least four"):
        call_hie_de(params={}, objective_fn=lambda p: p[0], bounds=[(-1.0, 1.0)], population_size=3)


# ─── call_hie_exact_solver (exact_dp.py) ───────────────────────────────────


def test_exact_solver_seam_avoids_masked_column():
    # 3x3 grid where the middle column is masked at every row; the DP seam
    # must route entirely through columns 0 or 2.
    grid = [
        [SeamPixel(energy=1.0), SeamPixel(energy=0.0, masked=True), SeamPixel(energy=1.0)]
        for _ in range(3)
    ]
    handle = call_hie_exact_solver("seam", energy_grid=grid)
    result = handle.result(timeout=5)
    seam = result.value

    assert result.ok
    assert seam.success
    assert all(c != 1 for c in seam.seam_x)


def test_exact_solver_seam_reports_failure_when_fully_masked():
    grid = [[SeamPixel(energy=0.0, masked=True)] for _ in range(2)]
    handle = call_hie_exact_solver("seam", energy_grid=grid)
    result = handle.result(timeout=5)
    seam = result.value

    assert result.ok
    assert not seam.success
    assert seam.error


def test_exact_solver_color_harmonization_matches_target_moments():
    source = LayerColorStats(mean_l=40.0, mean_a=0.0, mean_b=0.0, std_l=10.0, std_a=5.0, std_b=5.0)
    target = LayerColorStats(mean_l=60.0, mean_a=2.0, mean_b=-2.0, std_l=20.0, std_a=5.0, std_b=10.0)

    handle = call_hie_exact_solver("color_harmonization", source=source, target=target)
    result = handle.result(timeout=5)
    harmonization = result.value

    assert result.ok
    assert harmonization.success
    # Applying (alpha, beta) to the source mean must reproduce the target mean exactly.
    assert harmonization.alpha_l * source.mean_l + harmonization.beta_l == pytest.approx(target.mean_l)
    assert harmonization.alpha_a * source.mean_a + harmonization.beta_a == pytest.approx(target.mean_a)
    assert harmonization.alpha_b * source.mean_b + harmonization.beta_b == pytest.approx(target.mean_b)
    # Scale factor must match the std ratio per channel.
    assert harmonization.alpha_l == pytest.approx(target.std_l / source.std_l)
    assert harmonization.alpha_b == pytest.approx(target.std_b / source.std_b)


def test_exact_solver_color_harmonization_enforce_bounds_clamps_beta():
    # Same repro values as the clamp_beta sequencing bug (cb118ac) and
    # logic/test/test_solvers.cpp::test_color_harmonization_clamp_beta_sequencing —
    # alpha=2 makes the low/high Lab bounds mutually unsatisfiable by a pure
    # shift, so this exercises the "close as a shift can get" clamp path,
    # not just a trivial in-range case.
    source = LayerColorStats(mean_l=40.0, mean_a=1.0, mean_b=2.0, std_l=10.0, std_a=5.0, std_b=5.0)
    target = LayerColorStats(mean_l=60.0, mean_a=3.0, mean_b=-2.0, std_l=20.0, std_a=15.0, std_b=10.0)

    default_handle = call_hie_exact_solver("color_harmonization", source=source, target=target)
    default_result = default_handle.result(timeout=5).value
    assert default_result.beta_l == pytest.approx(-20.0)  # unclamped: 60 - 2*40

    clamped_handle = call_hie_exact_solver(
        "color_harmonization", source=source, target=target, enforce_bounds=True
    )
    clamped_result = clamped_handle.result(timeout=5).value
    assert clamped_result.success
    assert clamped_result.alpha_l == pytest.approx(2.0)
    assert clamped_result.beta_l == pytest.approx(-100.0)
    # High bound is exactly satisfied post-clamp (the low bound is the one
    # that stays violated — see _clamp_beta's docstring).
    assert clamped_result.alpha_l * 100.0 + clamped_result.beta_l == pytest.approx(100.0)


@pytest.mark.skipif(not HAVE_NATIVE_HIE, reason="compiled base.hie extension not available")
def test_exact_solver_color_harmonization_enforce_bounds_matches_native():
    # With base.hie present, enforce_bounds=True routes to
    # native_solve_color_harmonization directly (see call_hie_exact_solver) —
    # this just confirms that path and the pure-Python _clamp_beta mirror
    # (exercised above without native) agree, which they must since both are
    # required to implement the same fixed clamp_beta sequencing.
    source = LayerColorStats(mean_l=40.0, mean_a=1.0, mean_b=2.0, std_l=10.0, std_a=5.0, std_b=5.0)
    target = LayerColorStats(mean_l=60.0, mean_a=3.0, mean_b=-2.0, std_l=20.0, std_a=15.0, std_b=10.0)

    result = call_hie_exact_solver(
        "color_harmonization", source=source, target=target, enforce_bounds=True
    ).result(timeout=5).value
    assert result.success
    assert result.beta_l == pytest.approx(-100.0)
    assert result.alpha_l * 100.0 + result.beta_l == pytest.approx(100.0)


def test_exact_solver_rejects_unknown_method():
    with pytest.raises(ValueError):
        call_hie_exact_solver("not-a-real-method")  # type: ignore[arg-type]


# ─── GNC-TLS alignment (exact_dp.py, native-only) ──────────────────────────


@pytest.mark.skipif(not HAVE_NATIVE_HIE, reason="compiled base.hie extension not available")
def test_alignment_gnc_recovers_pure_translation():
    correspondences = [
        Correspondence(src_x=float(i), src_y=float(i * 2), dst_x=float(i) + 10.0, dst_y=float(i * 2) - 5.0)
        for i in range(20)
    ]
    handle = call_hie_alignment_gnc(correspondences)
    result = handle.result(timeout=5)
    alignment = result.value

    assert result.ok
    assert alignment.success
    assert alignment.model.tx == pytest.approx(10.0, abs=1e-2)
    assert alignment.model.ty == pytest.approx(-5.0, abs=1e-2)
    assert alignment.inlier_count == 20


def test_alignment_gnc_raises_without_native_extension(monkeypatch):
    monkeypatch.setattr("jobs.exact_dp.HAVE_NATIVE_HIE", False)
    with pytest.raises(RuntimeError):
        call_hie_alignment_gnc([Correspondence(0.0, 0.0, 1.0, 1.0)])
