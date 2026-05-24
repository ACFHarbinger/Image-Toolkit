"""
Tests for affine matrix validation — documents the expected behavior of a
`_validate_affines` function to be implemented as part of Priority-1 and
Priority-3b fixes.

Issue categories covered:
  C — Alignment failure: frame clustering (min_gap=0), high ratio (>3×).
  D/G — Affine rotation/scale mismatch (test18: good ty/tx, bad rotation).

The helper `_validate_affines` is defined inline here as the specification of
correct behavior.  When the function is added to `src.anim.bundle_adjust` (or
a new `src.anim.validation` module), replace the inline version with an import.
"""

from __future__ import annotations

import os
import sys
from typing import List, NamedTuple

import numpy as np
import pytest

_repo_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
sys.path.insert(0, _repo_root)

from conftest import make_rotation_affine, make_translation_affine  # noqa: E402


# ---------------------------------------------------------------------------
# Reference implementation of _validate_affines (specification)
# ---------------------------------------------------------------------------


class AffineHealth(NamedTuple):
    valid: bool
    ratio: float
    min_gap: float
    max_rotation: float
    max_scale_dev: float
    reason: str


def _validate_affines(
    affines: List[np.ndarray],
    min_step: float = 50.0,
    max_ratio: float = 3.0,
    max_rotation: float = 0.1,
    max_scale_dev: float = 0.1,
) -> AffineHealth:
    """
    Specification of the full affine health check.

    A frame set is considered INVALID if ANY of the following hold:
      1. max_gap / median_gap > max_ratio  (uneven spacing / clustering)
      2. min_gap < min_step                (co-located frames)
      3. any off-diagonal element > max_rotation  (rotation mismatch — test18)
      4. any diagonal element deviates from 1.0 by > max_scale_dev (scale drift)
    """
    N = len(affines)
    if N < 2:
        return AffineHealth(True, 1.0, 0.0, 0.0, 0.0, "single frame")

    tys = np.array([float(a[1, 2]) for a in affines])
    sorted_tys = np.sort(tys)
    gaps = np.diff(sorted_tys)

    if len(gaps) == 0:
        return AffineHealth(False, float("inf"), 0.0, 0.0, 0.0, "all frames at same position")

    median_gap = float(np.median(gaps))
    max_gap = float(gaps.max())
    min_gap = float(gaps.min())
    ratio = max_gap / max(median_gap, 1.0)

    max_rot = max(max(abs(float(a[0, 1])), abs(float(a[1, 0]))) for a in affines)
    max_sc = max(
        max(abs(float(a[0, 0]) - 1.0), abs(float(a[1, 1]) - 1.0)) for a in affines
    )

    if ratio > max_ratio:
        return AffineHealth(False, ratio, min_gap, max_rot, max_sc, f"ratio={ratio:.1f} > {max_ratio}")
    if min_gap < min_step:
        return AffineHealth(False, ratio, min_gap, max_rot, max_sc, f"min_gap={min_gap:.1f}px < {min_step}px")
    if max_rot > max_rotation:
        return AffineHealth(False, ratio, min_gap, max_rot, max_sc, f"rotation={max_rot:.3f} > {max_rotation}")
    if max_sc > max_scale_dev:
        return AffineHealth(False, ratio, min_gap, max_rot, max_sc, f"scale_dev={max_sc:.3f} > {max_scale_dev}")

    return AffineHealth(True, ratio, min_gap, max_rot, max_sc, "ok")


# ---------------------------------------------------------------------------
# 1. Clean affines — should pass
# ---------------------------------------------------------------------------


class TestGoodAffinesPass:
    def test_perfect_chain(self):
        """Well-spaced, pure-translation affines should be marked valid."""
        affines = [make_translation_affine(ty=i * 300.0) for i in range(5)]
        h = _validate_affines(affines)
        assert h.valid, f"Expected valid, got: {h.reason}"

    def test_test11_baseline_pattern(self):
        """test11 baseline: ratio=1.1×, min_gap=59px → valid."""
        tys = [0, 59, 130, 200, 275, 345, 420]
        affines = [make_translation_affine(ty=float(ty)) for ty in tys]
        h = _validate_affines(affines, min_step=50.0)
        assert h.valid, f"test11-like affines should be valid: {h.reason}"
        assert h.ratio < 2.0

    def test_test6_baseline_pattern(self):
        """test6 baseline: ratio=1.4×, min_gap=126px → valid."""
        gaps = [174, 177, 178, 163, 238, 133, 137, 126]
        tys = np.cumsum([0] + gaps).tolist()
        affines = [make_translation_affine(ty=float(ty)) for ty in tys]
        h = _validate_affines(affines, min_step=50.0)
        assert h.valid, f"test6-like affines should be valid: {h.reason}"

    def test_borderline_ratio_large_min_gap(self):
        """test12: ratio=2.9×, min_gap=173px → valid (min_gap large enough)."""
        tys = [0, 173, 400, 600, 780, 1280]
        affines = [make_translation_affine(ty=float(ty)) for ty in tys]
        h = _validate_affines(affines, min_step=50.0, max_ratio=3.0)
        assert h.valid, f"Borderline ratio with large min_gap should be valid: {h.reason}"
        assert h.min_gap >= 173.0


# ---------------------------------------------------------------------------
# 2. High ratio detection (frame clustering)
# ---------------------------------------------------------------------------


class TestHighRatioDetection:
    def test_test8_pattern_ratio_59x(self):
        """test8: ratio=5.9×, min_gap=16px → invalid."""
        tys = [1085, 243, 762, 259, 1166, 1785, 0, 333, 726, 1263, 1806]
        affines = [make_translation_affine(ty=float(ty)) for ty in tys]
        h = _validate_affines(affines)
        assert not h.valid, f"test8-like affines should be INVALID: ratio={h.ratio:.1f}"
        assert h.ratio > 3.0

    def test_test9_pattern_ratio_118x(self):
        """test9: ratio=11.8× → invalid."""
        tys = [680, 654, 628, 624, 471, 459, 451, 145, 0]
        affines = [make_translation_affine(ty=float(ty)) for ty in tys]
        h = _validate_affines(affines)
        assert not h.valid

    def test_test16_pattern_ratio_61x(self):
        """test16: ratio=6.1×, min_gap=12px → invalid."""
        tys = [430, 0, 746, 843, 418, 370, 1021, 902, 807, 565]
        affines = [make_translation_affine(ty=float(ty)) for ty in tys]
        h = _validate_affines(affines)
        assert not h.valid
        assert h.min_gap < 50.0

    def test_single_2x_outlier_ratio_threshold(self):
        """One gap at 3.5× median → exceeds threshold → invalid."""
        gaps = [200, 200, 700, 200, 200]
        tys = np.cumsum([0] + gaps).tolist()
        affines = [make_translation_affine(ty=float(ty)) for ty in tys]
        h = _validate_affines(affines, max_ratio=3.0)
        assert not h.valid
        assert h.ratio == pytest.approx(3.5, abs=0.1)


# ---------------------------------------------------------------------------
# 3. Min gap detection (co-located frames)
# ---------------------------------------------------------------------------


class TestMinGapDetection:
    def test_test21_colocated_triplet(self):
        """test21: 3 frames at ty=0 → min_gap=0 → invalid."""
        tys = [0, 177, 355, 532, 710, 887, 1064, 1242, 0, 0]
        affines = [make_translation_affine(ty=float(ty)) for ty in tys]
        h = _validate_affines(affines)
        assert not h.valid
        assert h.min_gap == pytest.approx(0.0, abs=1.0)

    def test_zero_gap_two_identical_frames(self):
        """Two frames at the same ty → min_gap=0 → invalid."""
        affines = [make_translation_affine(ty=float(ty)) for ty in [0, 0, 300, 600]]
        h = _validate_affines(affines)
        assert not h.valid

    def test_small_gap_below_min_step(self):
        """Gap of 10px < min_step=50px → invalid."""
        affines = [make_translation_affine(ty=float(ty)) for ty in [0, 10, 300, 600]]
        h = _validate_affines(affines, min_step=50.0)
        assert not h.valid
        assert h.min_gap < 50.0


# ---------------------------------------------------------------------------
# 4. Rotation / scale mismatch (test18 pattern — Category G)
# ---------------------------------------------------------------------------


class TestRotationScaleMismatch:
    def test_small_rotation_detected(self):
        """
        test18 pattern: ty/tx look healthy but affine matrices contain significant
        rotation components → canvas placement will misalign warped frames.
        """
        affines = [
            make_rotation_affine(tx=0.0, ty=float(i * 300), angle_deg=8.0)
            for i in range(5)
        ]
        h = _validate_affines(affines, max_rotation=0.1)
        assert not h.valid, (
            f"8° rotation should be flagged; max_rotation={h.max_rotation:.3f}"
        )
        assert h.max_rotation > 0.05

    def test_pure_translation_no_rotation_warning(self):
        """Pure translation affines have off-diagonal=0 → rotation check passes."""
        affines = [make_translation_affine(ty=i * 300.0) for i in range(5)]
        h = _validate_affines(affines, max_rotation=0.1)
        assert h.max_rotation == pytest.approx(0.0, abs=1e-6)

    def test_scale_deviation_detected(self):
        """Scale drift (a[0][0] != 1.0) should be flagged."""
        affines = [
            np.array([[1.2, 0.0, 0.0], [0.0, 1.2, float(i * 300)]], dtype=np.float32)
            for i in range(4)
        ]
        h = _validate_affines(affines, max_scale_dev=0.1)
        assert not h.valid
        assert h.max_scale_dev > 0.1

    def test_tiny_rotation_within_tolerance(self):
        """Sub-pixel rotation (< 0.5°) should not trigger the rotation check."""
        affines = [
            make_rotation_affine(tx=0.0, ty=float(i * 300), angle_deg=0.3)
            for i in range(5)
        ]
        h = _validate_affines(affines, max_rotation=0.1)
        assert h.max_rotation < 0.1


# ---------------------------------------------------------------------------
# 5. Non-monotonic order (test2, test7)
# ---------------------------------------------------------------------------


class TestNonMonotonicOrder:
    def test_non_monotonic_tys_still_sorted_for_gap_computation(self):
        """
        Even if affines have non-monotonic ty (by frame index), gap computation
        sorts them first. Non-monotonicity is detectable via a separate check.
        """
        tys_by_frame = [0, 49, 99, 130, 165, 335, 538, 465, 265, 816, 771, 821, 991, 1040]
        affines = [make_translation_affine(ty=float(ty)) for ty in tys_by_frame]

        sorted_tys = sorted(tys_by_frame)
        gaps = np.diff(sorted_tys)
        ratio = float(gaps.max()) / float(np.median(gaps))

        h = _validate_affines(affines)
        assert not h.valid, f"test7 non-monotonic affines should be invalid: {h.reason}"
        assert h.ratio > 3.0

    def test_decreasing_tys_valid_if_evenly_spaced(self):
        """
        test9 affines are monotonically decreasing (reverse order) — the gap
        computation should handle this correctly.
        """
        tys = [900, 700, 500, 300, 100]
        affines = [make_translation_affine(ty=float(ty)) for ty in tys]
        h = _validate_affines(affines, min_step=50.0)
        assert h.valid, f"Evenly spaced decreasing tys should be valid: {h.reason}"
        assert h.ratio == pytest.approx(1.0, abs=0.01)


# ---------------------------------------------------------------------------
# 6. Alignment statistics helper
# ---------------------------------------------------------------------------


class TestAlignmentStats:
    def test_stats_for_positive_baseline(self):
        """test22: ratio=1.0×, min_gap=83px → ratio near 1.0."""
        tys = [0, 83, 166, 249, 332, 415, 498, 581, 664, 747, 830]
        affines = [make_translation_affine(ty=float(ty)) for ty in tys]
        h = _validate_affines(affines)
        assert h.ratio == pytest.approx(1.0, abs=0.05)
        assert h.min_gap == pytest.approx(83.0, abs=1.0)
        assert h.valid

    def test_ratio_calculation_matches_report_values(self):
        """Verify ratio formula: max_gap / median_gap matches the report."""
        gaps = [143, 129, 151, 167, 400, 154, 443, 170, 477, 103, 109, 135, 114]
        tys = np.cumsum([0] + sorted(gaps)).tolist()
        affines = [make_translation_affine(ty=float(ty)) for ty in tys]
        h = _validate_affines(affines)
        assert h.ratio == pytest.approx(477 / 151, abs=0.5)
