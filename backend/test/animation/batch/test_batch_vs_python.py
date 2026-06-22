"""
backend/test/animation/batch/test_batch_vs_python.py
======================================================
Parity tests: C++ batch implementations vs Python reference functions.

These tests MUST live in Python because they require importing the Python
reference implementations to compare against.  The test structure is:

  1. Build the same input in Python (numpy arrays).
  2. Call the Python reference (pure Python or Python+OpenCV).
  3. Call the C++ batch function via pybind11.
  4. Assert pixel-level agreement within documented tolerances.

Tolerances (from asp_cpp_migration.md §3 Testing):
  seam path  : ≤ 1 px  (DP floating-point ordering)
  affine tx/ty: ≤ 0.5 px (numerical precision)

All tests are xfail-skipped:
  - When batch is not built (ImportError)
  - When the C++ impl is still a stub (RuntimeError from BATCH_NOT_IMPLEMENTED)

Phase guard tags:
  [phase2] : seam_cut, compositing zone functions
  [phase3] : bundle_adjust, matching

Usage:
  pytest backend/test/animation/batch/test_batch_vs_python.py -v
"""

from __future__ import annotations

import numpy as np
import pytest

try:
    import batch

    HAS_BATCH = True
except ImportError:
    HAS_BATCH = False

pytestmark = pytest.mark.skipif(not HAS_BATCH, reason="batch not built")


def _xfail_until_implemented(phase: str):
    """Mark as xfail if the C++ stub raises RuntimeError."""
    return pytest.mark.xfail(
        reason=f"C++ implementation not yet complete ({phase})",
        raises=RuntimeError,
        strict=False,
    )


# ---------------------------------------------------------------------------
# Fixtures: reproducible random frames
# ---------------------------------------------------------------------------


def _rand_bgr(h: int, w: int, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.integers(0, 256, (h, w, 3), dtype=np.uint8)


def _rand_mask(h: int, w: int, seed: int = 0, fg_ratio: float = 0.4) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return (rng.random((h, w)) > (1 - fg_ratio)).astype(np.uint8) * 255


# ---------------------------------------------------------------------------
# §batch.seam.seam_cut  vs  Python reference
# ---------------------------------------------------------------------------


class TestSeamCutVsPython:
    """
    seam_cut parity: path must agree with Python reference within ±1 px.
    Requires the Python reference to be exposed as a testable function.
    """

    @_xfail_until_implemented("Phase 2")
    def test_path_length_matches(self):
        try:
            from backend.src.animation.rendering.compositing import _seam_cut_python  # type: ignore
        except ImportError:
            pytest.skip("Python reference _seam_cut_python not yet exposed for testing")

        H, W = 40, 60
        fa = _rand_bgr(H, W, 0)
        fb = _rand_bgr(H, W, 1)

        path_py  = np.array(_seam_cut_python(fa, fb), dtype=np.int32)
        path_cpp = np.array(batch.seam.seam_cut(fa, fb), dtype=np.int32)

        assert len(path_py) == W
        assert len(path_cpp) == W

    @_xfail_until_implemented("Phase 2")
    def test_pixel_agreement_within_1px(self):
        try:
            from backend.src.animation.rendering.compositing import _seam_cut_python  # type: ignore
        except ImportError:
            pytest.skip("Python reference _seam_cut_python not yet exposed for testing")

        H, W = 40, 60
        fa = _rand_bgr(H, W, 42)
        fb = _rand_bgr(H, W, 43)

        path_py  = np.array(_seam_cut_python(fa, fb), dtype=np.int32)
        path_cpp = np.array(batch.seam.seam_cut(fa, fb), dtype=np.int32)

        max_diff = np.abs(path_py - path_cpp).max()
        assert max_diff <= 1, (
            f"Max path disagreement {max_diff} px exceeds 1 px tolerance. "
            "Floating-point tie-breaking in DP allows ±1 px."
        )

    @_xfail_until_implemented("Phase 2")
    @pytest.mark.parametrize("seed", [0, 7, 42, 99, 123])
    def test_pixel_agreement_multiple_seeds(self, seed: int):
        try:
            from backend.src.animation.rendering.compositing import _seam_cut_python  # type: ignore
        except ImportError:
            pytest.skip("Python reference _seam_cut_python not yet exposed for testing")

        H, W = 60, 90
        fa = _rand_bgr(H, W, seed)
        fb = _rand_bgr(H, W, seed + 1000)

        path_py  = np.array(_seam_cut_python(fa, fb), dtype=np.int32)
        path_cpp = np.array(batch.seam.seam_cut(fa, fb), dtype=np.int32)

        assert np.abs(path_py - path_cpp).max() <= 1


# ---------------------------------------------------------------------------
# §batch.compositing zone functions  vs  Python references
# ---------------------------------------------------------------------------


class TestZoneLumNormVsPython:
    @_xfail_until_implemented("Phase 2")
    def test_luma_agreement_within_2(self):
        try:
            from backend.src.animation.rendering.compositing import _zone_lum_norm_python  # type: ignore
        except ImportError:
            pytest.skip("Python reference _zone_lum_norm_python not yet exposed")

        H, W = 64, 80
        fa = _rand_bgr(H, W, 0)
        fb = _rand_bgr(H, W, 1)

        out_py  = _zone_lum_norm_python(fa, fb)
        out_cpp = batch.compositing.zone_lum_norm(fa, fb)

        max_diff = np.abs(
            out_py.astype(np.int32) - out_cpp.astype(np.int32)
        ).max()
        assert max_diff <= 2, (
            f"zone_lum_norm max pixel diff {max_diff} > 2 tolerance "
            "(colour space round-trip rounding)"
        )


class TestZoneChromaAlignVsPython:
    @_xfail_until_implemented("Phase 2")
    def test_chroma_agreement_within_2(self):
        try:
            from backend.src.animation.rendering.compositing import _zone_chroma_align_python  # type: ignore
        except ImportError:
            pytest.skip("Python reference _zone_chroma_align_python not yet exposed")

        H, W = 64, 80
        fa = _rand_bgr(H, W, 2)
        fb = _rand_bgr(H, W, 3)

        out_py  = _zone_chroma_align_python(fa, fb)
        out_cpp = batch.compositing.zone_chroma_align(fa, fb)

        max_diff = np.abs(
            out_py.astype(np.int32) - out_cpp.astype(np.int32)
        ).max()
        assert max_diff <= 2


# ---------------------------------------------------------------------------
# §batch.bundle_adjust.bundle_adjust_affine  vs  Python reference
# ---------------------------------------------------------------------------


class TestBundleAdjustVsPython:
    @staticmethod
    def _make_chain(N: int, step_px: float = 100.0, seed: int = 42) -> list:
        rng = np.random.default_rng(seed)
        return [
            {
                "i": i, "j": i + 1,
                "dx": float(rng.normal(0, 1)),
                "dy": float(step_px + rng.normal(0, 2)),
                "weight": 0.95,
                "type": "adjacent",
            }
            for i in range(N - 1)
        ]

    @_xfail_until_implemented("Phase 3")
    def test_tx_ty_agreement_within_half_px(self):
        try:
            from backend.src.animation.alignment.bundle_adjust import _bundle_adjust_affine_python  # type: ignore
        except ImportError:
            pytest.skip("Python reference _bundle_adjust_affine_python not exposed")

        N = 6
        edges = self._make_chain(N, step_px=120.0, seed=99)

        affines_py  = _bundle_adjust_affine_python(edges, N)
        affines_cpp = batch.bundle_adjust.bundle_adjust_affine(edges, N)

        assert len(affines_cpp) == N
        for i in range(N):
            for key in ("tx", "ty"):
                diff = abs(affines_py[i][key] - affines_cpp[i][key])
                assert diff <= 0.5, (
                    f"Frame {i} {key}: py={affines_py[i][key]:.3f} "
                    f"cpp={affines_cpp[i][key]:.3f} diff={diff:.3f} > 0.5 px"
                )

    @_xfail_until_implemented("Phase 3")
    @pytest.mark.parametrize("N,step_px,seed", [
        (4,  80.0,  0),
        (6, 100.0,  7),
        (8, 120.0, 42),
        (10, 60.0, 99),
    ])
    def test_agreement_multiple_chain_configs(self, N: int, step_px: float, seed: int):
        try:
            from backend.src.animation.alignment.bundle_adjust import _bundle_adjust_affine_python  # type: ignore
        except ImportError:
            pytest.skip("Python reference _bundle_adjust_affine_python not exposed")

        edges = self._make_chain(N, step_px, seed)
        affines_py  = _bundle_adjust_affine_python(edges, N)
        affines_cpp = batch.bundle_adjust.bundle_adjust_affine(edges, N)

        for i in range(N):
            for key in ("tx", "ty"):
                diff = abs(affines_py[i][key] - affines_cpp[i][key])
                assert diff <= 0.5, f"N={N} seed={seed} frame={i} {key} diff={diff:.3f}"


# ---------------------------------------------------------------------------
# §batch.seam.build_seam_cost_map  vs  Python reference
# ---------------------------------------------------------------------------


class TestBuildSeamCostMapVsPython:
    @_xfail_until_implemented("Phase 2")
    def test_cost_map_agreement(self):
        try:
            from backend.src.animation.rendering.compositing import _build_seam_cost_map_python  # type: ignore
        except ImportError:
            pytest.skip("Python reference _build_seam_cost_map_python not exposed")

        H, W = 50, 80
        fa     = _rand_bgr(H, W, 0)
        mask_a = _rand_mask(H, W, 0)
        mask_b = _rand_mask(H, W, 1)

        cost_py  = _build_seam_cost_map_python(fa, mask_a, mask_b)
        cost_cpp = batch.seam.build_seam_cost_map(fa, mask_a, mask_b)

        assert cost_cpp.shape == (H, W)
        # Max absolute difference in cost values ≤ 0.01 (float32 precision)
        max_diff = np.abs(cost_py - cost_cpp).max()
        assert max_diff <= 0.01, f"Cost map max diff {max_diff:.4f} > 0.01"
