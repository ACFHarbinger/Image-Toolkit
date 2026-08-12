"""Tests for `hie_middleware.logic_bridge.solvers` — the thin `base.hie` adapter.

Previously untested: `HAVE_NATIVE_HIE`'s fallback-unavailable error path is
exercised unconditionally; the native-path assertions run only when the
compiled `base` extension is importable (`HAVE_NATIVE_HIE`), since this
suite must also pass in a middleware-only install with no C++ extension.
"""

import pytest

from hie_middleware.jobs.exact_dp import Correspondence, SeamPixel
from hie_middleware.logic_bridge.solvers import (
    HAVE_NATIVE_HIE,
    native_de_solve,
    native_pso_solve,
    native_solve_alignment_gnc,
    native_solve_seam,
)

requires_native = pytest.mark.skipif(not HAVE_NATIVE_HIE, reason="compiled base.hie extension not available")


def _sphere(p: list[float]) -> float:
    return sum(x * x for x in p)


@requires_native
def test_native_pso_solve_minimizes_sphere():
    best = native_pso_solve(_sphere, [(-10.0, 10.0), (-10.0, 10.0)], n_particles=20, max_iter=100)
    assert _sphere(best) < 0.1


@requires_native
def test_native_de_solve_minimizes_sphere():
    best = native_de_solve(_sphere, [(-10.0, 10.0), (-10.0, 10.0)], population_size=20, max_iter=100)
    assert _sphere(best) < 0.1


@requires_native
def test_native_solve_seam_avoids_masked_barrier():
    # Column 1 is a full-height masked barrier; the seam must route around it.
    grid = [
        [SeamPixel(1.0), SeamPixel(0.0, masked=True), SeamPixel(1.0)],
        [SeamPixel(1.0), SeamPixel(0.0, masked=True), SeamPixel(1.0)],
        [SeamPixel(1.0), SeamPixel(0.0, masked=True), SeamPixel(1.0)],
    ]
    result = native_solve_seam(grid)
    assert result.success
    assert all(x != 1 for x in result.seam_x)


@requires_native
def test_native_solve_seam_prefers_zero_energy_column():
    grid = [
        [SeamPixel(1.0), SeamPixel(0.0), SeamPixel(1.0)],
        [SeamPixel(1.0), SeamPixel(0.0), SeamPixel(1.0)],
        [SeamPixel(1.0), SeamPixel(0.0), SeamPixel(1.0)],
    ]
    result = native_solve_seam(grid)
    assert result.success
    assert all(x == 1 for x in result.seam_x)


@requires_native
def test_native_solve_alignment_gnc_recovers_pure_translation():
    # dst = src + (10, -5), no scale or outliers — GNC should recover this exactly.
    correspondences = [
        Correspondence(src_x=float(i), src_y=float(i * 2), dst_x=float(i) + 10.0, dst_y=float(i * 2) - 5.0)
        for i in range(20)
    ]
    result = native_solve_alignment_gnc(correspondences)
    assert result.success
    assert result.model.tx == pytest.approx(10.0, abs=1e-2)
    assert result.model.ty == pytest.approx(-5.0, abs=1e-2)
    assert result.model.scale == pytest.approx(1.0, abs=1e-2)
    assert result.inlier_count == 20


def test_native_functions_raise_when_unavailable(monkeypatch):
    monkeypatch.setattr("hie_middleware.logic_bridge.solvers.HAVE_NATIVE_HIE", False)
    with pytest.raises(RuntimeError):
        native_pso_solve(_sphere, [(-1.0, 1.0)], n_particles=4, max_iter=1)
    with pytest.raises(RuntimeError):
        native_de_solve(_sphere, [(-1.0, 1.0)], population_size=4, max_iter=1)
    with pytest.raises(RuntimeError):
        native_solve_seam([[SeamPixel(0.0)]])
    with pytest.raises(RuntimeError):
        native_solve_alignment_gnc([Correspondence(0.0, 0.0, 1.0, 1.0)])
