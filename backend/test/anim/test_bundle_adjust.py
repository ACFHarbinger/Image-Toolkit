"""
Tests for the global bundle adjustment stage (Stage 7).

Issue categories covered:
  C — Alignment failure: frame clustering, wrong order, non-monotonic ty values.

All tests use synthetic edges with no GPU dependency.
"""

from __future__ import annotations

import os
import sys

import numpy as np
import pytest

# Repo root is 4 dirname() calls up from backend/test/anim/test_*.py
_repo_root = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
sys.path.insert(0, _repo_root)

from backend.src.anim.bundle_adjust import _bundle_adjust_affine  # noqa: E402
from conftest import compute_ty_gaps, make_edge  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _tys(affines):
    return np.array([float(a[1, 2]) for a in affines])


# ---------------------------------------------------------------------------
# 1. Basic correctness
# ---------------------------------------------------------------------------


class TestPerfectChainTranslation:
    """A perfect sequential chain should yield monotonically spaced ty values."""

    def test_3frame_chain_ty_values(self):
        edges = [make_edge(i, i + 1, dy=300.0) for i in range(2)]
        affines = _bundle_adjust_affine(edges, 3, use_affine=False)
        tys = _tys(affines)
        gaps = np.diff(sorted(tys))
        assert len(gaps) == 2
        assert np.allclose(gaps, 300.0, atol=5.0), f"gaps={gaps}"

    def test_5frame_chain_monotonic(self):
        edges = [make_edge(i, i + 1, dy=250.0) for i in range(4)]
        affines = _bundle_adjust_affine(edges, 5, use_affine=False)
        tys = _tys(affines)
        sorted_tys = sorted(tys)
        gaps = np.diff(sorted_tys)
        assert all(g > 0 for g in gaps), f"Non-positive gaps: {gaps}"

    def test_uniform_dy_produces_uniform_gaps(self):
        dy = 200.0
        N = 6
        edges = [make_edge(i, i + 1, dy=dy) for i in range(N - 1)]
        affines = _bundle_adjust_affine(edges, N, use_affine=False)
        gaps = compute_ty_gaps(affines)
        assert np.allclose(gaps, dy, atol=10.0), f"gaps={gaps}"


class TestAnchorFrame:
    """Frame 0 must be pinned near identity (ty≈0) to prevent global drift."""

    def test_frame0_ty_near_zero(self):
        edges = [make_edge(i, i + 1, dy=300.0) for i in range(3)]
        affines = _bundle_adjust_affine(edges, 4, use_affine=False)
        assert abs(float(affines[0][1, 2])) < 5.0, (
            f"frame0 ty={affines[0][1, 2]:.2f} should be near 0"
        )

    def test_frame0_tx_near_zero_translation_mode(self):
        edges = [make_edge(i, i + 1, dx=5.0, dy=300.0) for i in range(3)]
        affines = _bundle_adjust_affine(edges, 4, use_affine=False)
        assert abs(float(affines[0][0, 2])) < 5.0


class TestTranslationOnlyMode:
    """use_affine=False should produce pure translation matrices."""

    def test_returns_translation_matrices(self):
        edges = [make_edge(i, i + 1, dy=300.0) for i in range(2)]
        affines = _bundle_adjust_affine(edges, 3, use_affine=False)
        for i, M in enumerate(affines):
            assert M.shape == (2, 3), f"frame{i}: shape={M.shape}"
            assert np.allclose(M[:2, :2], np.eye(2), atol=1e-4), (
                f"frame{i}: rotation block deviated from identity: {M[:2, :2]}"
            )

    def test_returns_n_affines(self):
        N = 7
        edges = [make_edge(i, i + 1, dy=150.0) for i in range(N - 1)]
        affines = _bundle_adjust_affine(edges, N, use_affine=False)
        assert len(affines) == N


class TestAffineMode:
    """use_affine=True should return 2×3 matrices (may include small rotation)."""

    def test_returns_n_affines_affine_mode(self):
        N = 4
        edges = [make_edge(i, i + 1, dy=300.0) for i in range(N - 1)]
        affines = _bundle_adjust_affine(edges, N, use_affine=True)
        assert len(affines) == N

    def test_affine_mode_ty_close_to_translation_mode(self):
        """When edges are pure translation, affine and translation modes agree closely."""
        N = 4
        edges = [make_edge(i, i + 1, dy=300.0) for i in range(N - 1)]
        aff_t = _bundle_adjust_affine(edges, N, use_affine=False)
        aff_a = _bundle_adjust_affine(edges, N, use_affine=True)
        tys_t = _tys(aff_t)
        tys_a = _tys(aff_a)
        assert np.allclose(sorted(tys_t), sorted(tys_a), atol=10.0), (
            f"translation mode tys={sorted(tys_t)}, affine mode tys={sorted(tys_a)}"
        )


# ---------------------------------------------------------------------------
# 2. Robustness to bad edges (documents missing RANSAC — Issues C)
# ---------------------------------------------------------------------------


class TestFrameClusteringPattern:
    """
    Near-zero dy edges cause multiple frames to land at the same canvas position.
    This is the root cause of test8 and test9 catastrophic failures.

    These tests document the CURRENT behavior (clustering occurs) and the
    EXPECTED behavior after the Priority-1 fix (clusters are rejected/corrected).
    """

    def test_near_zero_edges_inverted_outlier_rejection(self):
        """
        When most edges have near-zero dy and only one is normal, the BA outlier
        rejection correctly identifies the normal edge as a statistical outlier
        and prunes it. The remaining near-zero edges produce a low-ratio (but
        physically incorrect) result.
        
        This demonstrates why the min-step guard in _filter_edges is required
        BEFORE bundle adjustment — to prevent the inverted consensus scenario.
        """
        edges = [
            make_edge(0, 1, dy=5.0),   # near-zero
            make_edge(1, 2, dy=8.0),   # near-zero
            make_edge(2, 3, dy=6.0),   # near-zero
            make_edge(3, 4, dy=300.0), # one normal — pruned as outlier!
        ]
        affines = _bundle_adjust_affine(edges, 5, use_affine=False)
        gaps = compute_ty_gaps(affines)
    
        max_gap = float(gaps.max())
        median_gap = float(np.median(gaps))
        ratio = max_gap / max(median_gap, 1.0)
    
        # The 300px edge is pruned, leaving only near-zero edges.
        # The ratio of max (8) to median (6) is < 3.0.
        assert ratio < 3.0, (
            f"Expected the normal edge to be pruned as an outlier (ratio < 3), "
            f"but got ratio={ratio:.1f}."
        )

    def test_all_near_zero_edges_degenerate_output(self):
        """All near-zero edges → all frames cluster at ~0; canvas height collapses."""
        edges = [make_edge(i, i + 1, dy=3.0) for i in range(4)]
        affines = _bundle_adjust_affine(edges, 5, use_affine=False)
        tys = _tys(affines)
        canvas_extent = float(max(tys) - min(tys))
        assert canvas_extent < 50.0, (
            f"All near-zero dy edges should produce a tiny canvas extent, "
            f"got {canvas_extent:.1f}px"
        )

    def test_single_outlier_edge_rejected_by_ba(self):
        """
        A single edge with 5× the expected dy should be pruned by the
        residual-based outlier rejection, keeping the result near inlier dy.
        """
        inlier_dy = 200.0
        edges = [
            make_edge(0, 1, dy=inlier_dy),
            make_edge(1, 2, dy=inlier_dy),
            make_edge(2, 3, dy=inlier_dy * 5),  # outlier
            make_edge(3, 4, dy=inlier_dy),
        ]
        affines = _bundle_adjust_affine(edges, 5, use_affine=False)
        gaps = compute_ty_gaps(affines)
        max_gap = float(gaps.max())
        median_gap = float(np.median(gaps))
        ratio = max_gap / max(median_gap, 1.0)

        # After outlier rejection, the 5× outlier edge should be pruned
        # and the remaining inlier edges should produce a ratio near 1.0.
        assert ratio < 3.0, (
            f"Outlier should have been pruned by BA residual rejection "
            f"(ratio={ratio:.1f}), but it still distorts the result."
        )


class TestNonMonotonicFrameOrder:
    """
    Non-monotonic ty values (test2, test7 pattern) indicate wrong-direction matches.
    Bundle adjust alone cannot fix these — they must be caught by _filter_edges first.
    """

    def test_reversed_edge_produces_non_monotonic_tys(self):
        """One reversed edge (dy<0 among otherwise positive chain) → non-monotonic."""
        edges = [
            make_edge(0, 1, dy=300.0),
            make_edge(1, 2, dy=-280.0),  # reversed — wrong direction
            make_edge(2, 3, dy=300.0),
        ]
        affines = _bundle_adjust_affine(edges, 4, use_affine=False)
        tys = _tys(affines)
        diffs = np.diff(tys)
        has_non_monotonic = not (np.all(diffs >= 0) or np.all(diffs <= 0))
        assert has_non_monotonic, (
            f"Expected non-monotonic tys from reversed edge, got tys={tys}"
        )

    def test_compute_ty_gap_ratio(self):
        """Utility: compute alignment health ratio from affine list."""
        affines = [
            np.array([[1, 0, 0], [0, 1, ty]], dtype=np.float32)
            for ty in [0, 300, 600, 900]
        ]
        gaps = compute_ty_gaps(affines)
        assert gaps.max() / np.median(gaps) == pytest.approx(1.0, abs=0.01)


# ---------------------------------------------------------------------------
# 3. Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_two_frames_minimal_input(self):
        edges = [make_edge(0, 1, dy=200.0)]
        affines = _bundle_adjust_affine(edges, 2, use_affine=False)
        assert len(affines) == 2
        assert abs(float(affines[0][1, 2])) < 5.0

    def test_skip_pair_edge_included(self):
        """Skip-pair edges (non-adjacent) are valid inputs."""
        edges = [
            make_edge(0, 1, dy=300.0),
            make_edge(1, 2, dy=300.0),
            make_edge(0, 2, dy=600.0),  # skip-pair: sum of adj edges
        ]
        affines = _bundle_adjust_affine(edges, 3, use_affine=False)
        gaps = compute_ty_gaps(affines)
        assert all(g > 0 for g in gaps)

    def test_dx_component_propagates(self):
        """Horizontal tx offsets (diagonal scroll) should be preserved."""
        edges = [make_edge(i, i + 1, dx=50.0, dy=200.0) for i in range(2)]
        affines = _bundle_adjust_affine(edges, 3, use_affine=False)
        txs = [float(a[0, 2]) for a in affines]
        tx_range = max(txs) - min(txs)
        assert tx_range > 10.0, (
            f"Expected non-zero tx range for dx=50 edges, got tx_range={tx_range:.1f}"
        )
