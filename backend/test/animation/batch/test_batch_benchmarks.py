"""
backend/test/animation/batch/test_batch_benchmarks.py
=======================================================
Timing benchmarks: verify C++ batch functions achieve target speedups.

These tests MUST live in Python because:
  - They import Python reference implementations for comparison.
  - They measure wall-clock time using time.perf_counter() across
    Python↔C++ boundary calls (which require the GIL context).

Expected speedups (from asp_cpp_migration.md §3):
  seam_cut      > 5× (Phase 2 target: 27×)
  zone_lum_norm > 5× (Phase 2 target: 20×)
  bundle_adjust > 5× (Phase 3 target: 25×)

All tests:
  - Are xfail until the C++ implementation ships.
  - Are marked @pytest.mark.slow so standard CI skips them with -m "not slow".
  - Can be run explicitly with: just test-cpp or pytest -m slow

Usage:
  pytest backend/test/animation/batch/test_batch_benchmarks.py -v -m slow
"""

from __future__ import annotations

import time

import numpy as np
import pytest

try:
    import base as batch
    if getattr(batch, "__file__", None) is None:
        raise ImportError("base is a namespace package, not the compiled extension")
    HAS_BATCH = True
except ImportError:
    HAS_BATCH = False

pytestmark = [
    pytest.mark.skipif(not HAS_BATCH, reason="batch not built"),
    pytest.mark.slow,
]

MIN_SPEEDUP = 5.0  # Minimum acceptable speedup; Phase targets are 20–27×


def _mean_wall_time(fn, *args, n: int = 10, **kwargs) -> float:
    """Return mean wall-clock time per call (seconds)."""
    t0 = time.perf_counter()
    for _ in range(n):
        fn(*args, **kwargs)
    return (time.perf_counter() - t0) / n


def _rand_bgr(h: int, w: int, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.integers(0, 256, (h, w, 3), dtype=np.uint8)


# ---------------------------------------------------------------------------
# seam_cut speedup
# ---------------------------------------------------------------------------


class TestSeamCutSpeedup:
    @pytest.mark.xfail(
        reason="batch.seam.seam_cut not implemented yet (Phase 2)",
        raises=RuntimeError,
        strict=False,
    )
    def test_seam_cut_exceeds_5x_speedup(self):
        try:
            from backend.src.animation.rendering.compositing import _seam_cut_python  # type: ignore
        except ImportError:
            pytest.skip("Python reference _seam_cut_python not exposed")

        # 200-row × 1080-col zone (one full-HD zone strip)
        fa = _rand_bgr(200, 1080, seed=0)
        fb = _rand_bgr(200, 1080, seed=1)

        py_time  = _mean_wall_time(_seam_cut_python, fa, fb, n=10)
        cpp_time = _mean_wall_time(batch.seam.seam_cut, fa, fb, n=10)
        speedup  = py_time / max(cpp_time, 1e-9)

        print(
            f"\nseam_cut: py={py_time*1000:.1f}ms  "
            f"cpp={cpp_time*1000:.1f}ms  speedup={speedup:.1f}×"
        )
        assert speedup >= MIN_SPEEDUP, (
            f"seam_cut speedup {speedup:.1f}× < {MIN_SPEEDUP}×. "
            "Check -O3 -march=native and OpenMP parallelism flags."
        )


# ---------------------------------------------------------------------------
# zone_lum_norm speedup
# ---------------------------------------------------------------------------


class TestZoneLumNormSpeedup:
    @pytest.mark.xfail(
        reason="batch.compositing.zone_lum_norm not implemented yet (Phase 2)",
        raises=RuntimeError,
        strict=False,
    )
    def test_zone_lum_norm_exceeds_5x_speedup(self):
        try:
            from backend.src.animation.rendering.compositing import _zone_lum_norm_python  # type: ignore
        except ImportError:
            pytest.skip("Python reference _zone_lum_norm_python not exposed")

        # 400 × 600 BGR zone (typical zone crop size)
        fa = _rand_bgr(400, 600, seed=0)
        fb = _rand_bgr(400, 600, seed=1)

        py_time  = _mean_wall_time(_zone_lum_norm_python, fa, fb, n=10)
        cpp_time = _mean_wall_time(batch.compositing.zone_lum_norm, fa, fb, n=10)
        speedup  = py_time / max(cpp_time, 1e-9)

        print(
            f"\nzone_lum_norm: py={py_time*1000:.1f}ms  "
            f"cpp={cpp_time*1000:.1f}ms  speedup={speedup:.1f}×"
        )
        assert speedup >= MIN_SPEEDUP, (
            f"zone_lum_norm speedup {speedup:.1f}× < {MIN_SPEEDUP}×."
        )


# ---------------------------------------------------------------------------
# bundle_adjust speedup
# ---------------------------------------------------------------------------


class TestBundleAdjustSpeedup:
    @staticmethod
    def _chain_edges(N: int, step_px: float = 100.0) -> list:
        rng = np.random.default_rng(0)
        return [
            {
                "i": i, "j": i + 1,
                "dx": float(rng.normal(0, 1)),
                "dy": float(step_px + rng.normal(0, 2)),
                "weight": 0.9,
                "type": "adjacent",
            }
            for i in range(N - 1)
        ]

    @pytest.mark.xfail(
        reason="batch.bundle_adjust.bundle_adjust_affine not implemented yet (Phase 3)",
        raises=RuntimeError,
        strict=False,
    )
    def test_bundle_adjust_exceeds_5x_speedup(self):
        try:
            from backend.src.animation.alignment.bundle_adjust import _bundle_adjust_affine_python  # type: ignore
        except ImportError:
            pytest.skip("Python reference _bundle_adjust_affine_python not exposed")

        N = 14
        edges = self._chain_edges(N)

        py_time  = _mean_wall_time(_bundle_adjust_affine_python, edges, N, n=20)
        cpp_time = _mean_wall_time(batch.bundle_adjust.bundle_adjust_affine, edges, N, n=20)
        speedup  = py_time / max(cpp_time, 1e-9)

        print(
            f"\nbundle_adjust: py={py_time*1000:.2f}ms  "
            f"cpp={cpp_time*1000:.2f}ms  speedup={speedup:.1f}×"
        )
        assert speedup >= MIN_SPEEDUP, (
            f"bundle_adjust speedup {speedup:.1f}× < {MIN_SPEEDUP}×."
        )


# ---------------------------------------------------------------------------
# seam_batch (parallel) speedup
# ---------------------------------------------------------------------------


class TestSeamBatchSpeedup:
    @pytest.mark.xfail(
        reason="batch.seam.seam_batch not implemented yet (Phase 2)",
        raises=RuntimeError,
        strict=False,
    )
    def test_seam_batch_exceeds_5x_sequential(self):
        """
        seam_batch (OpenMP parallel) should be >5× faster than calling
        Python seam_cut sequentially for N-1 pairs.
        """
        try:
            from backend.src.animation.rendering.compositing import _seam_cut_python  # type: ignore
        except ImportError:
            pytest.skip("Python reference _seam_cut_python not exposed")

        N = 8
        H, W = 200, 540  # half-HD width zone
        rng = np.random.default_rng(0)
        zone_pairs = [
            {
                "fa": rng.integers(0, 256, (H, W, 3), dtype=np.uint8),
                "fb": rng.integers(0, 256, (H, W, 3), dtype=np.uint8),
                "cost": None,
            }
            for _ in range(N - 1)
        ]

        def sequential_python():
            for zp in zone_pairs:
                _seam_cut_python(zp["fa"], zp["fb"])

        py_time  = _mean_wall_time(sequential_python, n=5)
        cpp_time = _mean_wall_time(batch.seam.seam_batch, zone_pairs, n=5)
        speedup  = py_time / max(cpp_time, 1e-9)

        print(
            f"\nseam_batch vs sequential: py={py_time*1000:.1f}ms  "
            f"cpp={cpp_time*1000:.1f}ms  speedup={speedup:.1f}×"
        )
        assert speedup >= MIN_SPEEDUP, (
            f"seam_batch speedup {speedup:.1f}× < {MIN_SPEEDUP}×."
        )
