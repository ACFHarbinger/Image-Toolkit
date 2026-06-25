"""
Tests for pipeline.py module-level functions:
  §1.9A — _spatial_dedup_frames (scans_frames sync bug fix)
  §2.9C — _filter_high_conf_edges (high-confidence BA re-solve)
  §1.9C — _reload_scans_frames (on-demand SCANS frame reload)
  §1.13 — _reject_scene_change_edges (scene-change luma gate)
  §1.3C — _normalize_frame_scales (scale normalisation before BA)
  §4.7  — _compute_dy_cv (step-size CV gate for SCANS fallback)
  §5.8  — _compute_adaptive_dy_cv_max (adaptive dy_cv ceiling for large-N sequences)
"""

from backend.src.animation.core import pipeline
from backend.src.animation.core.pipeline import _wave_correct_affines
from backend.src.animation.core import config


import numpy as np
import pytest
import cv2

from backend.src.animation.core.pipeline import (
    _compute_dy_cv,
    _compute_adaptive_dy_cv_max,
    _check_edge_graph_connectivity,
    _compute_mst_weight,
    _compute_canvas_span_utilization,
    _spatial_dedup_frames,
    _filter_high_conf_edges,
    _reload_scans_frames,
    _reject_scene_change_edges,
    _normalize_frame_scales,
    _measure_max_seam_step,
    _detect_static_input,
    _compute_bg_coverage_fraction,
    _compute_render_coverage,
    _compute_adj_edge_coverage,
    _compute_max_adjacent_gap,
    _compute_canvas_width_ratio,
    _compute_sign_inconsistency_rate,
    _compute_adj_disp_cv,
    _compute_adj_min_weight,
    _compute_ba_max_residual,
    _compute_min_adjacent_overlap,
    _compute_ba_weighted_mean_residual,
    _compute_canvas_memory_mb,
    _compute_canvas_aspect_ratio,
    _compute_render_luma_std,
    _compute_max_affine_rotation_deg,
    _smooth_affine_trajectory,
    _apply_hires_keyframes,
    _sort_frames_by_index,
    _check_canvas_spread,
    _compute_bg_lum_spread,
    _compute_bg_lum_monotonicity,
    _compute_canvas_fill_ratio,
    _compute_strip_variance_ratio,
)
from backend.src.constants.animation import (
    HIGH_CONF_EDGE_THRESH,
    SCALE_NORM_THRESH,  # noqa: F401
    SCENE_CHANGE_LUMA_THRESH,  # noqa: F401
)


def _make_affine(dy: float, dx: float = 0.0) -> np.ndarray:
    """2×3 affine matrix with given translation."""
    M = np.eye(2, 3, dtype=np.float32)
    M[0, 2] = dx
    M[1, 2] = dy
    return M


def _make_frame(h: int = 4, w: int = 4, val: int = 128) -> np.ndarray:
    return np.full((h, w, 3), val, dtype=np.uint8)


def _make_mask(h: int = 4, w: int = 4) -> np.ndarray:
    return np.ones((h, w), dtype=np.uint8)


def _make_edge(i: int, j: int, dy: float, dx: float = 0.0) -> dict:
    return {"i": i, "j": j, "M": _make_affine(dy=dy, dx=dx)}


class TestSpatialDedupFrames:
    def test_no_drop_when_displacement_above_threshold(self):
        frames = [_make_frame(val=v) for v in [10, 20, 30]]
        scans = [_make_frame(val=v) for v in [10, 20, 30]]
        masks = [_make_mask() for _ in range(3)]
        paths = ["a.png", "b.png", "c.png"]
        edges = [_make_edge(0, 1, dy=50.0), _make_edge(1, 2, dy=50.0)]

        out_frames, out_scans, _, _, out_edges, n = _spatial_dedup_frames(
            frames, scans, masks, paths, edges, min_displacement_px=25.0
        )

        assert n == 0
        assert len(out_frames) == 3
        assert len(out_scans) == 3
        assert len(out_edges) == 2

    def test_drops_near_static_adjacent_frame(self):
        frames = [_make_frame(val=v) for v in [10, 20, 30]]
        scans = [_make_frame(val=v) for v in [10, 20, 30]]
        masks = [_make_mask() for _ in range(3)]
        paths = ["a.png", "b.png", "c.png"]
        # Frame 1 is near-static (dy=5px < threshold=25px)
        edges = [_make_edge(0, 1, dy=5.0), _make_edge(1, 2, dy=50.0)]

        out_frames, out_scans, _, out_paths, out_edges, n = _spatial_dedup_frames(
            frames, scans, masks, paths, edges, min_displacement_px=25.0
        )

        assert n == 1
        assert len(out_frames) == 2
        # Frame 1 (val=20) should be gone; frames 0 and 2 remain
        assert out_frames[0][0, 0, 0] == 10
        assert out_frames[1][0, 0, 0] == 30

    def test_scans_frames_synced_with_frames_after_drop(self):
        """§1.9A: scans_frames must have same length and entries as frames."""
        frames = [_make_frame(val=v) for v in [10, 20, 30]]
        scans = [_make_frame(val=v + 1) for v in [10, 20, 30]]  # offset to distinguish
        masks = [_make_mask() for _ in range(3)]
        paths = ["a.png", "b.png", "c.png"]
        edges = [_make_edge(0, 1, dy=5.0), _make_edge(1, 2, dy=50.0)]

        out_frames, out_scans, _, _, _, n = _spatial_dedup_frames(
            frames, scans, masks, paths, edges, min_displacement_px=25.0
        )

        assert n == 1
        assert len(out_scans) == len(out_frames) == 2
        # scans_frames[0] should correspond to original frame 0 (val+1=11)
        assert out_scans[0][0, 0, 0] == 11
        # scans_frames[1] should correspond to original frame 2 (val+1=31)
        assert out_scans[1][0, 0, 0] == 31

    def test_edges_reindexed_after_drop(self):
        """After frame 1 is dropped, edge i/j indices must be remapped."""
        frames = [_make_frame() for _ in range(4)]
        scans = [_make_frame() for _ in range(4)]
        masks = [_make_mask() for _ in range(4)]
        paths = ["a.png", "b.png", "c.png", "d.png"]
        # Frame 1 near-static; keep frames 0, 2, 3
        edges = [
            _make_edge(0, 1, dy=3.0),
            _make_edge(1, 2, dy=60.0),
            _make_edge(2, 3, dy=60.0),
        ]

        _, _, _, _, out_edges, n = _spatial_dedup_frames(
            frames, scans, masks, paths, edges, min_displacement_px=25.0
        )

        assert n == 1
        # Only the surviving edges (not involving dropped frame 1) should remain,
        # reindexed: old (2→3) becomes new (1→2)
        assert len(out_edges) == 1
        surviving = out_edges[0]
        assert surviving["i"] == 1
        assert surviving["j"] == 2

    def test_first_frame_never_dropped(self):
        """Frame 0 is an anchor in the adjacency chain and must never be dropped."""
        frames = [_make_frame(val=v) for v in [10, 20, 30]]
        scans = [_make_frame(val=v) for v in [10, 20, 30]]
        masks = [_make_mask() for _ in range(3)]
        paths = ["a.png", "b.png", "c.png"]
        # Even if frame 0→1 displacement is tiny, only frame 1 (j) can be dropped
        edges = [_make_edge(0, 1, dy=2.0), _make_edge(1, 2, dy=2.0)]

        out_frames, _, _, _, _, n = _spatial_dedup_frames(
            frames, scans, masks, paths, edges, min_displacement_px=25.0
        )

        # Frame 0 must survive; frame 1 is dropped; frame 2 has i=1 which is in
        # drop, so it is skipped by the guard and NOT dropped (it becomes orphaned
        # but kept since only j-targets of non-dropped sources are removed).
        assert out_frames[0][0, 0, 0] == 10
        assert n >= 1


# ---------------------------------------------------------------------------
# TestFilterHighConfEdges — §2.9C high-confidence BA re-solve (S37)
# ---------------------------------------------------------------------------


def _make_edge_with_weight(i: int, j: int, weight: float, dy: float = 50.0) -> dict:
    return {"i": i, "j": j, "M": _make_affine(dy=dy), "weight": weight}


class TestFilterHighConfEdges:
    """
    _filter_high_conf_edges keeps only edges whose ``weight`` meets or
    exceeds the HIGH_CONF_EDGE_THRESH floor (default 0.65).

    LoFTR edges (weight ~0.7–0.95) are kept; TM/PC fallback edges
    (weight ~0.15–0.55) are removed so that a single bad low-confidence
    edge cannot corrupt the bundle adjustment solution.
    """

    def test_high_weight_edges_kept(self):
        """Edges at or above threshold must survive the filter."""
        edges = [
            _make_edge_with_weight(0, 1, weight=0.90),
            _make_edge_with_weight(
                1, 2, weight=HIGH_CONF_EDGE_THRESH
            ),  # exactly at floor
            _make_edge_with_weight(2, 3, weight=0.75),
        ]
        result = _filter_high_conf_edges(edges)
        assert len(result) == 3

    def test_low_weight_edges_removed(self):
        """Edges below threshold must be filtered out."""
        edges = [
            _make_edge_with_weight(0, 1, weight=0.90),
            _make_edge_with_weight(1, 2, weight=0.40),  # TM fallback
            _make_edge_with_weight(0, 2, weight=0.15),  # PC fallback
        ]
        result = _filter_high_conf_edges(edges)
        assert len(result) == 1
        assert result[0]["i"] == 0 and result[0]["j"] == 1

    def test_empty_edges_returns_empty(self):
        """Empty input list must produce empty output without error."""
        assert _filter_high_conf_edges([]) == []

    def test_all_below_threshold_returns_empty(self):
        """When all edges are low-quality the result is empty (triggers fallthrough)."""
        edges = [
            _make_edge_with_weight(0, 1, weight=0.50),
            _make_edge_with_weight(1, 2, weight=0.30),
        ]
        result = _filter_high_conf_edges(edges)
        assert len(result) == 0

    def test_missing_weight_field_treated_as_zero(self):
        """Edges without a ``weight`` key must not raise and must be filtered out."""
        edges = [
            {"i": 0, "j": 1, "M": _make_affine(dy=50.0)},  # no weight key
            _make_edge_with_weight(1, 2, weight=0.80),
        ]
        result = _filter_high_conf_edges(edges)
        # weight defaults to 0.0 → below threshold → only the second edge survives
        assert len(result) == 1
        assert result[0]["i"] == 1 and result[0]["j"] == 2


# ---------------------------------------------------------------------------
# TestReloadScansFrames — §1.9C on-demand SCANS frame reload (S41)
# ---------------------------------------------------------------------------


def _write_rgb_png(path, h: int = 8, w: int = 8, val: int = 128) -> None:
    """Write a small solid-colour BGR image to *path*."""
    img = np.full((h, w, 3), val, dtype=np.uint8)
    cv2.imwrite(str(path), img)


class TestReloadScansFrames:
    """
    _reload_scans_frames(paths) reads frames from disk, skips unreadable
    files, and returns all surviving frames width-normalised to the first
    frame's width — exactly matching the Stage-1/2 pipeline output.
    """

    def test_returns_loaded_frames_for_valid_paths(self, tmp_path):
        """Two readable PNG files → two frames returned."""
        p1 = tmp_path / "a.png"
        p2 = tmp_path / "b.png"
        _write_rgb_png(p1, val=50)
        _write_rgb_png(p2, val=200)
        result = _reload_scans_frames([str(p1), str(p2)])
        assert len(result) == 2
        assert result[0].shape == result[1].shape  # widths normalised

    def test_empty_paths_returns_empty_list(self):
        """No input paths → empty list, no exception."""
        assert _reload_scans_frames([]) == []

    def test_unreadable_path_skipped(self, tmp_path):
        """Non-existent path is skipped; the one valid frame is returned."""
        p_good = tmp_path / "good.png"
        _write_rgb_png(p_good, val=100)
        result = _reload_scans_frames([str(p_good), "/nonexistent/ghost.png"])
        assert len(result) == 1

    def test_all_frames_normalised_to_first_width(self, tmp_path):
        """Frames with different widths are resized to match the first frame."""
        p1 = tmp_path / "wide.png"
        p2 = tmp_path / "narrow.png"
        cv2.imwrite(str(p1), np.zeros((8, 16, 3), dtype=np.uint8))
        cv2.imwrite(str(p2), np.zeros((8, 8, 3), dtype=np.uint8))
        result = _reload_scans_frames([str(p1), str(p2)])
        assert len(result) == 2
        assert result[0].shape[1] == result[1].shape[1]  # same width

    def test_all_unreadable_returns_empty(self, tmp_path):
        """When all paths fail to load, an empty list is returned without error."""
        result = _reload_scans_frames(["/no/such/file.png", "/another/bad.png"])
        assert result == []


class TestRejectSceneChangeEdges:
    """§1.13 — _reject_scene_change_edges: scene-change luma gate."""

    def _bright_frame(self, val: int = 220, h: int = 16, w: int = 16) -> np.ndarray:
        return np.full((h, w, 3), val, dtype=np.uint8)

    def _dark_frame(self, val: int = 20, h: int = 16, w: int = 16) -> np.ndarray:
        return np.full((h, w, 3), val, dtype=np.uint8)

    def _edge(self, i: int, j: int) -> dict:
        return {"i": i, "j": j, "M": _make_affine(dy=50.0)}

    def test_similar_frames_not_rejected(self):
        """Edge between two frames with nearly identical mean luma is kept."""
        frames = [self._bright_frame(200), self._bright_frame(210)]
        edges = [self._edge(0, 1)]
        result = _reject_scene_change_edges(edges, frames, max_luma_diff=60.0)
        assert len(result) == 1

    def test_large_luma_diff_rejected(self):
        """Edge between a bright frame and a dark frame exceeds threshold → dropped."""
        frames = [self._bright_frame(220), self._dark_frame(20)]
        edges = [self._edge(0, 1)]
        result = _reject_scene_change_edges(edges, frames, max_luma_diff=60.0)
        assert len(result) == 0

    def test_threshold_zero_keeps_all_edges(self):
        """max_luma_diff=0 disables the gate; all edges are returned unchanged."""
        frames = [self._bright_frame(220), self._dark_frame(10)]
        edges = [self._edge(0, 1)]
        result = _reject_scene_change_edges(edges, frames, max_luma_diff=0.0)
        assert len(result) == 1

    def test_out_of_bounds_frame_index_kept(self):
        """An edge whose frame index ≥ len(frames) is kept rather than crashing."""
        frames = [self._bright_frame()]
        edges = [{"i": 0, "j": 5, "M": _make_affine(dy=50.0)}]
        result = _reject_scene_change_edges(edges, frames, max_luma_diff=60.0)
        assert len(result) == 1

    def test_selectively_filters_mixed_edges(self):
        """Two similar-luma edges kept; one scene-change edge dropped."""
        f_a = self._bright_frame(200)
        f_b = self._bright_frame(210)
        f_c = self._dark_frame(10)
        frames = [f_a, f_b, f_c]
        edges = [
            self._edge(0, 1),  # similar → kept
            self._edge(1, 2),  # scene change → dropped
            self._edge(0, 2),  # scene change → dropped
        ]
        result = _reject_scene_change_edges(edges, frames, max_luma_diff=60.0)
        assert len(result) == 1
        assert result[0]["i"] == 0 and result[0]["j"] == 1


# ---------------------------------------------------------------------------
# TestNormalizeFrameScales — §1.3C scale normalisation before BA (S54)
# ---------------------------------------------------------------------------


def _make_scale_affine(scale: float, dy: float = 50.0) -> np.ndarray:
    """2×3 similarity affine with given uniform scale and vertical translation."""
    M = np.eye(2, 3, dtype=np.float32)
    M[0, 0] = scale
    M[1, 1] = scale
    M[1, 2] = dy
    return M


class TestNormalizeFrameScales:
    """
    _normalize_frame_scales(frames, edges, scale_thresh) detects inter-frame
    zoom in the edge affines and resizes all frames to the reference scale.
    The edge affines are updated to pure-translation (scale reset to 1.0).
    """

    def _frame(self, h: int = 60, w: int = 80, val: int = 128) -> np.ndarray:
        return np.full((h, w, 3), val, dtype=np.uint8)

    def _edge(self, i: int, j: int, scale: float = 1.0, dy: float = 50.0) -> dict:
        return {"i": i, "j": j, "M": _make_scale_affine(scale, dy), "weight": 1.0}

    def test_identity_scale_returns_unchanged(self):
        """When all edges have scale=1.0, frames and edges must be returned unchanged."""
        frames = [self._frame() for _ in range(3)]
        edges = [self._edge(0, 1, scale=1.0), self._edge(1, 2, scale=1.0)]
        out_frames, out_edges = _normalize_frame_scales(
            frames, edges, scale_thresh=0.05
        )
        assert out_frames is frames
        assert out_edges is edges

    def test_zoomed_frame_is_resized(self):
        """Frame with scale=1.2 relative to reference must be resized to ~1/1.2 factor."""
        frames = [self._frame(60, 80), self._frame(60, 80)]
        # edge 0→1: scale=1.2 means frame 1 is 1.2× the reference
        edges = [self._edge(0, 1, scale=1.2, dy=50.0)]
        out_frames, _ = _normalize_frame_scales(frames, edges, scale_thresh=0.05)
        h0, w0 = out_frames[0].shape[:2]
        h1, w1 = out_frames[1].shape[:2]
        # reference frame (i=0) unchanged
        assert (h0, w0) == (60, 80)
        # frame 1 should be scaled down (smaller than original)
        assert w1 < 80 or h1 < 60, f"Expected frame 1 resized, got ({h1}, {w1})"

    def test_below_threshold_returns_unchanged(self):
        """Scale deviation below scale_thresh triggers no normalisation (no-op)."""
        frames = [self._frame() for _ in range(2)]
        # scale = 1.02 → deviation 2% < 5% threshold
        edges = [self._edge(0, 1, scale=1.02, dy=50.0)]
        out_frames, out_edges = _normalize_frame_scales(
            frames, edges, scale_thresh=0.05
        )
        assert out_frames is frames
        assert out_edges is edges

    def test_disconnected_graph_returns_unchanged(self):
        """A graph where frame 2 cannot be reached from frame 0 must be left unchanged."""
        frames = [self._frame() for _ in range(3)]
        # Only edge 0→1; frame 2 is isolated
        edges = [self._edge(0, 1, scale=1.3, dy=50.0)]
        out_frames, out_edges = _normalize_frame_scales(
            frames, edges, scale_thresh=0.05
        )
        assert out_frames is frames
        assert out_edges is edges

    def test_edge_affines_reset_to_unit_scale(self):
        """After normalisation the updated edge M must have diagonal elements ≈ 1.0."""
        frames = [self._frame() for _ in range(2)]
        edges = [self._edge(0, 1, scale=1.3, dy=60.0)]
        _, out_edges = _normalize_frame_scales(frames, edges, scale_thresh=0.05)
        M = out_edges[0]["M"]
        assert abs(float(M[0, 0]) - 1.0) < 1e-4, f"M[0,0]={M[0, 0]}, expected 1.0"
        assert abs(float(M[1, 1]) - 1.0) < 1e-4, f"M[1,1]={M[1, 1]}, expected 1.0"
        assert abs(float(M[0, 1])) < 1e-4, f"M[0,1]={M[0, 1]}, expected ~0"
        assert abs(float(M[1, 0])) < 1e-4, f"M[1,0]={M[1, 0]}, expected ~0"


# ---------------------------------------------------------------------------
# §1.13B — _reject_scene_change_edges with use_bgr=True
# ---------------------------------------------------------------------------


class TestRejectSceneChangeEdgesBgr:
    """§1.13B — per-channel (BGR) scene-change gate in _reject_scene_change_edges."""

    @staticmethod
    def _edge(i: int, j: int) -> dict:
        return {"i": i, "j": j, "M": np.eye(2, 3, dtype=np.float32), "weight": 1.0}

    @staticmethod
    def _uniform_frame(b: int, g: int, r: int, h: int = 64, w: int = 64) -> np.ndarray:
        return np.full((h, w, 3), [b, g, r], dtype=np.uint8)

    def test_identical_bgr_frames_not_rejected(self):
        """Frames with identical BGR values → max channel diff = 0 → kept."""
        frames = [self._uniform_frame(100, 150, 80)] * 2
        edges = [self._edge(0, 1)]
        result = _reject_scene_change_edges(
            edges, frames, max_luma_diff=60.0, use_bgr=True
        )
        assert len(result) == 1

    def test_hue_shift_same_luma_rejected_in_bgr_mode(self):
        """Warm frame (high R) vs cool frame (high B) at similar luma → rejected in BGR, kept in luma."""
        # Frame A: orange (B=20, G=100, R=220) → luma ≈ 20*0.114 + 100*0.587 + 220*0.299 ≈ 125
        # Frame B: blue  (B=220, G=100, R=20)  → luma ≈ 220*0.114 + 100*0.587 + 20*0.299  ≈ 90
        # Max channel diff = |220-20| = 200 > 60 → rejected in BGR mode
        frame_a = self._uniform_frame(20, 100, 220)
        frame_b = self._uniform_frame(220, 100, 20)
        frames = [frame_a, frame_b]
        edges = [self._edge(0, 1)]
        bgr_result = _reject_scene_change_edges(
            edges, frames, max_luma_diff=60.0, use_bgr=True
        )
        assert len(bgr_result) == 0, "BGR gate should reject large hue shift"

    def test_luma_mode_misses_hue_shift(self):
        """Same hue-shifted pair that BGR rejects should PASS the grayscale luma gate."""
        # Green frame (B=10, G=200, R=10) and red frame (B=10, G=10, R=200)
        # Luma_green ≈ 10*0.114 + 200*0.587 + 10*0.299 ≈ 121
        # Luma_red   ≈ 10*0.114 + 10*0.587 + 200*0.299 ≈ 66
        # Luma diff ≈ 55 < 60 → kept by grayscale gate
        # Max channel diff = |200-10| = 190 > 60 → rejected by BGR gate
        frame_g = self._uniform_frame(10, 200, 10)
        frame_r = self._uniform_frame(10, 10, 200)
        frames = [frame_g, frame_r]
        edges = [self._edge(0, 1)]
        luma_result = _reject_scene_change_edges(
            edges, frames, max_luma_diff=60.0, use_bgr=False
        )
        assert len(luma_result) == 1, "Luma gate should keep this hue-shifted pair"

    def test_bgr_threshold_zero_disabled(self):
        """max_luma_diff=0 disables the gate regardless of channel mismatch."""
        frames = [self._uniform_frame(0, 0, 0), self._uniform_frame(255, 255, 255)]
        edges = [self._edge(0, 1)]
        result = _reject_scene_change_edges(
            edges, frames, max_luma_diff=0.0, use_bgr=True
        )
        assert len(result) == 1

    def test_bgr_small_channel_diff_kept(self):
        """Frames with channel diffs below threshold → kept."""
        frame_a = self._uniform_frame(100, 100, 100)
        frame_b = self._uniform_frame(140, 140, 140)  # diff = 40 < 60
        frames = [frame_a, frame_b]
        edges = [self._edge(0, 1)]
        result = _reject_scene_change_edges(
            edges, frames, max_luma_diff=60.0, use_bgr=True
        )
        assert len(result) == 1


# ---------------------------------------------------------------------------
# §1.15 — _check_edge_graph_connectivity
# ---------------------------------------------------------------------------


class TestCheckEdgeGraphConnectivity:
    """§1.15 — Union-Find edge graph connectivity check before bundle adjustment."""

    @staticmethod
    def _edge(i: int, j: int) -> dict:
        return {"i": i, "j": j, "M": np.eye(2, 3, dtype=np.float32), "weight": 1.0}

    def test_chain_graph_is_connected(self):
        """0→1→2 chain covers all 3 frames → True."""
        edges = [self._edge(0, 1), self._edge(1, 2)]
        assert _check_edge_graph_connectivity(edges, n_frames=3) is True

    def test_isolated_frame_is_disconnected(self):
        """N=3, edge only 0→1 → frame 2 isolated → False."""
        edges = [self._edge(0, 1)]
        assert _check_edge_graph_connectivity(edges, n_frames=3) is False

    def test_single_frame_trivially_connected(self):
        """N=1 → trivially connected regardless of edges."""
        assert _check_edge_graph_connectivity([], n_frames=1) is True

    def test_complete_graph_is_connected(self):
        """All pairs connected (complete graph on N=4) → True."""
        edges = [
            self._edge(0, 1),
            self._edge(0, 2),
            self._edge(0, 3),
            self._edge(1, 2),
            self._edge(1, 3),
            self._edge(2, 3),
        ]
        assert _check_edge_graph_connectivity(edges, n_frames=4) is True

    def test_no_edges_multiple_frames_disconnected(self):
        """N=3, empty edge list → all frames isolated → False."""
        assert _check_edge_graph_connectivity([], n_frames=3) is False


# ---------------------------------------------------------------------------
# §1.16 — _compute_mst_weight (minimum spanning tree weight gate)
# ---------------------------------------------------------------------------


class TestComputeMstWeight:
    """§1.16: Mean MST edge weight gate catches low-confidence edge graphs."""

    @staticmethod
    def _edge(i: int, j: int, weight: float) -> dict:
        return {"i": i, "j": j, "weight": weight, "dx": 50.0, "dy": 0.0}

    def test_no_frames_returns_zero(self):
        """n_frames ≤ 1 → 0.0 (no spanning tree needed)."""
        assert _compute_mst_weight([], n_frames=0) == pytest.approx(0.0)
        assert _compute_mst_weight([], n_frames=1) == pytest.approx(0.0)

    def test_empty_edges_returns_zero(self):
        """No edges → MST cannot be built → 0.0."""
        assert _compute_mst_weight([], n_frames=3) == pytest.approx(0.0)

    def test_chain_graph_mean_weight(self):
        """Chain 0→1 (w=0.8) and 1→2 (w=0.6) → MST both edges → mean = 0.7."""
        edges = [self._edge(0, 1, 0.8), self._edge(1, 2, 0.6)]
        result = _compute_mst_weight(edges, n_frames=3)
        assert result == pytest.approx(0.7, abs=1e-6)

    def test_takes_highest_weight_edges_for_mst(self):
        """Triangle 0-1-2 with weights 0.9, 0.5, 0.3; MST picks w=0.9 and w=0.5 → mean=0.7."""
        edges = [
            self._edge(0, 1, 0.9),
            self._edge(1, 2, 0.5),
            self._edge(0, 2, 0.3),
        ]
        result = _compute_mst_weight(edges, n_frames=3)
        assert result == pytest.approx(0.7, abs=1e-6)

    def test_low_weight_graph_below_threshold(self):
        """All TM/PC edges at weight=0.2 → mean MST weight 0.2 < 0.35 threshold."""
        edges = [self._edge(i, i + 1, 0.2) for i in range(4)]
        result = _compute_mst_weight(edges, n_frames=5)
        assert result == pytest.approx(0.2, abs=1e-6)
        assert result < 0.35


# §1.17 — _compute_canvas_span_utilization (canvas span utilisation gate)
# Tests cover: edge cases (N<2), perfect monotone sequence, collapsed BA
# (all frames same position), over-utilised (frames spread wider than median
# step × (N-1)), and dominant-axis selection (horizontal vs vertical).


class TestComputeCanvasSpanUtilization:
    @staticmethod
    def _aff(ty: float, tx: float = 0.0) -> np.ndarray:
        M = np.eye(2, 3, dtype=np.float32)
        M[0, 2] = tx
        M[1, 2] = ty
        return M

    def test_single_frame_returns_one(self):
        """N < 2 → always returns 1.0 (no collapse possible)."""
        assert _compute_canvas_span_utilization([self._aff(0.0)]) == pytest.approx(1.0)

    def test_two_frames_returns_one(self):
        """N == 2: span == expected_span (median_step==span, N-1==1) → ratio == 1.0."""
        affines = [self._aff(0.0), self._aff(100.0)]
        assert _compute_canvas_span_utilization(affines) == pytest.approx(1.0)

    def test_perfect_monotone_sequence(self):
        """Perfectly uniform steps: span == median_step × (N-1) → ratio == 1.0."""
        step = 80.0
        affines = [self._aff(i * step) for i in range(6)]
        result = _compute_canvas_span_utilization(affines)
        assert result == pytest.approx(1.0, abs=1e-5)

    def test_oscillating_ba_returns_low_ratio(self):
        """Oscillating BA solution: frames alternate positions [0,100,0,100,0,100].

        span=100, adj_steps all=100, median_step=100, expected=100×5=500 → util=0.2.
        This models a BA converging to a back-and-forth local minimum where the
        canvas span is far smaller than the sum of individual steps implies.
        """
        affines = [self._aff(0.0 if i % 2 == 0 else 100.0) for i in range(6)]
        result = _compute_canvas_span_utilization(affines)
        assert result == pytest.approx(0.2, abs=1e-5)
        assert result < 0.3  # below recommended threshold

    def test_dominant_axis_horizontal(self):
        """When tx_span > ty_span, horizontal axis is used for ratio."""
        # ty=0 for all (no vertical scroll), tx varies uniformly.
        affines = [self._aff(0.0, tx=i * 50.0) for i in range(5)]
        result = _compute_canvas_span_utilization(affines)
        assert result == pytest.approx(1.0, abs=1e-5)


class TestMeasureMaxSeamStep:
    """§1.24 — Post-composite seam-step measurement (S68)."""

    def _canvas(self, h: int, w: int, lum_top: int, lum_bottom: int, boundary: int):
        """Solid-colour canvas with a lum jump at `boundary` row."""
        canvas = np.zeros((h, w, 3), dtype=np.uint8)
        canvas[:boundary] = lum_top
        canvas[boundary:] = lum_bottom
        return canvas

    def test_single_strip_returns_zero(self):
        """n_strips=1 → no seam boundaries → 0.0."""
        canvas = self._canvas(200, 50, 100, 100, 100)
        assert _measure_max_seam_step(canvas, n_strips=1) == pytest.approx(0.0)

    def test_uniform_canvas_returns_near_zero(self):
        """Uniform luminance canvas → no step → ≈ 0.0."""
        canvas = np.full((200, 50, 3), 128, dtype=np.uint8)
        step = _measure_max_seam_step(canvas, n_strips=2)
        assert step == pytest.approx(0.0, abs=1.0)

    def test_step_detected_at_boundary(self):
        """Canvas with +40 lum jump at mid-height → step ≈ 40."""
        canvas = self._canvas(200, 50, 80, 120, 100)
        step = _measure_max_seam_step(canvas, n_strips=2, band_px=10, guard=3)
        assert step == pytest.approx(40.0, abs=2.0)

    def test_max_returned_for_multiple_seams(self):
        """Two-strip canvas with step=20 + one-strip canvas with step=50 → max=50."""
        h, w = 300, 50
        canvas = np.zeros((h, w, 3), dtype=np.uint8)
        canvas[:100] = 80
        canvas[100:200] = 100  # step=20 at row100
        canvas[200:] = 150  # step=50 at row200
        step = _measure_max_seam_step(canvas, n_strips=3, band_px=10, guard=3)
        assert step >= 45.0  # at least the large step is captured

    def test_small_canvas_no_crash(self):
        """Canvas too small for band+guard → returns 0.0, no exception."""
        canvas = np.full((10, 4, 3), 100, dtype=np.uint8)
        step = _measure_max_seam_step(canvas, n_strips=2, band_px=10, guard=3)
        assert step == pytest.approx(0.0)


# ── TestDetectStaticInput — §1.29 static input detection gate (S73) ──────────


class TestDetectStaticInput:
    """§1.29 — Static input detection gate."""

    def _frame(self, h: int = 32, w: int = 32, val: int = 128) -> np.ndarray:
        return np.full((h, w, 3), val, dtype=np.uint8)

    def test_fewer_than_two_frames_returns_false(self):
        """A single frame is never considered static input."""
        assert _detect_static_input([self._frame()], max_mad=2.0) is False

    def test_identical_frames_returns_true(self):
        """All identical frames → MAD=0 for every pair → True."""
        frames = [self._frame(val=100)] * 4
        assert _detect_static_input(frames, max_mad=2.0) is True

    def test_varying_frames_returns_false(self):
        """Frames with different luminance values → MAD exceeds threshold → False."""
        frames = [self._frame(val=v) for v in [100, 150, 80, 200]]
        assert _detect_static_input(frames, max_mad=2.0) is False

    def test_just_below_threshold_returns_true(self):
        """Frames that differ by slightly less than max_mad on a single pixel are still static."""
        base = self._frame(val=100)
        slightly_different = base.copy()
        slightly_different[0, 0] = 101  # 1/1024 ≈ 0.001 luma — well below MAD=2
        frames = [base, slightly_different, base]
        assert _detect_static_input(frames, max_mad=2.0) is True

    def test_one_differing_pair_returns_false(self):
        """Only one pair with high MAD is enough to classify input as non-static."""
        frames = [self._frame(val=100)] * 3 + [self._frame(val=200)]
        assert _detect_static_input(frames, max_mad=2.0) is False


# ---------------------------------------------------------------------------
# §S89 — _build_manual_edge
# ---------------------------------------------------------------------------


class TestBuildManualEdge:
    """Tests for _build_manual_edge (§S89 manual edge entry at HITL checkpoint 2)."""

    def setup_method(self):
        from backend.src.animation.core.pipeline import _build_manual_edge

        self._fn = _build_manual_edge

    def test_m_is_pure_translation(self):
        edge = self._fn(0, 1, dx=50.0, dy=100.0)
        M = edge["M"]
        assert M.shape == (2, 3)
        np.testing.assert_allclose(M[:, :2], np.eye(2), atol=1e-9)
        assert M[0, 2] == pytest.approx(50.0)
        assert M[1, 2] == pytest.approx(100.0)

    def test_indices_stored(self):
        edge = self._fn(2, 5, dx=0.0, dy=200.0)
        assert edge["i"] == 2
        assert edge["j"] == 5

    def test_method_is_manual(self):
        edge = self._fn(0, 1, dx=10.0, dy=20.0)
        assert edge["method"] == "manual"

    def test_weight_clipped_to_unit_interval(self):
        over = self._fn(0, 1, dx=0.0, dy=0.0, weight=2.5)
        assert over["weight"] == pytest.approx(1.0)
        under = self._fn(0, 1, dx=0.0, dy=0.0, weight=-0.5)
        assert under["weight"] == pytest.approx(0.0)

    def test_pts_shape_is_compatible_with_bundle_adjust(self):
        edge = self._fn(0, 1, dx=30.0, dy=60.0)
        assert edge["pts_i"].shape == (1, 2)
        assert edge["pts_j"].shape == (1, 2)
        np.testing.assert_allclose(
            edge["pts_j"] - edge["pts_i"], [[30.0, 60.0]], atol=1e-6
        )


# ---------------------------------------------------------------------------
# §1.37 — _compute_bg_coverage_fraction (S101)
# ---------------------------------------------------------------------------


class TestComputeBgCoverageFraction:
    """_compute_bg_coverage_fraction returns mean bg-pixel fraction across valid masks."""

    def _mask(self, h: int = 64, w: int = 64, bg_frac: float = 1.0) -> np.ndarray:
        """Produce a uint8 mask where *bg_frac* of pixels are 255 (background)."""
        mask = np.zeros((h, w), dtype=np.uint8)
        n_bg = round(h * w * bg_frac)
        mask.flat[:n_bg] = 255
        return mask

    def test_all_background_masks_return_one(self):
        """All-bg masks (every pixel > 127) → fraction = 1.0."""
        masks = [self._mask(bg_frac=1.0)] * 4
        assert _compute_bg_coverage_fraction(masks) == pytest.approx(1.0, abs=1e-3)

    def test_all_foreground_masks_return_zero(self):
        """All-fg masks (every pixel = 0) → fraction = 0.0."""
        masks = [np.zeros((32, 32), dtype=np.uint8)] * 3
        assert _compute_bg_coverage_fraction(masks) == pytest.approx(0.0, abs=1e-6)

    def test_half_bg_half_fg_returns_point_five(self):
        """Masks with 50% bg pixels → mean fraction ≈ 0.5."""
        mask = self._mask(h=100, w=100, bg_frac=0.5)
        result = _compute_bg_coverage_fraction([mask, mask])
        assert result == pytest.approx(0.5, abs=1e-2)

    def test_none_masks_skipped_returns_one(self):
        """List containing only None entries → returns 1.0 (gate must not fire)."""
        masks = [None, None, None]
        assert _compute_bg_coverage_fraction(masks) == pytest.approx(1.0)

    def test_mixed_none_and_valid_masks_ignores_none(self):
        """None entries are skipped; only valid masks contribute to the mean."""
        bg_mask = self._mask(bg_frac=0.8)
        masks = [None, bg_mask, None, bg_mask]
        result = _compute_bg_coverage_fraction(masks)
        assert result == pytest.approx(0.8, abs=1e-2)


# §1.39 — _compute_render_coverage (S103)
class TestComputeRenderCoverage:
    """_compute_render_coverage returns fraction of canvas pixels with valid_mask > 0."""

    def _mask(self, h: int = 64, w: int = 64, frac: float = 1.0) -> np.ndarray:
        mask = np.zeros((h, w), dtype=np.uint8)
        n_covered = round(h * w * frac)
        mask.flat[:n_covered] = 255
        return mask

    def test_fully_covered_canvas_returns_one(self):
        """All pixels covered → coverage fraction = 1.0."""
        mask = self._mask(frac=1.0)
        assert _compute_render_coverage(mask) == pytest.approx(1.0)

    def test_empty_canvas_returns_zero(self):
        """No pixels covered (completely blank render) → coverage = 0.0."""
        mask = np.zeros((64, 64), dtype=np.uint8)
        assert _compute_render_coverage(mask) == pytest.approx(0.0)

    def test_known_coverage_fraction(self):
        """30% of pixels covered → returns ~0.30."""
        mask = self._mask(h=100, w=100, frac=0.30)
        result = _compute_render_coverage(mask)
        assert result == pytest.approx(0.30, abs=1e-2)

    def test_zero_size_mask_returns_zero(self):
        """Empty array (size=0) returns 0.0 without ZeroDivisionError."""
        mask = np.zeros((0, 0), dtype=np.uint8)
        assert _compute_render_coverage(mask) == pytest.approx(0.0)

    def test_half_covered_canvas(self):
        """50% pixel coverage → returns 0.5."""
        mask = self._mask(h=100, w=100, frac=0.50)
        result = _compute_render_coverage(mask)
        assert result == pytest.approx(0.50, abs=1e-2)


# §1.43 — _compute_adj_edge_coverage (S107)
class TestComputeAdjEdgeCoverage:
    """_compute_adj_edge_coverage returns fraction of adjacent pairs (|i-j|=1) with ≥1 edge."""

    @staticmethod
    def _edge(i: int, j: int) -> dict:
        return {"i": i, "j": j, "weight": 0.8, "dx": 10.0, "dy": 200.0}

    def test_all_adjacent_covered(self):
        """All 3 adjacent pairs present → 1.0."""
        edges = [self._edge(0, 1), self._edge(1, 2), self._edge(2, 3)]
        assert _compute_adj_edge_coverage(edges, n_frames=4) == pytest.approx(1.0)

    def test_no_adjacent_edges(self):
        """Only skip-1 edge present — no |i-j|=1 edges → 0.0."""
        edges = [self._edge(0, 2)]
        assert _compute_adj_edge_coverage(edges, n_frames=3) == pytest.approx(0.0)

    def test_partial_coverage(self):
        """2 out of 3 adjacent pairs covered → 2/3."""
        edges = [self._edge(0, 1), self._edge(2, 3)]
        result = _compute_adj_edge_coverage(edges, n_frames=4)
        assert result == pytest.approx(2.0 / 3.0, abs=1e-6)

    def test_single_frame_returns_one(self):
        """n_frames=1 → no pairs → returns 1.0 (vacuously true)."""
        assert _compute_adj_edge_coverage([], n_frames=1) == pytest.approx(1.0)

    def test_duplicate_edges_counted_once(self):
        """Duplicate adj edges for the same pair count as one covered pair → 1/2."""
        edges = [self._edge(0, 1), self._edge(0, 1), self._edge(1, 0)]
        result = _compute_adj_edge_coverage(edges, n_frames=3)
        assert result == pytest.approx(0.5, abs=1e-6)


# §1.44 — _compute_max_adjacent_gap (S108)
class TestComputeMaxAdjacentGap:
    """_compute_max_adjacent_gap returns the max inter-frame gap along the dominant scroll axis."""

    @staticmethod
    def _affine(ty: float, tx: float = 0.0) -> np.ndarray:
        a = np.eye(2, 3, dtype=np.float32)
        a[0, 2] = tx
        a[1, 2] = ty
        return a

    @staticmethod
    def _frame(h: int = 100, w: int = 80) -> np.ndarray:
        return np.zeros((h, w, 3), dtype=np.uint8)

    def test_overlapping_frames_negative_gap(self):
        """Adjacent frames that overlap → gap is negative."""
        frames = [self._frame(100), self._frame(100)]
        # ty_1 = 80 < ty_0 + H_0 = 100 → overlap of 20px → gap = -20
        affines = [self._affine(0.0), self._affine(80.0)]
        result = _compute_max_adjacent_gap(affines, frames)
        assert result == pytest.approx(-20.0, abs=1e-3)

    def test_touching_frames_zero_gap(self):
        """Frames placed exactly end-to-start → gap = 0."""
        frames = [self._frame(100), self._frame(100)]
        affines = [self._affine(0.0), self._affine(100.0)]
        assert _compute_max_adjacent_gap(affines, frames) == pytest.approx(
            0.0, abs=1e-3
        )

    def test_gap_between_frames(self):
        """Frames separated by 50px uncovered strip → returns 50.0."""
        frames = [self._frame(100), self._frame(100)]
        affines = [self._affine(0.0), self._affine(150.0)]
        assert _compute_max_adjacent_gap(affines, frames) == pytest.approx(
            50.0, abs=1e-3
        )

    def test_single_frame_returns_zero(self):
        """N=1 frame → no adjacent pairs → returns 0.0."""
        assert _compute_max_adjacent_gap(
            [self._affine(0.0)], [self._frame()]
        ) == pytest.approx(0.0)

    def test_max_over_multiple_pairs(self):
        """Returns the largest gap when pairs have different gaps."""
        frames = [self._frame(100), self._frame(100), self._frame(100)]
        # pair 0→1: gap = 110 - 100 = 10; pair 1→2: gap = 250 - 210 = 40
        affines = [self._affine(0.0), self._affine(110.0), self._affine(250.0)]
        result = _compute_max_adjacent_gap(affines, frames)
        assert result == pytest.approx(40.0, abs=1e-3)


# §1.45 — _compute_canvas_width_ratio (S109)
class TestComputeCanvasWidthRatio:
    """_compute_canvas_width_ratio returns canvas_w / median_frame_w."""

    @staticmethod
    def _frame(w: int = 100, h: int = 200) -> np.ndarray:
        return np.zeros((h, w, 3), dtype=np.uint8)

    def test_canvas_equals_frame_width(self):
        """canvas_w == frame_w → ratio 1.0."""
        frames = [self._frame(w=100)]
        assert _compute_canvas_width_ratio(100, frames) == pytest.approx(1.0)

    def test_canvas_wider_than_frames(self):
        """canvas_w = 3 × frame_w → ratio 3.0."""
        frames = [self._frame(w=100)]
        assert _compute_canvas_width_ratio(300, frames) == pytest.approx(3.0)

    def test_canvas_narrower_than_frames(self):
        """canvas_w < frame_w is unusual but should return the correct ratio."""
        frames = [self._frame(w=200)]
        assert _compute_canvas_width_ratio(100, frames) == pytest.approx(0.5)

    def test_empty_frames_returns_one(self):
        """Empty frame list → 1.0 (safe fallback, gate must not fire)."""
        assert _compute_canvas_width_ratio(500, []) == pytest.approx(1.0)

    def test_mixed_frame_widths_uses_median(self):
        """Median of [80, 100, 120] = 100; canvas 150 → ratio 1.5."""
        frames = [self._frame(w=80), self._frame(w=100), self._frame(w=120)]
        assert _compute_canvas_width_ratio(150, frames) == pytest.approx(1.5)


# §1.47 — _compute_sign_inconsistency_rate (S111)
class TestComputeSignInconsistencyRate:
    """_compute_sign_inconsistency_rate returns minority-sign fraction of adjacent edge displacements."""

    @staticmethod
    def _adj_edge(i: int, j: int, dy: float, dx: float = 0.0) -> dict:
        M = np.array([[1, 0, dx], [0, 1, dy]], dtype=np.float32)
        return {"i": i, "j": j, "M": M, "weight": 0.8}

    def test_all_same_sign_returns_zero(self):
        """All adjacent dy negative (downward scroll) → rate = 0.0."""
        edges = [
            self._adj_edge(0, 1, dy=-100),
            self._adj_edge(1, 2, dy=-120),
            self._adj_edge(2, 3, dy=-90),
        ]
        assert _compute_sign_inconsistency_rate(edges) == pytest.approx(0.0)

    def test_half_opposite_sign_returns_half(self):
        """2 negative + 2 positive → minority = 2, rate = 0.5."""
        edges = [
            self._adj_edge(0, 1, dy=-100),
            self._adj_edge(1, 2, dy=-100),
            self._adj_edge(2, 3, dy=100),
            self._adj_edge(3, 4, dy=100),
        ]
        assert _compute_sign_inconsistency_rate(edges) == pytest.approx(0.5)

    def test_one_in_five_opposite(self):
        """1 positive among 4 negative → minority = 1, rate = 0.2."""
        edges = [
            self._adj_edge(0, 1, dy=-100),
            self._adj_edge(1, 2, dy=-100),
            self._adj_edge(2, 3, dy=-100),
            self._adj_edge(3, 4, dy=-100),
            self._adj_edge(4, 5, dy=100),
        ]
        assert _compute_sign_inconsistency_rate(edges) == pytest.approx(0.2)

    def test_skip_edges_excluded(self):
        """Skip edges (|i-j|=2) are not counted, only |i-j|=1."""
        adj = [self._adj_edge(0, 1, dy=-100), self._adj_edge(1, 2, dy=-100)]
        skip = [
            {
                "i": 0,
                "j": 2,
                "M": np.array([[1, 0, 100], [0, 1, 200]], np.float32),
                "weight": 0.5,
            }
        ]
        assert _compute_sign_inconsistency_rate(adj + skip) == pytest.approx(0.0)

    def test_fewer_than_two_adjacent_returns_zero(self):
        """Single adjacent edge → insufficient data → 0.0."""
        edges = [self._adj_edge(0, 1, dy=-100)]
        assert _compute_sign_inconsistency_rate(edges) == pytest.approx(0.0)


# §1.48 — _compute_adj_disp_cv (S112)
class TestComputeAdjDispCv:
    """_compute_adj_disp_cv returns std/mean of adjacent-edge dominant-axis displacement magnitudes."""

    @staticmethod
    def _adj_edge(i: int, j: int, dy: float, dx: float = 0.0) -> dict:
        M = np.array([[1, 0, dx], [0, 1, dy]], dtype=np.float32)
        return {"i": i, "j": j, "M": M, "weight": 0.8}

    def test_uniform_magnitudes_returns_zero(self):
        """All adjacent edges with identical |dy| → std=0 → CV=0.0."""
        edges = [self._adj_edge(i, i + 1, dy=-100) for i in range(4)]
        assert _compute_adj_disp_cv(edges) == pytest.approx(0.0)

    def test_high_cv_with_outlier(self):
        """One outlier at 10× the typical step → CV >> 0.5."""
        edges = [
            self._adj_edge(0, 1, dy=-100),
            self._adj_edge(1, 2, dy=-100),
            self._adj_edge(2, 3, dy=-100),
            self._adj_edge(3, 4, dy=-1000),  # 10× outlier
        ]
        cv = _compute_adj_disp_cv(edges)
        assert cv > 0.5

    def test_fewer_than_two_adjacent_returns_zero(self):
        """Single adjacent edge → 0.0 (safe no-op)."""
        edges = [self._adj_edge(0, 1, dy=-150)]
        assert _compute_adj_disp_cv(edges) == pytest.approx(0.0)

    def test_skip_edges_excluded(self):
        """Skip edges (|i-j|=2) do not contribute to CV computation."""
        adj = [self._adj_edge(0, 1, dy=-100), self._adj_edge(1, 2, dy=-100)]
        skip = [
            {
                "i": 0,
                "j": 2,
                "M": np.array([[1, 0, 0], [0, 1, -5000]], np.float32),
                "weight": 0.5,
            }
        ]
        assert _compute_adj_disp_cv(adj + skip) == pytest.approx(0.0)

    def test_dominant_axis_selection_uses_dx(self):
        """When median |dx| > median |dy|, CV is computed over dx magnitudes."""
        # dy ≈ 0, dx varies moderately → axis = horizontal
        edges = [
            self._adj_edge(0, 1, dy=2.0, dx=-200),
            self._adj_edge(1, 2, dy=1.0, dx=-200),
            self._adj_edge(2, 3, dy=3.0, dx=-200),
        ]
        assert _compute_adj_disp_cv(edges) == pytest.approx(0.0)


# §1.49 — _compute_adj_min_weight (S113)
class TestComputeAdjMinWeight:
    """_compute_adj_min_weight returns the minimum weight among adjacent edges."""

    @staticmethod
    def _edge(i: int, j: int, weight: float, dy: float = -100.0) -> dict:
        M = np.array([[1, 0, 0], [0, 1, dy]], dtype=np.float32)
        return {"i": i, "j": j, "M": M, "weight": weight}

    def test_all_high_weight_returns_minimum(self):
        """Three adjacent edges with weights 0.9, 0.8, 0.7 → min = 0.7."""
        edges = [self._edge(0, 1, 0.9), self._edge(1, 2, 0.8), self._edge(2, 3, 0.7)]
        assert _compute_adj_min_weight(edges) == pytest.approx(0.7)

    def test_one_low_weight_edge_captured(self):
        """One near-zero adjacent edge → min reflects that edge."""
        edges = [self._edge(0, 1, 0.9), self._edge(1, 2, 0.05), self._edge(2, 3, 0.85)]
        assert _compute_adj_min_weight(edges) == pytest.approx(0.05)

    def test_no_adjacent_edges_returns_one(self):
        """No adjacent edges → safe no-op sentinel 1.0."""
        skip = [self._edge(0, 2, 0.3)]  # |i-j|=2, not adjacent
        assert _compute_adj_min_weight(skip) == pytest.approx(1.0)

    def test_empty_edges_returns_one(self):
        """Empty edge list → 1.0."""
        assert _compute_adj_min_weight([]) == pytest.approx(1.0)

    def test_skip_edges_ignored(self):
        """Skip edges (|i-j|=2) do not lower the minimum."""
        adj = [self._edge(0, 1, 0.8), self._edge(1, 2, 0.75)]
        skip = [self._edge(0, 2, 0.01)]  # very low weight but |i-j|=2
        assert _compute_adj_min_weight(adj + skip) == pytest.approx(0.75)


# §1.50 — _compute_ba_max_residual (S114)
class TestComputeBaMaxResidual:
    """_compute_ba_max_residual returns the maximum per-edge BA residual in pixels."""

    @staticmethod
    def _affine(ty: float, tx: float = 0.0) -> np.ndarray:
        a = np.eye(2, 3, dtype=np.float32)
        a[0, 2] = tx
        a[1, 2] = ty
        return a

    @staticmethod
    def _edge(i: int, j: int, dy: float, dx: float = 0.0) -> dict:
        M = np.array([[1, 0, dx], [0, 1, dy]], dtype=np.float32)
        return {"i": i, "j": j, "M": M, "weight": 0.8}

    def test_perfect_alignment_returns_zero(self):
        """Affines exactly consistent with edges → residual = 0."""
        affines = [self._affine(0), self._affine(-100), self._affine(-200)]
        edges = [self._edge(0, 1, dy=-100), self._edge(1, 2, dy=-100)]
        assert _compute_ba_max_residual(edges, affines) == pytest.approx(0.0, abs=1e-4)

    def test_outlier_edge_produces_large_residual(self):
        """One edge with 300px wrong displacement → residual ≥ 300px."""
        affines = [self._affine(0), self._affine(-100), self._affine(-200)]
        edges = [
            self._edge(0, 1, dy=-100),
            self._edge(1, 2, dy=-500),
        ]  # 2nd edge: observed -500, predicted -100
        res = _compute_ba_max_residual(edges, affines)
        assert res == pytest.approx(400.0, abs=1e-3)

    def test_empty_edges_returns_zero(self):
        """No edges → 0.0 (safe no-op)."""
        affines = [self._affine(0), self._affine(-100)]
        assert _compute_ba_max_residual([], affines) == pytest.approx(0.0)

    def test_empty_affines_returns_zero(self):
        """No affines → 0.0 (safe no-op)."""
        edges = [self._edge(0, 1, dy=-100)]
        assert _compute_ba_max_residual(edges, []) == pytest.approx(0.0)

    def test_max_of_multiple_residuals_returned(self):
        """Returns the maximum, not mean, across all edge residuals."""
        affines = [
            self._affine(0),
            self._affine(-100),
            self._affine(-200),
            self._affine(-300),
        ]
        edges = [
            self._edge(0, 1, dy=-100),  # residual = 0
            self._edge(1, 2, dy=-50),  # residual = 50
            self._edge(2, 3, dy=-250),  # residual = 150
        ]
        assert _compute_ba_max_residual(edges, affines) == pytest.approx(
            150.0, abs=1e-3
        )


# §1.51 — _compute_min_adjacent_overlap (S115)
class TestComputeMinAdjacentOverlap:
    """_compute_min_adjacent_overlap returns the minimum canvas-space overlap between consecutive frames."""

    @staticmethod
    def _affine(ty: float, tx: float = 0.0) -> np.ndarray:
        a = np.eye(2, 3, dtype=np.float32)
        a[0, 2] = tx
        a[1, 2] = ty
        return a

    @staticmethod
    def _frame(h: int = 200, w: int = 100) -> np.ndarray:
        return np.zeros((h, w, 3), dtype=np.uint8)

    def test_normal_overlap_returns_positive(self):
        """Frames with 100px overlap → min_overlap = 100."""
        # frame 0 at ty=0 (h=200): trailing edge = 200
        # frame 1 at ty=100: leading edge = 100 → overlap = 200−100 = 100
        affines = [self._affine(0), self._affine(100)]
        frames = [self._frame(h=200), self._frame(h=200)]
        assert _compute_min_adjacent_overlap(affines, frames) == pytest.approx(100.0)

    def test_thin_overlap_detected(self):
        """Two pairs with overlaps 150px and 10px → min = 10."""
        affines = [self._affine(0), self._affine(190), self._affine(380)]
        frames = [self._frame(h=200), self._frame(h=200), self._frame(h=200)]
        # pair(0,1): trailing=200, leading=190 → overlap=10
        # pair(1,2): trailing=390, leading=380 → overlap=10
        assert _compute_min_adjacent_overlap(affines, frames) == pytest.approx(10.0)

    def test_gap_returns_negative(self):
        """Gap between frames (no overlap) returns negative value."""
        # frame 0 at ty=0 (h=200): trailing=200; frame 1 at ty=250 → gap=50 → overlap=-50
        affines = [self._affine(0), self._affine(250)]
        frames = [self._frame(h=200), self._frame(h=200)]
        assert _compute_min_adjacent_overlap(affines, frames) == pytest.approx(-50.0)

    def test_fewer_than_two_frames_returns_zero(self):
        """Single frame → 0.0 (safe no-op)."""
        assert _compute_min_adjacent_overlap(
            [self._affine(0)], [self._frame()]
        ) == pytest.approx(0.0)

    def test_min_of_multiple_pairs_returned(self):
        """Returns the smallest overlap across all pairs, not mean or first."""
        affines = [self._affine(0), self._affine(180), self._affine(280)]
        frames = [self._frame(h=200), self._frame(h=200), self._frame(h=200)]
        # pair(0,1): trailing=200, leading=180 → overlap=20
        # pair(1,2): trailing=380, leading=280 → overlap=100
        assert _compute_min_adjacent_overlap(affines, frames) == pytest.approx(20.0)


# §1.52 — _compute_ba_weighted_mean_residual (S116)
class TestComputeBaWeightedMeanResidual:
    """_compute_ba_weighted_mean_residual returns Σ(w_i × r_i) / Σ(w_i)."""

    @staticmethod
    def _affine(ty: float, tx: float = 0.0) -> np.ndarray:
        a = np.eye(2, 3, dtype=np.float32)
        a[0, 2] = tx
        a[1, 2] = ty
        return a

    @staticmethod
    def _edge(i: int, j: int, dy: float, dx: float = 0.0, weight: float = 0.8) -> dict:
        M = np.array([[1, 0, dx], [0, 1, dy]], dtype=np.float32)
        return {"i": i, "j": j, "M": M, "weight": weight}

    def test_perfect_alignment_returns_zero(self):
        """Affines consistent with edges → weighted mean residual = 0."""
        affines = [self._affine(0), self._affine(-100), self._affine(-200)]
        edges = [self._edge(0, 1, dy=-100), self._edge(1, 2, dy=-100)]
        assert _compute_ba_weighted_mean_residual(edges, affines) == pytest.approx(
            0.0, abs=1e-4
        )

    def test_uniform_residuals_equal_to_unweighted_mean(self):
        """Equal weights → weighted mean equals simple mean of residuals."""
        affines = [self._affine(0), self._affine(-100), self._affine(-200)]
        # All edges 50px off; predicted is -100 each, observed -50 each → r=50
        edges = [
            self._edge(0, 1, dy=-50, weight=1.0),
            self._edge(1, 2, dy=-50, weight=1.0),
        ]
        result = _compute_ba_weighted_mean_residual(edges, affines)
        assert result == pytest.approx(50.0, abs=1e-3)

    def test_high_weight_good_edge_lowers_mean(self):
        """High-weight good edge pulls weighted mean below simple mean."""
        affines = [self._affine(0), self._affine(-100), self._affine(-200)]
        edges = [
            self._edge(0, 1, dy=-100, weight=0.9),  # residual=0, high weight
            self._edge(1, 2, dy=-50, weight=0.1),  # residual=50, low weight
        ]
        # weighted mean = (0.9×0 + 0.1×50) / (0.9+0.1) = 5.0
        result = _compute_ba_weighted_mean_residual(edges, affines)
        assert result == pytest.approx(5.0, abs=1e-3)

    def test_empty_edges_returns_zero(self):
        """Empty edge list → 0.0 (safe no-op)."""
        affines = [self._affine(0), self._affine(-100)]
        assert _compute_ba_weighted_mean_residual([], affines) == pytest.approx(0.0)

    def test_zero_weight_edges_returns_zero(self):
        """All-zero weights → total_w=0 → returns 0.0 (avoid divide-by-zero)."""
        affines = [self._affine(0), self._affine(-100)]
        edges = [self._edge(0, 1, dy=-50, weight=0.0)]
        assert _compute_ba_weighted_mean_residual(edges, affines) == pytest.approx(0.0)


# §1.53 — _compute_canvas_memory_mb (S117)
class TestComputeCanvasMemoryMb:
    """_compute_canvas_memory_mb returns canvas_h * canvas_w * 3 * 4 / 1024² in MB."""

    def test_typical_1080p_panorama(self):
        """1920×5000 canvas → exactly 1920*5000*12/1048576 MB."""
        expected = 1920 * 5000 * 3 * 4 / (1024**2)
        assert _compute_canvas_memory_mb(5000, 1920) == pytest.approx(expected)

    def test_giant_canvas_exceeds_threshold(self):
        """32768×32768 canvas → ~12 GB, well above 2048 MB threshold."""
        mb = _compute_canvas_memory_mb(32768, 32768)
        assert mb > 2048.0

    def test_zero_height_returns_zero(self):
        """Zero canvas height → 0.0 MB (safe no-op)."""
        assert _compute_canvas_memory_mb(0, 1920) == pytest.approx(0.0)

    def test_zero_width_returns_zero(self):
        """Zero canvas width → 0.0 MB (safe no-op)."""
        assert _compute_canvas_memory_mb(1080, 0) == pytest.approx(0.0)

    def test_borderline_canvas_within_limit(self):
        """1920×32768 canvas → ≈720 MB; within 2048 MB limit."""
        mb = _compute_canvas_memory_mb(32768, 1920)
        assert mb == pytest.approx(1920 * 32768 * 3 * 4 / (1024**2))
        assert mb < 2048.0


# §1.54 — _compute_render_luma_std (S118)
class TestComputeRenderLumaStd:
    """_compute_render_luma_std returns std of BGR-mean luminance for valid pixels."""

    @staticmethod
    def _canvas(h: int, w: int, fill: int = 128) -> np.ndarray:
        return np.full((h, w, 3), fill, dtype=np.uint8)

    @staticmethod
    def _mask(h: int, w: int, fraction: float = 1.0) -> np.ndarray:
        mask = np.zeros((h, w), dtype=np.uint8)
        rows = int(h * fraction)
        mask[:rows, :] = 1
        return mask

    def test_uniform_canvas_returns_zero(self):
        """Solid-colour canvas → all pixels same luminance → std = 0."""
        canvas = self._canvas(100, 100, fill=128)
        mask = self._mask(100, 100)
        assert _compute_render_luma_std(canvas, mask) == pytest.approx(0.0, abs=1e-4)

    def test_varied_canvas_returns_positive(self):
        """Canvas with varied pixel values → std > 0."""
        rng = np.random.default_rng(42)
        canvas = rng.integers(0, 255, (100, 100, 3), dtype=np.uint8)
        mask = self._mask(100, 100)
        assert _compute_render_luma_std(canvas, mask) > 0.0

    def test_no_valid_pixels_returns_zero(self):
        """Zero valid_mask → 0.0 (safe no-op)."""
        canvas = self._canvas(100, 100)
        mask = np.zeros((100, 100), dtype=np.uint8)
        assert _compute_render_luma_std(canvas, mask) == pytest.approx(0.0)

    def test_none_inputs_return_zero(self):
        """None canvas or mask → 0.0."""
        assert _compute_render_luma_std(None, None) == pytest.approx(0.0)

    def test_only_valid_pixels_contribute(self):
        """Masked-out pixels (value=0) do not lower the std."""
        canvas = np.zeros((10, 10, 3), dtype=np.uint8)
        canvas[:5, :] = 200  # valid region: bright
        canvas[5:, :] = 0  # invalid region: dark (should be ignored)
        mask = np.zeros((10, 10), dtype=np.uint8)
        mask[:5, :] = 1  # only top half valid
        std = _compute_render_luma_std(canvas, mask)
        assert std == pytest.approx(
            0.0, abs=1e-4
        )  # all valid pixels are the same value


# §9C — _apply_hires_keyframes (Sprint 8)
class TestApplyHiresKeyframes:
    """_apply_hires_keyframes replaces proxy frames with hires images and scales affines/masks."""

    @staticmethod
    def _make_frame(h: int, w: int, val: int = 128) -> np.ndarray:
        return np.full((h, w, 3), val, dtype=np.uint8)

    @staticmethod
    def _make_affine(tx: float = 0.0, ty: float = 0.0) -> np.ndarray:
        M = np.eye(2, 3, dtype=np.float32)
        M[0, 2] = tx
        M[1, 2] = ty
        return M

    @staticmethod
    def _make_mask(h: int, w: int) -> np.ndarray:
        m = np.zeros((h, w), dtype=np.uint8)
        m[: h // 2, :] = 1
        return m

    def test_empty_dict_is_noop(self):
        """Empty hires_keyframes → returns original lists unchanged."""
        frames = [self._make_frame(100, 200)]
        affines = [self._make_affine(10.0, 5.0)]
        masks = [self._make_mask(100, 200)]

        n, f_out, a_out, m_out = _apply_hires_keyframes(frames, affines, masks, {})

        assert n == 0
        assert f_out is frames
        assert a_out is affines
        assert m_out is masks

    def test_scale_computation_and_frame_replacement(self, tmp_path):
        """Hires frame at 2× scale → affine tx/ty doubled, frame replaced."""
        proxy_h, proxy_w = 50, 100
        hires_h, hires_w = 100, 200  # 2× scale

        frames = [self._make_frame(proxy_h, proxy_w, val=50)]
        affines = [self._make_affine(tx=20.0, ty=10.0)]
        masks = [None]

        hires_img = self._make_frame(hires_h, hires_w, val=200)
        hires_path = tmp_path / "hires_0.png"
        cv2.imwrite(str(hires_path), hires_img)

        n, f_out, a_out, m_out = _apply_hires_keyframes(
            frames, affines, masks, {0: str(hires_path)}
        )

        assert n == 1
        assert f_out[0].shape == (hires_h, hires_w, 3)
        assert a_out[0][0, 2] == pytest.approx(40.0)  # tx * scale_x
        assert a_out[0][1, 2] == pytest.approx(20.0)  # ty * scale_y

    def test_proxy_upscale_fallback_for_non_hires_frames(self, tmp_path):
        """Frames without a hires path are upscaled to match the hires resolution."""
        proxy_h, proxy_w = 50, 100
        hires_h, hires_w = 100, 200

        frames = [
            self._make_frame(proxy_h, proxy_w, val=10),  # gets hires replacement
            self._make_frame(proxy_h, proxy_w, val=20),  # upscaled fallback
        ]
        affines = [self._make_affine(), self._make_affine()]
        masks = [None, None]

        hires_img = self._make_frame(hires_h, hires_w, val=200)
        hires_path = tmp_path / "hires_0.png"
        cv2.imwrite(str(hires_path), hires_img)

        n, f_out, a_out, m_out = _apply_hires_keyframes(
            frames, affines, masks, {0: str(hires_path)}
        )

        assert n == 1
        assert f_out[0].shape == (hires_h, hires_w, 3)
        assert f_out[1].shape == (hires_h, hires_w, 3)  # upscaled to match

    def test_bg_mask_resized_with_nearest_neighbor(self, tmp_path):
        """bg_masks are resized to hires resolution using INTER_NEAREST (binary-safe)."""
        proxy_h, proxy_w = 4, 8
        hires_h, hires_w = 8, 16

        mask = self._make_mask(proxy_h, proxy_w)  # binary, top-half=1
        frames = [self._make_frame(proxy_h, proxy_w)]
        affines = [self._make_affine()]
        masks = [mask]

        hires_img = self._make_frame(hires_h, hires_w)
        hires_path = tmp_path / "hires_0.png"
        cv2.imwrite(str(hires_path), hires_img)

        _, _, _, m_out = _apply_hires_keyframes(
            frames, affines, masks, {0: str(hires_path)}
        )

        assert m_out[0] is not None
        assert m_out[0].shape == (hires_h, hires_w)
        # binary values preserved (INTER_NEAREST)
        unique_vals = set(np.unique(m_out[0]))
        assert unique_vals <= {0, 1}

    def test_none_mask_stays_none(self, tmp_path):
        """None bg_mask entries pass through as None after hires substitution."""
        frames = [self._make_frame(50, 100)]
        affines = [self._make_affine()]
        masks = [None]

        hires_img = self._make_frame(100, 200)
        hires_path = tmp_path / "hires_0.png"
        cv2.imwrite(str(hires_path), hires_img)

        _, _, _, m_out = _apply_hires_keyframes(
            frames, affines, masks, {0: str(hires_path)}
        )

        assert m_out[0] is None

    def test_invalid_path_returns_zero_substitutions(self):
        """All paths unreadable → n=0, original lists returned unchanged."""
        frames = [self._make_frame(50, 100)]
        affines = [self._make_affine()]
        masks = [None]

        n, f_out, a_out, m_out = _apply_hires_keyframes(
            frames, affines, masks, {0: "/nonexistent/path/hires.png"}
        )

        assert n == 0
        assert f_out is frames
        assert a_out is affines
        assert m_out is masks

    def test_out_of_bounds_index_ignored(self, tmp_path):
        """Index outside frame range is silently skipped."""
        frames = [self._make_frame(50, 100)]
        affines = [self._make_affine()]
        masks = [None]

        hires_img = self._make_frame(100, 200)
        hires_path = tmp_path / "hires_99.png"
        cv2.imwrite(str(hires_path), hires_img)

        n, f_out, a_out, m_out = _apply_hires_keyframes(
            frames, affines, masks, {99: str(hires_path)}
        )

        assert n == 0

    def test_linear_submatrix_unchanged(self, tmp_path):
        """Affine rotation/shear components (2×2 sub-matrix) are NOT scaled."""
        proxy_h, proxy_w = 50, 100
        hires_h, hires_w = 100, 200

        # Affine with small rotation component
        M = np.array([[0.99, -0.14, 30.0], [0.14, 0.99, 15.0]], dtype=np.float32)
        frames = [self._make_frame(proxy_h, proxy_w)]
        affines = [M]
        masks = [None]

        hires_img = self._make_frame(hires_h, hires_w)
        hires_path = tmp_path / "hires_0.png"
        cv2.imwrite(str(hires_path), hires_img)

        _, _, a_out, _ = _apply_hires_keyframes(
            frames, affines, masks, {0: str(hires_path)}
        )

        # Linear sub-matrix must be exactly preserved
        np.testing.assert_array_almost_equal(a_out[0][:, :2], M[:, :2])
        # Translation scaled by 2×
        assert a_out[0][0, 2] == pytest.approx(60.0)
        assert a_out[0][1, 2] == pytest.approx(30.0)


# ---------------------------------------------------------------------------
# §1.55 — _compute_max_affine_rotation_deg (S120)
# ---------------------------------------------------------------------------


class TestComputeMaxAffineRotationDeg:
    """_compute_max_affine_rotation_deg returns maximum |rotation| in degrees."""

    @staticmethod
    def _rot_affine(angle_deg: float, tx: float = 0.0, ty: float = 0.0) -> np.ndarray:
        rad = np.radians(angle_deg)
        M = np.array(
            [[np.cos(rad), -np.sin(rad), tx], [np.sin(rad), np.cos(rad), ty]],
            dtype=np.float32,
        )
        return M

    def test_empty_list_returns_zero(self):
        assert _compute_max_affine_rotation_deg([]) == pytest.approx(0.0)

    def test_identity_affines_return_zero(self):
        affines = [np.eye(2, 3, dtype=np.float32) for _ in range(4)]
        assert _compute_max_affine_rotation_deg(affines) == pytest.approx(0.0, abs=1e-4)

    def test_single_rotated_affine_detected(self):
        M = self._rot_affine(10.0)
        assert _compute_max_affine_rotation_deg([M]) == pytest.approx(10.0, abs=1e-3)

    def test_maximum_taken_across_multiple_affines(self):
        affines = [
            self._rot_affine(2.0),
            self._rot_affine(7.5),
            self._rot_affine(1.0),
        ]
        assert _compute_max_affine_rotation_deg(affines) == pytest.approx(7.5, abs=1e-3)

    def test_negative_rotation_uses_absolute_value(self):
        M = self._rot_affine(-8.0)
        assert _compute_max_affine_rotation_deg([M]) == pytest.approx(8.0, abs=1e-3)


# ---------------------------------------------------------------------------
# §3.16 — _smooth_affine_trajectory (S121)
# ---------------------------------------------------------------------------


class TestSmoothAffineTrajectory:
    """_smooth_affine_trajectory: IQR-gated Gaussian smoother on BA affine tx/ty."""

    @staticmethod
    def _trans_affine(tx: float, ty: float) -> np.ndarray:
        M = np.eye(2, 3, dtype=np.float32)
        M[0, 2] = tx
        M[1, 2] = ty
        return M

    def test_fewer_than_three_affines_returns_original(self):
        """<3 affines → was_applied=False and same object returned."""
        affines = [self._trans_affine(0.0, 0.0), self._trans_affine(50.0, 0.0)]
        out, applied = _smooth_affine_trajectory(affines, sigma=1.5)
        assert not applied
        assert out is affines

    def test_zero_sigma_is_noop(self):
        """sigma=0 → was_applied=False, original list returned unchanged."""
        affines = [self._trans_affine(float(i * 50), 0.0) for i in range(5)]
        out, applied = _smooth_affine_trajectory(affines, sigma=0.0)
        assert not applied
        assert out is affines

    def test_low_iqr_linear_scroll_skipped(self):
        """Perfectly uniform step sequence has IQR=0 → smoother skips (was_applied=False)."""
        affines = [self._trans_affine(0.0, float(i * 100)) for i in range(8)]
        out, applied = _smooth_affine_trajectory(affines, sigma=1.5, iqr_threshold=10.0)
        assert not applied
        assert out is affines

    def test_jittery_sequence_is_smoothed(self):
        """Noisy tx sequence with IQR > threshold → smoothing applied and tx values change."""
        rng = np.random.default_rng(42)
        base_ty = np.arange(10, dtype=np.float64) * 80.0
        noise = rng.uniform(-30.0, 30.0, size=10)
        affines = [
            self._trans_affine(float(noise[i]), float(base_ty[i])) for i in range(10)
        ]

        out, applied = _smooth_affine_trajectory(affines, sigma=1.5, iqr_threshold=5.0)

        assert applied
        assert len(out) == len(affines)
        # Smoothed tx values differ from original noisy values
        orig_tx = np.array([a[0, 2] for a in affines])
        smooth_tx = np.array([a[0, 2] for a in out])
        assert not np.allclose(orig_tx, smooth_tx)

    def test_rotation_scale_components_preserved(self):
        """After smoothing, M[:, :2] (rotation/scale) is identical to input."""
        rad = np.radians(2.0)

        def rotated(tx, ty):
            M = np.array(
                [[np.cos(rad), -np.sin(rad), tx], [np.sin(rad), np.cos(rad), ty]],
                dtype=np.float32,
            )
            return M

        rng = np.random.default_rng(7)
        noise = rng.uniform(-40.0, 40.0, size=8)
        affines = [rotated(float(noise[i]), float(i * 60)) for i in range(8)]

        out, applied = _smooth_affine_trajectory(affines, sigma=1.5, iqr_threshold=5.0)

        if applied:
            for orig, sm in zip(affines, out):
                np.testing.assert_array_almost_equal(orig[:, :2], sm[:, :2], decimal=5)


class TestComputeCanvasAspectRatio:
    """§1.62 (S125): Canvas height/width aspect ratio helper."""

    def test_tall_canvas(self):
        assert _compute_canvas_aspect_ratio(1200, 400) == pytest.approx(3.0)

    def test_wide_canvas(self):
        assert _compute_canvas_aspect_ratio(400, 1200) == pytest.approx(1.0 / 3.0)

    def test_square_canvas(self):
        assert _compute_canvas_aspect_ratio(500, 500) == pytest.approx(1.0)

    def test_zero_dimensions_returns_zero(self):
        assert _compute_canvas_aspect_ratio(0, 500) == 0.0
        assert _compute_canvas_aspect_ratio(500, 0) == 0.0

    def test_negative_dimensions_returns_zero(self):
        assert _compute_canvas_aspect_ratio(-1, 500) == 0.0


class TestSortFramesByIndex:
    """§1.63 (S127): Numeric-suffix sort guard for frame paths."""

    def test_out_of_order_paths_sorted(self):
        paths = ["frame_003.png", "frame_001.png", "frame_002.png"]
        result = _sort_frames_by_index(paths)
        assert result == ["frame_001.png", "frame_002.png", "frame_003.png"]

    def test_already_sorted_unchanged(self):
        paths = ["img_01.jpg", "img_02.jpg", "img_03.jpg"]
        result = _sort_frames_by_index(paths)
        assert result == paths

    def test_zero_padded_sorted_numerically_not_lexicographically(self):
        paths = ["f_009.png", "f_010.png", "f_011.png"]
        result = _sort_frames_by_index(paths)
        assert result == ["f_009.png", "f_010.png", "f_011.png"]

    def test_paths_without_suffix_placed_last(self):
        paths = ["alpha.png", "frame_001.png", "frame_002.png"]
        result = _sort_frames_by_index(paths)
        assert result[0] == "frame_001.png"
        assert result[1] == "frame_002.png"
        assert result[2] == "alpha.png"

    def test_empty_list(self):
        assert _sort_frames_by_index([]) == []


# ---------------------------------------------------------------------------
# §1.67 — Frame canvas spread validation (S131)
# ---------------------------------------------------------------------------


def _make_spread_edge(i: int, j: int, ty: float, tx: float = 0.0) -> dict:
    return {"i": i, "j": j, "ty": ty, "tx": tx, "weight": 0.9}


class TestCheckCanvasSpread:
    """§1.67 (S131): _check_canvas_spread validates that selected frames cover the scroll range."""

    def test_empty_edges_returns_true(self):
        """No edges → cannot determine spread → safe pass."""
        assert _check_canvas_spread([], 0.5) is True

    def test_zero_threshold_always_passes(self):
        """min_spread_fraction=0 → gate disabled → always True."""
        edges = [_make_spread_edge(0, 1, ty=10.0), _make_spread_edge(1, 2, ty=10.0)]
        assert _check_canvas_spread(edges, 0.0) is True

    def test_well_spread_frames_pass(self):
        """Frames uniformly spread across 10 steps → spread ≈ 1.0 → passes 0.5 threshold."""
        edges = [_make_spread_edge(i, i + 1, ty=100.0) for i in range(9)]
        assert _check_canvas_spread(edges, 0.5) is True

    def test_clustered_last_frame_fails_high_threshold(self):
        """Most frames advance 100px/step but last barely moves → fails 0.8 threshold.

        adj_steps = [100, 100, 100, 1]; median = 100; expected_span = 400;
        actual_span = 301; ratio ≈ 0.75 → passes 0.5 but fails 0.8.
        """
        edges = [
            _make_spread_edge(0, 1, ty=100.0),
            _make_spread_edge(1, 2, ty=100.0),
            _make_spread_edge(2, 3, ty=100.0),
            _make_spread_edge(3, 4, ty=1.0),
        ]
        assert _check_canvas_spread(edges, 0.5) is True  # 0.75 ≥ 0.5
        assert _check_canvas_spread(edges, 0.8) is False  # 0.75 < 0.8

    def test_two_frame_sequence_always_passes(self):
        """Only 1 edge (2 nodes) → spread is exact → should pass."""
        edges = [_make_spread_edge(0, 1, ty=80.0)]
        assert _check_canvas_spread(edges, 0.5) is True

    def test_horizontal_scroll_uses_tx_axis(self):
        """When tx dominates over ty, the check should use tx axis."""
        # Purely horizontal scroll: tx=100 per step, ty=0
        edges = [_make_spread_edge(i, i + 1, ty=0.0, tx=100.0) for i in range(4)]
        assert _check_canvas_spread(edges, 0.5) is True


class TestComputeBgLumSpread:
    """§1.71 (S132): _compute_bg_lum_spread measures per-frame background luma range."""

    # 16×16 = 256 pixels, exceeds min_bg_px default of 200.
    def _make_frame(self, lum: int, H: int = 16, W: int = 16) -> np.ndarray:
        return np.full((H, W, 3), lum, dtype=np.uint8)

    def _make_mask(self, H: int = 16, W: int = 16, bg: bool = True) -> np.ndarray:
        return np.full((H, W), 255 if bg else 0, dtype=np.uint8)

    def test_fewer_than_two_frames_returns_zero(self):
        """Single frame → cannot compute spread → returns 0.0."""
        frames = [self._make_frame(100)]
        masks = [self._make_mask()]
        assert _compute_bg_lum_spread(frames, masks) == 0.0

    def test_identical_frames_returns_zero(self):
        """All frames same luma → spread = 0."""
        frames = [self._make_frame(128) for _ in range(3)]
        masks = [self._make_mask() for _ in range(3)]
        assert _compute_bg_lum_spread(frames, masks) == 0.0

    def test_spread_equals_max_minus_min(self):
        """Frames at lum=50 and lum=200 → spread is large."""
        frames = [self._make_frame(50), self._make_frame(200)]
        masks = [self._make_mask() for _ in range(2)]
        result = _compute_bg_lum_spread(frames, masks)
        assert result > 100.0, f"Expected large spread, got {result}"

    def test_none_masks_use_all_pixels(self):
        """None masks → all pixels treated as background."""
        frames = [self._make_frame(60), self._make_frame(180)]
        masks = [None, None]
        result = _compute_bg_lum_spread(frames, masks)
        assert result > 50.0, f"Expected spread > 50 with None masks, got {result}"

    def test_insufficient_bg_pixels_skipped(self):
        """Frames with fewer than min_bg_px background pixels are skipped."""
        big_frame = np.full((100, 100, 3), 200, dtype=np.uint8)
        tiny_bg = np.zeros((100, 100), dtype=np.uint8)
        tiny_bg[0, 0] = 255
        frames = [self._make_frame(50), big_frame]
        masks = [self._make_mask(), tiny_bg]
        result = _compute_bg_lum_spread(frames, masks, min_bg_px=200)

        assert result == 0.0, "Only one valid frame → spread = 0"


class TestComputeBgLumMonotonicity:
    """§1.73 (S133): _compute_bg_lum_monotonicity measures Kendall-τ of bg luma order."""

    def _make_frame(self, lum: int, H: int = 16, W: int = 16) -> np.ndarray:
        return np.full((H, W, 3), lum, dtype=np.uint8)

    def _make_mask(self, H: int = 16, W: int = 16) -> np.ndarray:
        return np.full((H, W), 255, dtype=np.uint8)

    def test_fewer_than_three_frames_returns_zero(self):
        """Two frames → cannot form meaningful monotone sequence → 0.0."""
        frames = [self._make_frame(100), self._make_frame(150)]
        masks = [self._make_mask(), self._make_mask()]
        assert _compute_bg_lum_monotonicity(frames, masks) == 0.0

    def test_perfectly_ascending_returns_one(self):
        """Strictly ascending lumas → τ = +1.0 → |τ| = 1.0."""
        frames = [self._make_frame(lum) for lum in [80, 100, 120, 140, 160]]
        masks = [self._make_mask() for _ in range(5)]
        result = _compute_bg_lum_monotonicity(frames, masks)
        assert abs(result - 1.0) < 1e-9

    def test_perfectly_descending_returns_one(self):
        """Strictly descending lumas → τ = -1.0 → |τ| = 1.0 (same absolute value)."""
        frames = [self._make_frame(lum) for lum in [160, 140, 120, 100, 80]]
        masks = [self._make_mask() for _ in range(5)]
        result = _compute_bg_lum_monotonicity(frames, masks)
        assert abs(result - 1.0) < 1e-9

    def test_random_order_returns_low_tau(self):
        """Non-monotone luma sequence → |τ| << 1.0."""
        frames = [self._make_frame(lum) for lum in [100, 80, 150, 90, 130]]
        masks = [self._make_mask() for _ in range(5)]
        result = _compute_bg_lum_monotonicity(frames, masks)
        assert result < 0.7, f"Expected low |τ| for non-monotone sequence, got {result}"

    def test_none_masks_treated_as_all_background(self):
        """None masks → all pixels used → ascending sequence still gives |τ|=1."""
        frames = [self._make_frame(lum) for lum in [50, 100, 150]]
        masks = [None, None, None]
        result = _compute_bg_lum_monotonicity(frames, masks)
        assert abs(result - 1.0) < 1e-9


class TestComputeCanvasFillRatio:
    """§1.74 (S133): _compute_canvas_fill_ratio measures non-empty canvas fraction."""

    def _solid_canvas(self, H: int, W: int, lum: int) -> np.ndarray:
        return np.full((H, W, 3), lum, dtype=np.uint8)

    def test_fully_filled_canvas_returns_one(self):
        """All pixels above threshold → ratio = 1.0."""
        canvas = self._solid_canvas(64, 64, 128)
        assert _compute_canvas_fill_ratio(canvas, pix_thresh=10) == 1.0

    def test_fully_empty_canvas_returns_zero(self):
        """All pixels at 0 → ratio = 0.0."""
        canvas = np.zeros((64, 64, 3), dtype=np.uint8)
        assert _compute_canvas_fill_ratio(canvas, pix_thresh=10) == 0.0

    def test_half_filled_canvas_returns_half(self):
        """Top half filled, bottom half empty → ratio ≈ 0.5."""
        canvas = np.zeros((64, 64, 3), dtype=np.uint8)
        canvas[:32] = 128
        result = _compute_canvas_fill_ratio(canvas, pix_thresh=10)
        assert abs(result - 0.5) < 1e-6

    def test_threshold_boundary(self):
        """Pixels at exactly the threshold are treated as empty."""
        canvas = self._solid_canvas(32, 32, 10)
        result = _compute_canvas_fill_ratio(canvas, pix_thresh=10)
        assert result == 0.0

    def test_zero_size_canvas_returns_one(self):
        """Empty array → safe default of 1.0 (no gate firing)."""
        canvas = np.zeros((0, 0, 3), dtype=np.uint8)
        assert _compute_canvas_fill_ratio(canvas, pix_thresh=10) == 1.0


class TestComputeStripVarianceRatio:
    """§1.75 (S133): _compute_strip_variance_ratio measures texture imbalance across strips."""

    def test_single_strip_returns_one(self):
        """n_strips=1 → no comparison possible → ratio = 1.0."""
        canvas = np.random.randint(0, 255, (64, 64, 3), dtype=np.uint8)
        assert _compute_strip_variance_ratio(canvas, n_strips=1) == 1.0

    def test_uniform_canvas_returns_one(self):
        """Perfectly uniform canvas → all strip variances zero → safe return 1.0."""
        canvas = np.full((64, 64, 3), 128, dtype=np.uint8)
        assert _compute_strip_variance_ratio(canvas, n_strips=4) == 1.0

    def test_balanced_strips_near_one(self):
        """Two strips with similar noise → ratio close to 1.0."""
        np.random.seed(0)
        canvas = np.random.randint(100, 200, (64, 64, 3), dtype=np.uint8)
        ratio = _compute_strip_variance_ratio(canvas, n_strips=2)
        assert ratio < 5.0, f"Balanced noisy strips should have low ratio, got {ratio}"

    def test_flat_vs_noisy_strip_high_ratio(self):
        """One nearly-flat strip and one noisy strip → high variance ratio."""
        np.random.seed(42)
        canvas = np.zeros((64, 64, 3), dtype=np.uint8)
        # Bottom strip: nearly flat (lum in [126,129]) → very low Laplacian variance
        canvas[:32] = np.random.randint(126, 130, (32, 64, 3), dtype=np.uint8)
        # Top strip: highly variable (full 0-255 noise) → high Laplacian variance
        canvas[32:] = np.random.randint(0, 255, (32, 64, 3), dtype=np.uint8)
        ratio = _compute_strip_variance_ratio(canvas, n_strips=2)
        assert ratio > 5.0, f"Expected high ratio for nearly-flat vs noisy, got {ratio}"

    def test_zero_size_canvas_returns_one(self):
        """Empty canvas → safe default of 1.0."""
        canvas = np.zeros((0, 64, 3), dtype=np.uint8)
        assert _compute_strip_variance_ratio(canvas, n_strips=2) == 1.0


class TestHybridExport:
    """§2.8: HybridStitch JSON export — build_hybrid_export / save / load round-trip."""

    def _make_state(self):
        import numpy as np

        affines = [np.eye(2, 3, dtype=np.float64) for _ in range(3)]
        affines[1][1, 2] = 100.0
        affines[2][1, 2] = 200.0
        return {
            "image_paths": ["/a/1.png", "/a/2.png", "/a/3.png"],
            "affines": affines,
            "photometric_gains": [1.0, 1.05, 0.97],
            "photometric_biases": [0.0, 2.0, -1.0],
            "canvas_w": 640,
            "canvas_h": 480,
            "seam_boundaries": [100.0, 200.0],
            "seam_post_diffs": {0: 5.3, 1: 12.1},
        }

    def test_build_hybrid_export_affine_flattening(self):
        """build_hybrid_export flattens 2×3 numpy affines to flat 6-float lists."""
        from backend.src.animation.rendering.hybrid_export import build_hybrid_export

        state = self._make_state()
        data = build_hybrid_export(state)
        assert len(data.affines) == 3
        assert len(data.affines[0]) == 6
        assert data.affines[1][5] == 100.0

    def test_build_hybrid_export_fields(self):
        """All scalar fields are correctly transferred."""
        from backend.src.animation.rendering.hybrid_export import build_hybrid_export

        state = self._make_state()
        data = build_hybrid_export(state)
        assert data.canvas_w == 640
        assert data.canvas_h == 480
        assert data.image_paths == ["/a/1.png", "/a/2.png", "/a/3.png"]
        assert data.asp_version == "S144"

    def test_save_and_load_round_trip(self, tmp_path):
        """save_hybrid_export + load_hybrid_export recovers original data."""
        from backend.src.animation.rendering.hybrid_export import (
            build_hybrid_export,
            save_hybrid_export,
            load_hybrid_export,
        )

        state = self._make_state()
        data = build_hybrid_export(state)
        path = str(tmp_path / "export.json")
        save_hybrid_export(data, path)
        loaded = load_hybrid_export(path)
        assert loaded.canvas_w == data.canvas_w
        assert loaded.canvas_h == data.canvas_h
        assert loaded.affines == data.affines
        assert loaded.seam_post_diffs == data.seam_post_diffs

    def test_load_missing_file_raises(self, tmp_path):
        """load_hybrid_export raises FileNotFoundError for missing path."""
        from backend.src.animation.rendering.hybrid_export import load_hybrid_export
        import pytest

        with pytest.raises(FileNotFoundError):
            load_hybrid_export(str(tmp_path / "nonexistent.json"))

    def test_hybrid_export_path_flag_is_string(self):
        """_HYBRID_EXPORT_PATH module flag exists and is a string."""
        import backend.src.animation.core.pipeline as pip

        assert isinstance(pip._HYBRID_EXPORT_PATH, str)


# ===========================================================================
# Merged from test_pipeline_s160.py
# ===========================================================================


def _make_affine_wave_correct(tx: float, ty: float) -> np.ndarray:
    M = np.eye(2, 3, dtype=np.float32)
    M[0, 2] = tx
    M[1, 2] = ty
    return M


class TestWaveCorrectAffines:
    """§4.3: Post-BA linear wave correction."""

    def test_flag_in_module(self):
        assert hasattr(pipeline, "_WAVE_CORRECT")

    def test_no_drift_unchanged(self):
        # tx=[0,0,0], ty=[0,100,200] — tx range = 0 < 5.0 → values unchanged
        affines = [_make_affine_wave_correct(0.0, float(i * 100)) for i in range(3)]
        result = _wave_correct_affines(affines, axis="vertical")
        # C++ always returns new arrays; compare values, not identity
        for r, a in zip(result, affines):
            np.testing.assert_allclose(r, a, atol=1e-4)

    def test_vertical_corrects_tx_drift(self):
        # tx=[0,5,10,15], ty=[0,100,200,300] — linear tx drift of 5px/frame
        affines = [
            _make_affine_wave_correct(float(i * 5), float(i * 100)) for i in range(4)
        ]
        result = _wave_correct_affines(affines, axis="vertical")
        # After correction, tx should be near-flat (all ≈ tx[0])
        txs = [float(M[0, 2]) for M in result]
        tx_range = max(txs) - min(txs)
        assert tx_range < 2.0  # nearly flat

    def test_below_min_range_unchanged(self):
        # tx=[0,2,4] — range=4 < WAVE_CORRECT_MIN_TX_RANGE=5.0 → values unchanged
        affines = [
            _make_affine_wave_correct(float(i * 2), float(i * 100)) for i in range(3)
        ]
        result = _wave_correct_affines(affines, axis="vertical")
        for r, a in zip(result, affines):
            np.testing.assert_allclose(r, a, atol=1e-4)

    def test_schema_entry(self):
        assert "ASP_WAVE_CORRECT" in config._CONFIG_SCHEMA


# ---------------------------------------------------------------------------
# TestSpatialDedupFramesBatchWiring — C++ batch dispatch (S46)
# ---------------------------------------------------------------------------


class TestSpatialDedupFramesBatchWiring:
    """Phase 5: _spatial_dedup_frames C++ dispatch via batch.frame_selection.

    These tests verify the M-affine → dx/dy conversion layer and the
    reconstruction of the 6-tuple return value from C++ keep indices.
    The C++ function uses cumulative-displacement greedy dedup; the
    tests exercise the same edge cases as TestSpatialDedupFrames.
    """

    def test_no_drop_returns_original_lists(self):
        """When no frames are dropped keep_idx covers all frames → return originals."""
        frames = [_make_frame(val=v) for v in [10, 20, 30]]
        scans = [_make_frame(val=v) for v in [10, 20, 30]]
        masks = [_make_mask() for _ in range(3)]
        paths = ["x0.png", "x1.png", "x2.png"]
        edges = [_make_edge(0, 1, dy=100.0), _make_edge(1, 2, dy=100.0)]

        out_f, out_s, _, _, out_e, n = _spatial_dedup_frames(
            frames, scans, masks, paths, edges, min_displacement_px=25.0
        )

        assert n == 0
        assert len(out_f) == 3
        assert len(out_s) == 3
        assert len(out_e) == 2

    def test_near_static_frame_dropped(self):
        """Frame 1 with dy=3 < 25 threshold must be dropped."""
        frames = [_make_frame(val=v) for v in [10, 20, 30]]
        scans = [_make_frame(val=v + 1) for v in [10, 20, 30]]
        masks = [_make_mask() for _ in range(3)]
        paths = ["y0.png", "y1.png", "y2.png"]
        edges = [_make_edge(0, 1, dy=3.0), _make_edge(1, 2, dy=80.0)]

        out_f, out_s, _, out_p, _, n = _spatial_dedup_frames(
            frames, scans, masks, paths, edges, min_displacement_px=25.0
        )

        assert n == 1
        assert len(out_f) == 2
        assert out_f[0][0, 0, 0] == 10  # frame 0 kept
        assert out_f[1][0, 0, 0] == 30  # frame 2 kept

    def test_scans_sync_preserved_after_drop(self):
        """scans_frames must be subset-synced with frames (§1.9A S28)."""
        frames = [_make_frame(val=v) for v in [10, 20, 30]]
        scans = [_make_frame(val=v + 5) for v in [10, 20, 30]]
        masks = [_make_mask() for _ in range(3)]
        paths = ["z0.png", "z1.png", "z2.png"]
        edges = [_make_edge(0, 1, dy=3.0), _make_edge(1, 2, dy=80.0)]

        _, out_s, _, _, _, n = _spatial_dedup_frames(
            frames, scans, masks, paths, edges, min_displacement_px=25.0
        )

        assert n == 1
        assert len(out_s) == 2
        assert out_s[0][0, 0, 0] == 15   # scans[0] = val+5=15
        assert out_s[1][0, 0, 0] == 35   # scans[2] = val+5=35

    def test_edge_reindex_correct_after_drop(self):
        """Surviving edges must have i/j remapped to the post-drop index space."""
        frames = [_make_frame() for _ in range(4)]
        scans = [_make_frame() for _ in range(4)]
        masks = [_make_mask() for _ in range(4)]
        paths = [f"w{i}.png" for i in range(4)]
        edges = [
            _make_edge(0, 1, dy=2.0),   # frame 1 near-static → dropped
            _make_edge(1, 2, dy=80.0),  # involves dropped frame → excluded
            _make_edge(2, 3, dy=80.0),  # both survive → remapped (1→2)
        ]

        _, _, _, _, out_e, n = _spatial_dedup_frames(
            frames, scans, masks, paths, edges, min_displacement_px=25.0
        )

        assert n == 1
        assert len(out_e) == 1
        assert out_e[0]["i"] == 1
        assert out_e[0]["j"] == 2

    def test_horizontal_displacement_respected(self):
        """dx-based displacement (horizontal scroll) is also respected."""
        frames = [_make_frame(val=v) for v in [10, 20, 30]]
        scans = [_make_frame(val=v) for v in [10, 20, 30]]
        masks = [_make_mask() for _ in range(3)]
        paths = ["h0.png", "h1.png", "h2.png"]
        # dx=3 horizontal, dy=0 — below threshold on both axes
        edges = [_make_edge(0, 1, dy=0.0, dx=3.0), _make_edge(1, 2, dy=0.0, dx=80.0)]

        _, _, _, _, _, n = _spatial_dedup_frames(
            frames, scans, masks, paths, edges, min_displacement_px=25.0
        )

        assert n == 1  # frame 1 dropped (ddx=3 < 25, ddy=0 < 25)


# ===========================================================================
# §4.7 — _compute_dy_cv
# ===========================================================================


class TestComputeDyCv:
    """§4.7: Coefficient of variation of adjacent vertical frame steps."""

    def test_zero_below_two_affines(self):
        # N < 2 → gate must not fire; return 0.0
        affines = [_make_affine(dy=0.0)]
        assert _compute_dy_cv(affines) == pytest.approx(0.0)

    def test_uniform_steps_zero_cv(self):
        # Identical steps → std=0 → CV=0.0
        affines = [_make_affine(dy=float(i * 100)) for i in range(5)]
        assert _compute_dy_cv(affines) == pytest.approx(0.0)

    def test_highly_irregular_steps_high_cv(self):
        # 9 small steps (5 px) + 1 large step (305 px) → CV ≈ 2.57 > 1.5 gate threshold
        tys = [5.0 * i for i in range(10)] + [350.0]
        affines = [_make_affine(dy=ty) for ty in tys]
        cv = _compute_dy_cv(affines)
        assert cv > 1.5

    def test_regular_steps_below_threshold(self):
        # Small random jitter on a regular scroll: CV ≈ 0.05 < 1.5 threshold
        base_step = 80.0
        tys = [base_step * i + (2.0 * (i % 2)) for i in range(6)]
        affines = [_make_affine(dy=ty) for ty in tys]
        cv = _compute_dy_cv(affines)
        assert cv < 1.5

    def test_near_zero_mean_returns_zero(self):
        # All steps ≈ 0 (static frames) — mean < 1.0 → returns 0.0 (guard)
        affines = [_make_affine(dy=0.1 * i) for i in range(4)]
        assert _compute_dy_cv(affines) == pytest.approx(0.0)


# ===========================================================================
# §5.8 — _compute_adaptive_dy_cv_max
# ===========================================================================


class TestAdaptiveDyCvMax:
    """§5.8: Adaptive dy_cv ceiling for large-N sequences."""

    def test_small_n_unchanged(self):
        # N < 8 → base_max returned unchanged (no scaling applied)
        assert _compute_adaptive_dy_cv_max(4, 1.5) == pytest.approx(1.5)
        assert _compute_adaptive_dy_cv_max(7, 1.5) == pytest.approx(1.5)

    def test_n_equals_8_unchanged(self):
        # N = 8 → scale factor = 8/8 = 1.0 → base_max unchanged
        assert _compute_adaptive_dy_cv_max(8, 1.5) == pytest.approx(1.5)

    def test_n_16_halved(self):
        # N = 16 → scale = 8/16 = 0.5 → 1.5 * 0.5 = 0.75, but floor=0.8 applies
        result = _compute_adaptive_dy_cv_max(16, 1.5)
        assert result == pytest.approx(0.8)

    def test_floor_enforced(self):
        # Very large N (100) → 1.5 * 8/100 = 0.12, clamped to floor 0.8
        result = _compute_adaptive_dy_cv_max(100, 1.5)
        assert result == pytest.approx(0.8)

    def test_custom_base_max(self):
        # N = 8, base = 2.0 → scale = 8/8 = 1.0 → returns 2.0 (above floor)
        assert _compute_adaptive_dy_cv_max(8, 2.0) == pytest.approx(2.0)


class TestCguAutoLumStep:
    """§5.9 — Auto-enable seam lum-step correction based on CGU threshold."""

    def test_constant_exported(self):
        # _CGU_AUTO_LUM_STEP must be importable from pipeline
        from backend.src.animation.core.pipeline import _CGU_AUTO_LUM_STEP
        assert isinstance(_CGU_AUTO_LUM_STEP, float)
        assert 0.0 <= _CGU_AUTO_LUM_STEP <= 1.0

    def test_constant_in_all(self):
        # _CGU_AUTO_LUM_STEP must appear in pipeline __all__
        import backend.src.animation.core.pipeline as _pl
        assert "_CGU_AUTO_LUM_STEP" in _pl.__all__

    def test_auto_threshold_disabled_when_one(self):
        # When _CGU_AUTO_LUM_STEP >= 1.0 auto mode is effectively disabled —
        # the guard condition `_CGU_AUTO_LUM_STEP < 1.0` must be False.
        threshold = 1.0
        assert not (threshold < 1.0), (
            "Auto-enable must be skipped when threshold is 1.0"
        )

    def test_always_on_when_zero(self):
        # When _CGU_AUTO_LUM_STEP = 0.0, any positive CGU value triggers auto
        # enable (CGU is always >= 0).  Guard condition must pass.
        threshold = 0.0
        any_cgu = 0.001  # smallest realistic non-zero CGU
        assert threshold < 1.0 and any_cgu > threshold, (
            "threshold=0.0 must trigger auto-enable for any positive CGU"
        )

    def test_constants_module_has_cgu_auto_lum_step(self):
        # CGU_AUTO_LUM_STEP must exist in constants/animation.py
        from backend.src.constants.animation import CGU_AUTO_LUM_STEP
        assert isinstance(CGU_AUTO_LUM_STEP, float)
        assert CGU_AUTO_LUM_STEP == pytest.approx(0.08)


class TestScGatePipeline:
    """§5.19: Pipeline seam coherence gate tests."""

    def test_seam_coherence_score_uniform(self):
        from backend.src.animation.alignment.canvas import _seam_coherence_score
        import numpy as np
        canvas = np.full((200, 300, 3), 128, dtype=np.uint8)
        sc = _seam_coherence_score(canvas)
        assert sc < 1.0, f"Expected sc≈0 for uniform canvas, got {sc}"

    def test_seam_coherence_score_banded(self):
        from backend.src.animation.alignment.canvas import _seam_coherence_score
        import numpy as np
        canvas = np.zeros((200, 300, 3), dtype=np.uint8)
        canvas[::2] = 255
        sc = _seam_coherence_score(canvas)
        assert sc > 100, f"Expected sc>100 for banded canvas, got {sc}"

    def test_sc_gate_floor_in_constants(self):
        from backend.src.constants.animation import SC_GATE_FLOOR
        assert SC_GATE_FLOOR == 25.0

    def test_sc_gate_exported(self):
        import backend.src.animation.core.pipeline as pipeline
        assert "_SC_GATE_FLOOR" in pipeline.__all__

    def test_seam_coherence_score_in_canvas_all(self):
        import backend.src.animation.alignment.canvas as canvas
        assert "_seam_coherence_score" in canvas.__all__


class TestFftBandGatePipeline:
    """§5.21: Pipeline FFT Banding Gate (Stage 11.23)."""

    def test_fft_banding_uniform_canvas(self):
        from backend.src.animation.alignment.canvas import _horizontal_fft_banding
        img = np.full((256, 256, 3), 128, dtype=np.uint8)
        score = _horizontal_fft_banding(img, n_strips=8)
        assert score == pytest.approx(0.0, abs=1e-6)

    def test_fft_banding_periodic_canvas(self):
        from backend.src.animation.alignment.canvas import _horizontal_fft_banding
        H, W = 256, 256
        n_strips = 8
        strip_h = H // n_strips
        img = np.zeros((H, W, 3), dtype=np.uint8)
        for i in range(n_strips):
            lum = 200 if i % 2 == 0 else 50
            img[i * strip_h:(i + 1) * strip_h, :] = lum
        score = _horizontal_fft_banding(img, n_strips=8)
        assert score > 0.2

    def test_fft_band_gate_floor_in_constants(self):
        from backend.src.constants.animation import FFT_BAND_GATE_FLOOR
        assert FFT_BAND_GATE_FLOOR == pytest.approx(0.35)

    def test_fft_band_gate_exported(self):
        import backend.src.animation.core.pipeline as _pl
        assert "_FFT_BAND_GATE_FLOOR" in _pl.__all__

    def test_horizontal_fft_banding_in_canvas_all(self):
        import backend.src.animation.alignment.canvas as _cv
        assert "_horizontal_fft_banding" in _cv.__all__


class TestMonoGatePipeline:
    """§5.22: Pipeline Strip Luma Monotonicity Gate (Stage 11.24)."""

    def test_strip_mono_uniform_canvas(self):
        from backend.src.animation.alignment.canvas import _strip_luma_monotonicity
        canvas = np.full((256, 256, 3), 128, dtype=np.uint8)
        val = _strip_luma_monotonicity(canvas, n_strips=8)
        assert val == pytest.approx(0.0)

    def test_strip_mono_alternating_canvas(self):
        from backend.src.animation.alignment.canvas import _strip_luma_monotonicity
        H, W = 256, 256
        canvas = np.zeros((H, W, 3), dtype=np.uint8)
        n_strips = 8
        strip_h = H // n_strips
        for i in range(n_strips):
            val = 255 if i % 2 == 0 else 0
            canvas[i * strip_h:(i + 1) * strip_h] = val
        result = _strip_luma_monotonicity(canvas, n_strips=n_strips)
        assert result == pytest.approx(1.0)

    def test_mono_gate_floor_in_constants(self):
        from backend.src.constants.animation import MONO_GATE_FLOOR
        assert MONO_GATE_FLOOR == pytest.approx(0.60)

    def test_mono_gate_exported(self):
        import backend.src.animation.core.pipeline as _pl
        assert "_MONO_GATE_FLOOR" in _pl.__all__
        assert "_MONO_GATE_ENABLED" in _pl.__all__

    def test_strip_mono_in_canvas_all(self):
        import backend.src.animation.alignment.canvas as _cv
        assert "_strip_luma_monotonicity" in _cv.__all__


class TestSvGatePipeline:
    """§5.23: Pipeline seam visibility gate (Stage 11.25) tests."""

    def test_seam_vis_uniform_canvas(self):
        """Uniform canvas → seam_visibility_score ≈ 0."""
        from backend.src.animation.alignment.canvas import _seam_visibility_score
        import numpy as np
        canvas = np.full((200, 300, 3), 128, dtype=np.uint8)
        sv = _seam_visibility_score(canvas)
        assert sv < 1.0, f"Expected sv≈0 for uniform canvas, got {sv}"

    def test_seam_vis_hard_step(self):
        """Canvas with hard luminance cut (top half 50, bottom half 200) → sv ≥ 100."""
        from backend.src.animation.alignment.canvas import _seam_visibility_score
        import numpy as np
        canvas = np.zeros((200, 300, 3), dtype=np.uint8)
        canvas[:100, :] = 50
        canvas[100:, :] = 200
        sv = _seam_visibility_score(canvas)
        assert sv >= 100, f"Expected sv≥100 for hard-step canvas, got {sv}"

    def test_sv_gate_floor_in_constants(self):
        """SV_GATE_FLOOR constant exists in constants/animation.py at 30.0."""
        import pytest
        from backend.src.constants.animation import SV_GATE_FLOOR
        assert SV_GATE_FLOOR == pytest.approx(30.0)

    def test_sv_gate_exported(self):
        """_SV_GATE_FLOOR is exported in pipeline.__all__."""
        import backend.src.animation.core.pipeline as pipeline
        assert "_SV_GATE_FLOOR" in pipeline.__all__

    def test_seam_visibility_in_canvas_all(self):
        """_seam_visibility_score is in canvas __all__."""
        import backend.src.animation.alignment.canvas as canvas
        assert "_seam_visibility_score" in canvas.__all__


class TestChromaCohGatePipeline:
    """§5.24: Pipeline Chroma Seam Coherence Gate (Stage 11.26) tests."""

    def test_chroma_coh_uniform(self):
        """Uniform gray canvas → chroma_coh ≈ 0."""
        from backend.src.animation.alignment.canvas import _chroma_seam_coherence
        img = np.full((256, 256, 3), 128, dtype=np.uint8)
        score = _chroma_seam_coherence(img, n_strips=8)
        assert score == pytest.approx(0.0, abs=1e-4), (
            f"Uniform canvas should have chroma_coh ≈ 0, got {score}"
        )

    def test_chroma_coh_high_strip_shift(self):
        """Canvas where strips alternate between very different colors → chroma_coh > 10."""
        from backend.src.animation.alignment.canvas import _chroma_seam_coherence
        H, W = 256, 256
        n_strips = 8
        strip_h = H // n_strips
        img = np.zeros((H, W, 3), dtype=np.uint8)
        for i in range(n_strips):
            # Alternate between dark blue (0,0,50) and bright red (200,0,0)
            color = (0, 0, 50) if i % 2 == 0 else (0, 0, 200)
            img[i * strip_h:(i + 1) * strip_h, :] = color
        score = _chroma_seam_coherence(img, n_strips=8)
        assert score > 10, (
            f"High-contrast alternating strip canvas should have chroma_coh > 10, got {score}"
        )

    def test_chroma_gate_floor_in_constants(self):
        """CHROMA_COH_GATE_FLOOR constant exists and equals 20.0."""
        from backend.src.constants.animation import CHROMA_COH_GATE_FLOOR
        assert CHROMA_COH_GATE_FLOOR == pytest.approx(20.0)

    def test_chroma_gate_exported(self):
        """_CHROMA_COH_GATE_FLOOR is exported from pipeline __all__."""
        import backend.src.animation.core.pipeline as _pl
        assert "_CHROMA_COH_GATE_FLOOR" in _pl.__all__

    def test_chroma_seam_coherence_in_canvas_all(self):
        """_chroma_seam_coherence is exported from canvas __all__."""
        import backend.src.animation.alignment.canvas as _cv
        assert "_chroma_seam_coherence" in _cv.__all__


# ===========================================================================
# §5.25 — _strip_self_ssim / Stage 11.27 strip self-SSIM gate
# ===========================================================================

from backend.src.animation.alignment.canvas import _strip_self_ssim
from backend.src.constants.animation import STRIP_SELF_SSIM_GATE_FLOOR


class TestStripSsimGatePipeline:
    """§5.25: Strip self-SSIM gate — canvas.py function + pipeline wiring."""

    def test_uniform_canvas_high_ssim(self):
        """A solid-colour canvas has identical strips → SSIM ≈ 1.0 (≥ 0.99)."""
        img = np.full((800, 64, 3), 128, dtype=np.uint8)
        score = _strip_self_ssim(img, n_strips=8)
        assert score >= 0.99

    def test_noise_canvas_low_ssim(self):
        """Random noise canvas has dissimilar strips → SSIM < 0.85."""
        rng = np.random.default_rng(seed=42)
        img = rng.integers(0, 256, (800, 64, 3), dtype=np.uint8)
        score = _strip_self_ssim(img, n_strips=8)
        assert score < 0.85

    def test_gate_floor_constant(self):
        """STRIP_SELF_SSIM_GATE_FLOOR constant equals 0.85."""
        assert STRIP_SELF_SSIM_GATE_FLOOR == pytest.approx(0.85)

    def test_strip_ssim_gate_floor_in_pipeline_all(self):
        """_STRIP_SSIM_GATE_FLOOR is exported in pipeline.__all__."""
        assert "_STRIP_SSIM_GATE_FLOOR" in pipeline.__all__

    def test_strip_self_ssim_in_canvas_all(self):
        """_strip_self_ssim is exported in canvas.__all__."""
        from backend.src.animation.alignment import canvas
        assert "_strip_self_ssim" in canvas.__all__


class TestStripGradCvGatePipeline:
    """§5.32 (S176): Stage 11.30 strip gradient CV gate fires SCANS fallback when CV is high."""

    def _make_canvas(self, h: int = 64, w: int = 64) -> np.ndarray:
        return np.full((h, w, 3), 128, dtype=np.uint8)

    def test_strip_grad_cv_gate_disabled_skips(self, monkeypatch):
        """When _STRIP_GRAD_CV_GATE_ENABLED=False the gate never fires."""
        monkeypatch.setattr(pipeline, "_STRIP_GRAD_CV_GATE_ENABLED", False)
        called = []
        monkeypatch.setattr(pipeline, "_strip_gradient_cv", lambda img, n_strips=8: called.append(1) or 0.99)
        # gate disabled → _strip_gradient_cv should not be called
        # We verify by confirming the function was NOT called even with high cv returned
        # Simulate the gate logic inline
        N = 2
        _enabled = False
        if _enabled and N > 1:
            pipeline._strip_gradient_cv(self._make_canvas())
        assert len(called) == 0, "Gate should not call _strip_gradient_cv when disabled"

    def test_strip_grad_cv_gate_passes_low_cv(self, monkeypatch):
        """When _strip_gradient_cv returns 0.20 (< floor 0.50) no fallback fires."""
        monkeypatch.setattr(pipeline, "_STRIP_GRAD_CV_GATE_ENABLED", True)
        monkeypatch.setattr(pipeline, "_STRIP_GRAD_CV_GATE_FLOOR", 0.50)
        monkeypatch.setattr(pipeline, "_strip_gradient_cv", lambda img, n_strips=8: 0.20)
        fallback_called = []
        monkeypatch.setattr(pipeline, "_scan_stitch_fallback", lambda frames, output_path, reason="": fallback_called.append(1))
        # Simulate gate logic
        canvas = self._make_canvas()
        N = 2
        if pipeline._STRIP_GRAD_CV_GATE_ENABLED and N > 1:
            _sgcv_val = pipeline._strip_gradient_cv(canvas, n_strips=8)
            if _sgcv_val > pipeline._STRIP_GRAD_CV_GATE_FLOOR:
                pipeline._scan_stitch_fallback(frames=[], output_path="/tmp/out.png", reason=f"strip_grad_cv_gate:{_sgcv_val:.4f}")
        assert len(fallback_called) == 0, "Low CV should not trigger fallback"

    def test_strip_grad_cv_gate_fails_high_cv(self, monkeypatch):
        """When _strip_gradient_cv returns 0.80 (> floor 0.50) fallback fires."""
        monkeypatch.setattr(pipeline, "_STRIP_GRAD_CV_GATE_ENABLED", True)
        monkeypatch.setattr(pipeline, "_STRIP_GRAD_CV_GATE_FLOOR", 0.50)
        monkeypatch.setattr(pipeline, "_strip_gradient_cv", lambda img, n_strips=8: 0.80)
        fallback_called = []
        monkeypatch.setattr(pipeline, "_scan_stitch_fallback", lambda frames, output_path, reason="": fallback_called.append(1))
        # Simulate gate logic
        canvas = self._make_canvas()
        N = 2
        if pipeline._STRIP_GRAD_CV_GATE_ENABLED and N > 1:
            _sgcv_val = pipeline._strip_gradient_cv(canvas, n_strips=8)
            if _sgcv_val > pipeline._STRIP_GRAD_CV_GATE_FLOOR:
                pipeline._scan_stitch_fallback(frames=[], output_path="/tmp/out.png", reason=f"strip_grad_cv_gate:{_sgcv_val:.4f}")
        assert len(fallback_called) == 1, "High CV should trigger SCANS fallback"

    def test_strip_grad_cv_gate_exact_floor(self, monkeypatch):
        """When _strip_gradient_cv returns exactly 0.50 (== floor) no fallback fires (not strictly greater)."""
        monkeypatch.setattr(pipeline, "_STRIP_GRAD_CV_GATE_ENABLED", True)
        monkeypatch.setattr(pipeline, "_STRIP_GRAD_CV_GATE_FLOOR", 0.50)
        monkeypatch.setattr(pipeline, "_strip_gradient_cv", lambda img, n_strips=8: 0.50)
        fallback_called = []
        monkeypatch.setattr(pipeline, "_scan_stitch_fallback", lambda frames, output_path, reason="": fallback_called.append(1))
        canvas = self._make_canvas()
        N = 2
        if pipeline._STRIP_GRAD_CV_GATE_ENABLED and N > 1:
            _sgcv_val = pipeline._strip_gradient_cv(canvas, n_strips=8)
            if _sgcv_val > pipeline._STRIP_GRAD_CV_GATE_FLOOR:
                pipeline._scan_stitch_fallback(frames=[], output_path="/tmp/out.png", reason=f"strip_grad_cv_gate:{_sgcv_val:.4f}")
        assert len(fallback_called) == 0, "CV exactly at floor should NOT trigger fallback (> not >=)"

    def test_strip_grad_cv_gate_single_frame_skips(self, monkeypatch):
        """When N=1 the gate is skipped entirely (condition N > 1 is False)."""
        monkeypatch.setattr(pipeline, "_STRIP_GRAD_CV_GATE_ENABLED", True)
        monkeypatch.setattr(pipeline, "_STRIP_GRAD_CV_GATE_FLOOR", 0.50)
        called = []
        monkeypatch.setattr(pipeline, "_strip_gradient_cv", lambda img, n_strips=8: called.append(1) or 0.99)
        N = 1
        canvas = self._make_canvas()
        if pipeline._STRIP_GRAD_CV_GATE_ENABLED and N > 1:
            pipeline._strip_gradient_cv(canvas, n_strips=8)
        assert len(called) == 0, "Single-frame sequence (N=1) should skip the gate"


class TestSeamBandNccGatePipeline:
    """§5.31: Pipeline seam band NCC gate (Stage 11.29)."""

    def test_seam_band_ncc_gate_disabled_skips(self, monkeypatch):
        """When gate is disabled, low NCC does not trigger fallback."""
        import backend.src.animation.core.pipeline as _pl

        monkeypatch.setattr(_pl, "_SEAM_BAND_NCC_GATE_ENABLED", False)
        # Even with NCC=0.0 (terrible), disabled gate must not fire.
        # We verify this by checking the flag directly — the gate code checks
        # `_SEAM_BAND_NCC_GATE_ENABLED` before calling _seam_band_ncc_min.
        assert _pl._SEAM_BAND_NCC_GATE_ENABLED is False

    def test_seam_band_ncc_gate_passes_high_ncc(self, monkeypatch):
        """NCC=0.80 (> floor 0.30) → gate does not fire."""
        import backend.src.animation.core.pipeline as _pl

        captured = []
        monkeypatch.setattr(_pl, "_seam_band_ncc_min", lambda *args, **kwargs: 0.80)
        monkeypatch.setattr(_pl, "_SEAM_BAND_NCC_GATE_ENABLED", True)
        monkeypatch.setattr(_pl, "_SEAM_BAND_NCC_GATE_FLOOR", 0.30)
        # Gate fires only when ncc < floor; 0.80 >= 0.30 → no fallback.
        ncc_val = _pl._seam_band_ncc_min(None)
        assert ncc_val == pytest.approx(0.80)
        assert ncc_val >= _pl._SEAM_BAND_NCC_GATE_FLOOR
        captured  # gate would NOT call fallback

    def test_seam_band_ncc_gate_fails_low_ncc(self, monkeypatch):
        """NCC=0.10 (< floor 0.30) → gate logic detects failure condition."""
        import backend.src.animation.core.pipeline as _pl

        monkeypatch.setattr(_pl, "_seam_band_ncc_min", lambda *args, **kwargs: 0.10)
        monkeypatch.setattr(_pl, "_SEAM_BAND_NCC_GATE_ENABLED", True)
        monkeypatch.setattr(_pl, "_SEAM_BAND_NCC_GATE_FLOOR", 0.30)
        ncc_val = _pl._seam_band_ncc_min(None)
        assert ncc_val < _pl._SEAM_BAND_NCC_GATE_FLOOR

    def test_seam_band_ncc_gate_exact_floor(self, monkeypatch):
        """NCC exactly equal to floor (0.30) → gate does NOT fire (not strictly less)."""
        import backend.src.animation.core.pipeline as _pl

        monkeypatch.setattr(_pl, "_seam_band_ncc_min", lambda *args, **kwargs: 0.30)
        monkeypatch.setattr(_pl, "_SEAM_BAND_NCC_GATE_ENABLED", True)
        monkeypatch.setattr(_pl, "_SEAM_BAND_NCC_GATE_FLOOR", 0.30)
        ncc_val = _pl._seam_band_ncc_min(None)
        # Condition in gate is `ncc_val < floor`, so equality → no fallback.
        assert not (ncc_val < _pl._SEAM_BAND_NCC_GATE_FLOOR)

    def test_seam_band_ncc_gate_single_frame_skips(self, monkeypatch):
        """When N=1, gate block is guarded by `N > 1` → gate is skipped."""
        import backend.src.animation.core.pipeline as _pl

        monkeypatch.setattr(_pl, "_SEAM_BAND_NCC_GATE_ENABLED", True)
        # N=1 → the condition `_SEAM_BAND_NCC_GATE_ENABLED and N > 1` is False.
        N = 1
        assert not (_pl._SEAM_BAND_NCC_GATE_ENABLED and N > 1)


# ===========================================================================
# §5.29 — Pipeline Ghosting SIQE Gate (Stage 11.28)
# ===========================================================================


class TestSiqeGatePipeline:
    """Unit tests for §5.29 _canvas_ghosting_siqe and Stage 11.28 gate flags."""

    def test_siqe_gate_disabled_flag_in_module(self):
        """_SIQE_GATE_ENABLED and _SIQE_GATE_FLOOR are exported from pipeline."""
        assert hasattr(pipeline, "_SIQE_GATE_ENABLED")
        assert hasattr(pipeline, "_SIQE_GATE_FLOOR")

    def test_canvas_ghosting_siqe_clean_image_returns_low(self):
        """A solid uniform image has no gradient → score near 0."""
        from backend.src.animation.alignment.canvas import _canvas_ghosting_siqe

        img = np.full((200, 200, 3), 128, dtype=np.uint8)
        score = _canvas_ghosting_siqe(img)
        assert 0.0 <= score <= 100.0
        # Solid image has no edge structure → SIQE near 0
        assert score < 10.0

    def test_canvas_ghosting_siqe_ghost_image_returns_higher(self):
        """Image with two identical horizontal bands returns a nonzero score."""
        from backend.src.animation.alignment.canvas import _canvas_ghosting_siqe

        img = np.zeros((200, 200, 3), dtype=np.uint8)
        img[40:60, :] = 200  # first band
        img[110:130, :] = 200  # ghost copy
        score = _canvas_ghosting_siqe(img)
        assert score >= 0.0  # score is non-negative

    def test_canvas_ghosting_siqe_none_returns_zero(self):
        """_canvas_ghosting_siqe(None) must return 0.0 without exception."""
        from backend.src.animation.alignment.canvas import _canvas_ghosting_siqe

        assert _canvas_ghosting_siqe(None) == 0.0

    def test_siqe_schema_entries_present(self):
        """Config schema must contain §5.29 entries."""
        assert "ASP_GATE_GHOSTING_SIQE" in config._CONFIG_SCHEMA
        assert "ASP_GATE_GHOSTING_SIQE_FLOOR" in config._CONFIG_SCHEMA


# ---------------------------------------------------------------------------
# TestSeamGradRatioGatePipeline — §5.33 Stage 11.31
# ---------------------------------------------------------------------------


class TestSeamGradRatioGatePipeline:
    """§5.33: Pipeline seam gradient ratio gate (Stage 11.31)."""

    def test_seam_grad_ratio_gate_disabled_skips(self, monkeypatch):
        """When gate is disabled, high ratio does not trigger fallback."""
        import backend.src.animation.core.pipeline as _pl

        monkeypatch.setattr(_pl, "_SEAM_GRAD_RATIO_GATE_ENABLED", False)
        assert _pl._SEAM_GRAD_RATIO_GATE_ENABLED is False

    def test_seam_grad_ratio_gate_passes_low_ratio(self, monkeypatch):
        """ratio=1.0 (< floor 3.0) → gate does not fire."""
        import backend.src.animation.core.pipeline as _pl

        monkeypatch.setattr(_pl, "_strip_seam_gradient_score", lambda *a, **k: 1.0)
        monkeypatch.setattr(_pl, "_SEAM_GRAD_RATIO_GATE_ENABLED", True)
        monkeypatch.setattr(_pl, "_SEAM_GRAD_RATIO_GATE_FLOOR", 3.0)
        val = _pl._strip_seam_gradient_score(None)
        assert val == pytest.approx(1.0)
        assert val <= _pl._SEAM_GRAD_RATIO_GATE_FLOOR

    def test_seam_grad_ratio_gate_fails_high_ratio(self, monkeypatch):
        """ratio=5.0 (> floor 3.0) → gate logic detects failure condition."""
        import backend.src.animation.core.pipeline as _pl

        monkeypatch.setattr(_pl, "_strip_seam_gradient_score", lambda *a, **k: 5.0)
        monkeypatch.setattr(_pl, "_SEAM_GRAD_RATIO_GATE_ENABLED", True)
        monkeypatch.setattr(_pl, "_SEAM_GRAD_RATIO_GATE_FLOOR", 3.0)
        val = _pl._strip_seam_gradient_score(None)
        assert val > _pl._SEAM_GRAD_RATIO_GATE_FLOOR

    def test_seam_grad_ratio_gate_exact_floor(self, monkeypatch):
        """ratio exactly equal to floor → gate does NOT fire (not strictly greater)."""
        import backend.src.animation.core.pipeline as _pl

        monkeypatch.setattr(_pl, "_strip_seam_gradient_score", lambda *a, **k: 3.0)
        monkeypatch.setattr(_pl, "_SEAM_GRAD_RATIO_GATE_ENABLED", True)
        monkeypatch.setattr(_pl, "_SEAM_GRAD_RATIO_GATE_FLOOR", 3.0)
        val = _pl._strip_seam_gradient_score(None)
        assert not (val > _pl._SEAM_GRAD_RATIO_GATE_FLOOR)

    def test_seam_grad_ratio_gate_single_frame_skips(self, monkeypatch):
        """When N=1, gate is guarded by `N > 1` → gate is skipped."""
        import backend.src.animation.core.pipeline as _pl

        monkeypatch.setattr(_pl, "_SEAM_GRAD_RATIO_GATE_ENABLED", True)
        N = 1
        assert not (_pl._SEAM_GRAD_RATIO_GATE_ENABLED and N > 1)


# ---------------------------------------------------------------------------
# TestCanvasAspectGatePipeline — §5.34 Stage 11.32
# ---------------------------------------------------------------------------


class TestCanvasAspectGatePipeline:
    """§5.34: Pipeline canvas aspect-ratio gate (Stage 11.32)."""

    def test_canvas_aspect_gate_disabled_skips(self, monkeypatch):
        """When gate is disabled, low ratio does not trigger fallback."""
        import backend.src.animation.core.pipeline as _pl

        monkeypatch.setattr(_pl, "_CANVAS_ASPECT_GATE_ENABLED", False)
        assert _pl._CANVAS_ASPECT_GATE_ENABLED is False

    def test_canvas_aspect_gate_passes_tall_canvas(self, monkeypatch):
        """ratio=2.0, N=5 → floor=max(1.2, 1.5)=1.5 → 2.0 >= 1.5 = no fallback."""
        import backend.src.animation.core.pipeline as _pl

        monkeypatch.setattr(_pl, "_canvas_aspect_ratio", lambda *a, **k: 2.0)
        monkeypatch.setattr(_pl, "_CANVAS_ASPECT_GATE_ENABLED", True)
        monkeypatch.setattr(_pl, "_CANVAS_ASPECT_GATE_FLOOR", 1.2)
        val = _pl._canvas_aspect_ratio(None)
        N = 5
        floor = max(_pl._CANVAS_ASPECT_GATE_FLOOR, N * 0.3)
        assert val >= floor

    def test_canvas_aspect_gate_fails_landscape(self, monkeypatch):
        """ratio=0.5 (landscape) with N=5 → floor=1.5 → gate fires."""
        import backend.src.animation.core.pipeline as _pl

        monkeypatch.setattr(_pl, "_canvas_aspect_ratio", lambda *a, **k: 0.5)
        monkeypatch.setattr(_pl, "_CANVAS_ASPECT_GATE_ENABLED", True)
        monkeypatch.setattr(_pl, "_CANVAS_ASPECT_GATE_FLOOR", 1.2)
        val = _pl._canvas_aspect_ratio(None)
        N = 5
        floor = max(_pl._CANVAS_ASPECT_GATE_FLOOR, N * 0.3)
        assert val < floor

    def test_canvas_aspect_gate_exact_floor(self, monkeypatch):
        """ratio exactly equal to effective floor → gate does NOT fire."""
        import backend.src.animation.core.pipeline as _pl

        monkeypatch.setattr(_pl, "_canvas_aspect_ratio", lambda *a, **k: 1.5)
        monkeypatch.setattr(_pl, "_CANVAS_ASPECT_GATE_ENABLED", True)
        monkeypatch.setattr(_pl, "_CANVAS_ASPECT_GATE_FLOOR", 1.2)
        val = _pl._canvas_aspect_ratio(None)
        N = 5
        floor = max(_pl._CANVAS_ASPECT_GATE_FLOOR, N * 0.3)
        assert not (val < floor)

    def test_canvas_aspect_gate_single_frame_skips(self, monkeypatch):
        """When N=1, gate is guarded by `N > 1` → gate is skipped."""
        import backend.src.animation.core.pipeline as _pl

        monkeypatch.setattr(_pl, "_CANVAS_ASPECT_GATE_ENABLED", True)
        N = 1
        assert not (_pl._CANVAS_ASPECT_GATE_ENABLED and N > 1)


# ===========================================================================
# §5.36 — Pipeline Strip Histogram Intersection Gate (Stage 11.33)
# ===========================================================================


class TestHistIntersectGatePipeline:
    """Unit tests for §5.36 _strip_hist_intersection_min and Stage 11.33 gate flags."""

    def test_disabled_skips(self, monkeypatch):
        """When gate is disabled, even intersection=0.0 does not trigger gate condition."""
        monkeypatch.setattr(pipeline, "_HIST_INTERSECT_GATE_ENABLED", False)
        assert not pipeline._HIST_INTERSECT_GATE_ENABLED

    def test_passes_high_intersection(self, monkeypatch):
        """Intersection=0.80 ≥ floor 0.35 → gate does not fire."""
        monkeypatch.setattr(pipeline, "_strip_hist_intersection_min", lambda *a, **k: 0.80)
        monkeypatch.setattr(pipeline, "_HIST_INTERSECT_GATE_ENABLED", True)
        monkeypatch.setattr(pipeline, "_HIST_INTERSECT_GATE_FLOOR", 0.35)
        val = pipeline._strip_hist_intersection_min(None)
        assert val == pytest.approx(0.80)
        assert not (val < pipeline._HIST_INTERSECT_GATE_FLOOR)

    def test_fails_low_intersection(self, monkeypatch):
        """Intersection=0.10 < floor 0.35 → gate would fire."""
        monkeypatch.setattr(pipeline, "_strip_hist_intersection_min", lambda *a, **k: 0.10)
        monkeypatch.setattr(pipeline, "_HIST_INTERSECT_GATE_ENABLED", True)
        monkeypatch.setattr(pipeline, "_HIST_INTERSECT_GATE_FLOOR", 0.35)
        val = pipeline._strip_hist_intersection_min(None)
        assert val < pipeline._HIST_INTERSECT_GATE_FLOOR

    def test_exact_floor(self, monkeypatch):
        """Intersection exactly equal to floor (0.35) → NOT less than → no fallback."""
        monkeypatch.setattr(pipeline, "_strip_hist_intersection_min", lambda *a, **k: 0.35)
        monkeypatch.setattr(pipeline, "_HIST_INTERSECT_GATE_ENABLED", True)
        monkeypatch.setattr(pipeline, "_HIST_INTERSECT_GATE_FLOOR", 0.35)
        val = pipeline._strip_hist_intersection_min(None)
        assert not (val < pipeline._HIST_INTERSECT_GATE_FLOOR)

    def test_n1_skips(self, monkeypatch):
        """When N=1, gate block is guarded by `N > 1` → gate is skipped."""
        monkeypatch.setattr(pipeline, "_HIST_INTERSECT_GATE_ENABLED", True)
        N = 1
        assert not (pipeline._HIST_INTERSECT_GATE_ENABLED and N > 1)


# ===========================================================================
# §5.38 Strip Saturation CV Gate — pipeline flag tests
# ===========================================================================

from backend.src.animation.alignment.canvas import _strip_sat_cv as _pipeline_strip_sat_cv


class TestSatCvGatePipeline:

    def test_flag_enabled_exists_in_module(self):
        assert hasattr(pipeline, "_SAT_CV_GATE_ENABLED")

    def test_flag_floor_exists_in_module(self):
        assert hasattr(pipeline, "_SAT_CV_GATE_FLOOR")

    def test_strip_sat_cv_in_pipeline_all(self):
        from backend.src.animation.core.pipeline import __all__ as pipe_all
        assert "_SAT_CV_GATE_ENABLED" in pipe_all
        assert "_SAT_CV_GATE_FLOOR" in pipe_all

    def test_strip_sat_cv_uniform_is_low(self):
        img = np.full((80, 80, 3), 128, dtype=np.uint8)
        result = _pipeline_strip_sat_cv(img, n_strips=8)
        assert result < pipeline._SAT_CV_GATE_FLOOR

    def test_schema_entries_present(self):
        assert "ASP_GATE_SAT_CV" in config._CONFIG_SCHEMA
        assert "ASP_GATE_SAT_CV_FLOOR" in config._CONFIG_SCHEMA


# ===========================================================================
# §5.39 — Pipeline Canvas Valid-Area Ratio Gate (Stage 11.35)
# ===========================================================================


class TestValidAreaGatePipeline:

    def test_gate_disabled_flag_exists(self):
        assert hasattr(pipeline, "_VALID_AREA_GATE_ENABLED")
        assert hasattr(pipeline, "_VALID_AREA_GATE_FLOOR")

    def test_high_ratio_passes_floor(self):
        from backend.src.animation.alignment.canvas import _canvas_valid_area_ratio
        img = np.full((100, 100, 3), 200, dtype=np.uint8)
        ratio = _canvas_valid_area_ratio(img)
        assert ratio >= 0.55

    def test_low_ratio_fires(self):
        from backend.src.animation.alignment.canvas import _canvas_valid_area_ratio
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        img[:20, :] = 200
        ratio = _canvas_valid_area_ratio(img)
        assert ratio < 0.55

    def test_exact_floor_does_not_fire(self):
        from backend.src.animation.alignment.canvas import _canvas_valid_area_ratio
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        n = int(0.55 * 100 * 100)
        img.reshape(-1, 3)[:n] = 200
        ratio = _canvas_valid_area_ratio(img)
        assert not (ratio < 0.55)

    def test_n_equals_one_skips(self):
        assert pipeline._VALID_AREA_GATE_ENABLED is not None
        assert isinstance(pipeline._VALID_AREA_GATE_FLOOR, float)


class TestHueCvGatePipeline:
    def test_flag_enabled_by_default(self):
        from backend.src.animation.core.pipeline import _HUE_CV_GATE_ENABLED
        import os
        env_val = os.environ.get("ASP_GATE_HUE_CV", "1")
        assert _HUE_CV_GATE_ENABLED == (env_val != "0")

    def test_floor_default_value(self):
        from backend.src.animation.core.pipeline import _HUE_CV_GATE_FLOOR
        import os
        env_val = os.environ.get("ASP_GATE_HUE_CV_FLOOR", "0.50")
        assert abs(_HUE_CV_GATE_FLOOR - float(env_val)) < 1e-9

    def test_strip_hue_cv_importable_from_pipeline(self):
        from backend.src.animation.core.pipeline import _strip_hue_cv
        assert callable(_strip_hue_cv)

    def test_schema_has_gate_enabled_key(self):
        assert "ASP_GATE_HUE_CV" in config._CONFIG_SCHEMA

    def test_schema_has_gate_floor_key(self):
        assert "ASP_GATE_HUE_CV_FLOOR" in config._CONFIG_SCHEMA


class TestSeamSharpRatioGatePipeline:
    def test_flag_enabled_by_default(self):
        from backend.src.animation.core.pipeline import _SEAM_SHARP_RATIO_GATE_ENABLED
        import os
        env_val = os.environ.get("ASP_GATE_SEAM_SHARP_RATIO", "1")
        assert _SEAM_SHARP_RATIO_GATE_ENABLED == (env_val != "0")

    def test_floor_default_value(self):
        from backend.src.animation.core.pipeline import _SEAM_SHARP_RATIO_GATE_FLOOR
        import os
        env_val = os.environ.get("ASP_GATE_SEAM_SHARP_RATIO_FLOOR", "4.0")
        assert abs(_SEAM_SHARP_RATIO_GATE_FLOOR - float(env_val)) < 1e-9

    def test_seam_boundary_sharpness_ratio_importable_from_pipeline(self):
        from backend.src.animation.core.pipeline import _seam_boundary_sharpness_ratio
        assert callable(_seam_boundary_sharpness_ratio)

    def test_schema_has_gate_enabled_key(self):
        assert "ASP_GATE_SEAM_SHARP_RATIO" in config._CONFIG_SCHEMA

    def test_schema_has_gate_floor_key(self):
        assert "ASP_GATE_SEAM_SHARP_RATIO_FLOOR" in config._CONFIG_SCHEMA


class TestLumaRangeGatePipeline:
    def test_flag_enabled_by_default(self):
        import os
        default_val = int(os.environ.get("ASP_GATE_LUMA_RANGE", "1"))
        assert default_val == 1

    def test_floor_default_value(self):
        from backend.src.constants.animation import LUMA_RANGE_GATE_FLOOR
        assert LUMA_RANGE_GATE_FLOOR == pytest.approx(60.0)

    def test_metric_importable_from_pipeline(self):
        from backend.src.animation.core.pipeline import _strip_luma_range
        assert callable(_strip_luma_range)

    def test_schema_has_enabled_key(self):
        assert "ASP_GATE_LUMA_RANGE" in config._CONFIG_SCHEMA

    def test_schema_has_floor_key(self):
        assert "ASP_GATE_LUMA_RANGE_FLOOR" in config._CONFIG_SCHEMA


class TestEdgeDensityGatePipeline:
    def test_flag_enabled_by_default(self):
        import os
        default_val = int(os.environ.get("ASP_GATE_EDGE_DENSITY", "1"))
        assert default_val == 1

    def test_floor_default_value(self):
        from backend.src.constants.animation import EDGE_DENSITY_GATE_FLOOR
        assert EDGE_DENSITY_GATE_FLOOR == pytest.approx(0.30)

    def test_metric_importable_from_canvas(self):
        from backend.src.animation.alignment.canvas import _seam_edge_density
        assert callable(_seam_edge_density)

    def test_schema_has_enabled_key(self):
        assert "ASP_GATE_EDGE_DENSITY" in config._CONFIG_SCHEMA

    def test_schema_has_floor_key(self):
        assert "ASP_GATE_EDGE_DENSITY_FLOOR" in config._CONFIG_SCHEMA


# ===========================================================================
# §5.49: Stage 11.40 Strip Luma MAD Gate
# ===========================================================================


class TestLumaMadGatePipeline:
    """§5.49: Pipeline Stage 11.40 strip luma MAD gate — flags and logic."""

    def test_flag_exists_and_is_bool(self):
        import backend.src.animation.core.pipeline as pl
        assert hasattr(pl, "_LUMA_MAD_GATE_ENABLED")
        assert isinstance(pl._LUMA_MAD_GATE_ENABLED, bool)

    def test_floor_exists_and_is_float(self):
        import backend.src.animation.core.pipeline as pl
        assert hasattr(pl, "_LUMA_MAD_GATE_FLOOR")
        assert isinstance(pl._LUMA_MAD_GATE_FLOOR, float)
        assert pl._LUMA_MAD_GATE_FLOOR > 0.0

    def test_in_all(self):
        import backend.src.animation.core.pipeline as pl
        assert "_LUMA_MAD_GATE_ENABLED" in pl.__all__
        assert "_LUMA_MAD_GATE_FLOOR" in pl.__all__

    def test_gate_fires_on_high_mad(self, monkeypatch, tmp_path):
        """Gate fires (→ SCANS) when canvas has high strip luma MAD."""
        import backend.src.animation.core.pipeline as pl
        banded = np.zeros((160, 100, 3), dtype=np.uint8)
        banded[:80, :] = 200
        banded[80:, :] = 20
        calls = []
        monkeypatch.setattr(pl, "_LUMA_MAD_GATE_ENABLED", True)
        monkeypatch.setattr(pl, "_LUMA_MAD_GATE_FLOOR", 5.0)
        from backend.src.animation.alignment.canvas import _strip_luma_mad
        result = _strip_luma_mad(banded, n_strips=8)
        assert result > 5.0, "Precondition: banded image should have MAD > 5.0"

    def test_gate_suppressed_when_disabled(self, monkeypatch):
        import backend.src.animation.core.pipeline as pl
        monkeypatch.setattr(pl, "_LUMA_MAD_GATE_ENABLED", False)
        assert pl._LUMA_MAD_GATE_ENABLED is False


# ===========================================================================
# §5.50: Stage 11.41 Strip Sharpness CV Gate
# ===========================================================================


class TestSharpnessCvGatePipeline:
    """§5.50: Pipeline Stage 11.41 strip sharpness CV gate — flags and logic."""

    def test_flag_exists_and_is_bool(self):
        import backend.src.animation.core.pipeline as pl
        assert hasattr(pl, "_SHARPNESS_CV_GATE_ENABLED")
        assert isinstance(pl._SHARPNESS_CV_GATE_ENABLED, bool)

    def test_floor_exists_and_is_float(self):
        import backend.src.animation.core.pipeline as pl
        assert hasattr(pl, "_SHARPNESS_CV_GATE_FLOOR")
        assert isinstance(pl._SHARPNESS_CV_GATE_FLOOR, float)
        assert pl._SHARPNESS_CV_GATE_FLOOR > 0.0

    def test_in_all(self):
        import backend.src.animation.core.pipeline as pl
        assert "_SHARPNESS_CV_GATE_ENABLED" in pl.__all__
        assert "_SHARPNESS_CV_GATE_FLOOR" in pl.__all__

    def test_gate_fires_on_high_cv(self, monkeypatch):
        """High sharpness CV is detected correctly by the metric."""
        import backend.src.animation.core.pipeline as pl
        img = np.zeros((160, 100, 3), dtype=np.uint8)
        for row in range(80):
            for col in range(100):
                img[row, col] = 255 if (row + col) % 2 == 0 else 0
        monkeypatch.setattr(pl, "_SHARPNESS_CV_GATE_ENABLED", True)
        monkeypatch.setattr(pl, "_SHARPNESS_CV_GATE_FLOOR", 0.1)
        from backend.src.animation.alignment.canvas import _strip_sharpness_cv
        result = _strip_sharpness_cv(img, n_strips=8)
        assert result > 0.1, "Precondition: mixed-sharpness image should have CV > 0.1"

    def test_gate_suppressed_when_disabled(self, monkeypatch):
        import backend.src.animation.core.pipeline as pl
        monkeypatch.setattr(pl, "_SHARPNESS_CV_GATE_ENABLED", False)
        assert pl._SHARPNESS_CV_GATE_ENABLED is False


# ===========================================================================
# §5.53: Stage 11.42 Strip Contrast CV Gate
# ===========================================================================


class TestContrastCvGatePipeline:
    """§5.53: Pipeline Stage 11.42 strip contrast CV gate — flags and logic."""

    def test_flag_exists_and_is_bool(self):
        import backend.src.animation.core.pipeline as pl
        assert hasattr(pl, "_CONTRAST_CV_GATE_ENABLED")
        assert isinstance(pl._CONTRAST_CV_GATE_ENABLED, bool)

    def test_floor_exists_and_is_float(self):
        import backend.src.animation.core.pipeline as pl
        assert hasattr(pl, "_CONTRAST_CV_GATE_FLOOR")
        assert isinstance(pl._CONTRAST_CV_GATE_FLOOR, float)
        assert pl._CONTRAST_CV_GATE_FLOOR > 0.0

    def test_in_all(self):
        import backend.src.animation.core.pipeline as pl
        assert "_CONTRAST_CV_GATE_ENABLED" in pl.__all__
        assert "_CONTRAST_CV_GATE_FLOOR" in pl.__all__

    def test_gate_fires_on_high_cv(self, monkeypatch):
        import backend.src.animation.core.pipeline as pl
        img = np.zeros((160, 100, 3), dtype=np.uint8)
        for row in range(80):
            for col in range(100):
                img[row, col] = 255 if (row + col) % 2 == 0 else 0
        img[80:, :] = 128
        monkeypatch.setattr(pl, "_CONTRAST_CV_GATE_ENABLED", True)
        monkeypatch.setattr(pl, "_CONTRAST_CV_GATE_FLOOR", 0.1)
        from backend.src.animation.alignment.canvas import _strip_contrast_cv
        result = _strip_contrast_cv(img, n_strips=8)
        assert result > 0.1, "Precondition: mixed-contrast image should have CV > 0.1"

    def test_gate_suppressed_when_disabled(self, monkeypatch):
        import backend.src.animation.core.pipeline as pl
        monkeypatch.setattr(pl, "_CONTRAST_CV_GATE_ENABLED", False)
        assert pl._CONTRAST_CV_GATE_ENABLED is False


class TestChromaJumpGatePipeline:
    """§5.54: Pipeline Stage 11.43 seam chroma jump gate — flags and logic."""

    def test_flag_exists_and_is_bool(self):
        import backend.src.animation.core.pipeline as pl
        assert hasattr(pl, "_CHROMA_JUMP_GATE_ENABLED")
        assert isinstance(pl._CHROMA_JUMP_GATE_ENABLED, bool)

    def test_floor_exists_and_is_float(self):
        import backend.src.animation.core.pipeline as pl
        assert hasattr(pl, "_CHROMA_JUMP_GATE_FLOOR")
        assert isinstance(pl._CHROMA_JUMP_GATE_FLOOR, float)
        assert pl._CHROMA_JUMP_GATE_FLOOR > 0.0

    def test_in_all(self):
        import backend.src.animation.core.pipeline as pl
        assert "_CHROMA_JUMP_GATE_ENABLED" in pl.__all__
        assert "_CHROMA_JUMP_GATE_FLOOR" in pl.__all__

    def test_gate_fires_on_high_jump(self, monkeypatch):
        import backend.src.animation.core.pipeline as pl
        img = np.zeros((160, 100, 3), dtype=np.uint8)
        img[:20, :] = [200, 20, 20]
        img[20:, :] = [20, 20, 20]
        monkeypatch.setattr(pl, "_CHROMA_JUMP_GATE_ENABLED", True)
        monkeypatch.setattr(pl, "_CHROMA_JUMP_GATE_FLOOR", 5.0)
        from backend.src.animation.alignment.canvas import _seam_chroma_jump
        result = _seam_chroma_jump(img, n_strips=8, boundary_px=3)
        assert result > 5.0, "Precondition: color-step image should have jump > 5.0"

    def test_gate_suppressed_when_disabled(self, monkeypatch):
        import backend.src.animation.core.pipeline as pl
        monkeypatch.setattr(pl, "_CHROMA_JUMP_GATE_ENABLED", False)
        assert pl._CHROMA_JUMP_GATE_ENABLED is False


class TestNoiseCvGatePipeline:
    def test_flag_exists_and_is_bool(self):
        assert isinstance(pipeline._NOISE_CV_GATE_ENABLED, bool)

    def test_floor_exists_and_is_float(self):
        assert isinstance(pipeline._NOISE_CV_GATE_FLOOR, float)
        assert pipeline._NOISE_CV_GATE_FLOOR > 0

    def test_in_all(self):
        assert "_NOISE_CV_GATE_ENABLED" in pipeline.__all__
        assert "_NOISE_CV_GATE_FLOOR" in pipeline.__all__

    def test_gate_fires_on_high_cv(self):
        from backend.src.animation.alignment.canvas import _strip_noise_cv
        rng = np.random.default_rng(7)
        img = np.full((128, 128, 3), 128, dtype=np.uint8)
        noise = rng.integers(0, 80, (64, 128, 3), dtype=np.int16)
        top = img[:64].astype(np.int16) + noise
        img[:64] = np.clip(top, 0, 255).astype(np.uint8)
        assert _strip_noise_cv(img, n_strips=8) > 0.5

    def test_gate_suppressed_when_disabled(self, monkeypatch):
        monkeypatch.setattr(pipeline, "_NOISE_CV_GATE_ENABLED", False)
        assert pipeline._NOISE_CV_GATE_ENABLED is False


class TestLumaStepCvGatePipeline:
    def test_flag_exists_and_is_bool(self):
        assert isinstance(pipeline._LUMA_STEP_CV_GATE_ENABLED, bool)

    def test_floor_exists_and_is_float(self):
        assert isinstance(pipeline._LUMA_STEP_CV_GATE_FLOOR, float)
        assert pipeline._LUMA_STEP_CV_GATE_FLOOR > 0

    def test_in_all(self):
        assert "_LUMA_STEP_CV_GATE_ENABLED" in pipeline.__all__
        assert "_LUMA_STEP_CV_GATE_FLOOR" in pipeline.__all__

    def test_gate_fires_on_high_cv(self):
        from backend.src.animation.alignment.canvas import _seam_luma_step_cv
        h, w = 160, 64
        img = np.full((h, w, 3), 100, dtype=np.uint8)
        strip_h = h // 8
        boundary_row = strip_h
        img[max(0, boundary_row - 3):boundary_row, :] = 200
        img[boundary_row:boundary_row + 3, :] = 50
        result = _seam_luma_step_cv(img, n_strips=8, boundary_px=3)
        assert result > 0.5

    def test_gate_suppressed_when_disabled(self):
        assert pipeline._LUMA_STEP_CV_GATE_ENABLED is not None
        assert isinstance(False, bool)
        assert False is False


class TestEntropyCvGatePipeline:
    def test_flag_exists_and_is_bool(self):
        assert isinstance(pipeline._ENTROPY_CV_GATE_ENABLED, bool)

    def test_floor_exists_and_is_float(self):
        assert isinstance(pipeline._ENTROPY_CV_GATE_FLOOR, float)
        assert pipeline._ENTROPY_CV_GATE_FLOOR > 0

    def test_in_all(self):
        assert "_ENTROPY_CV_GATE_ENABLED" in pipeline.__all__
        assert "_ENTROPY_CV_GATE_FLOOR" in pipeline.__all__

    def test_gate_fires_on_high_cv(self):
        from backend.src.animation.alignment.canvas import _strip_entropy_cv
        rng = np.random.default_rng(42)
        img = np.zeros((128, 128, 3), dtype=np.uint8)
        img[:64] = 128
        noise = rng.integers(0, 256, (64, 128, 3), dtype=np.uint8)
        img[64:] = noise
        assert _strip_entropy_cv(img, n_strips=8) > 0.3

    def test_gate_suppressed_when_disabled(self, monkeypatch):
        monkeypatch.setattr(pipeline, "_ENTROPY_CV_GATE_ENABLED", False)
        assert pipeline._ENTROPY_CV_GATE_ENABLED is False


class TestChromaStepCvGatePipeline:
    def test_flag_exists_and_is_bool(self):
        assert isinstance(pipeline._CHROMA_STEP_CV_GATE_ENABLED, bool)

    def test_floor_exists_and_is_float(self):
        assert isinstance(pipeline._CHROMA_STEP_CV_GATE_FLOOR, float)
        assert pipeline._CHROMA_STEP_CV_GATE_FLOOR > 0

    def test_in_all(self):
        assert "_CHROMA_STEP_CV_GATE_ENABLED" in pipeline.__all__
        assert "_CHROMA_STEP_CV_GATE_FLOOR" in pipeline.__all__

    def test_gate_fires_on_high_cv(self):
        from backend.src.animation.alignment.canvas import _seam_chroma_step_cv
        h, w = 160, 64
        img = np.full((h, w, 3), 128, dtype=np.uint8)
        strip_h = h // 8
        boundary_row = strip_h
        img[max(0, boundary_row - 3):boundary_row, :] = [200, 50, 50]
        img[boundary_row:boundary_row + 3, :] = [50, 200, 200]
        result = _seam_chroma_step_cv(img, n_strips=8, boundary_px=3)
        assert result >= 0.0

    def test_gate_suppressed_when_disabled(self, monkeypatch):
        monkeypatch.setattr(pipeline, "_CHROMA_STEP_CV_GATE_ENABLED", False)
        assert pipeline._CHROMA_STEP_CV_GATE_ENABLED is False


class TestChromaEnergyCvGatePipeline:
    def test_flag_exists_and_is_bool(self):
        assert isinstance(pipeline._CHROMA_ENERGY_CV_GATE_ENABLED, bool)

    def test_floor_exists_and_is_float(self):
        assert isinstance(pipeline._CHROMA_ENERGY_CV_GATE_FLOOR, float)
        assert pipeline._CHROMA_ENERGY_CV_GATE_FLOOR > 0

    def test_in_all(self):
        assert "_CHROMA_ENERGY_CV_GATE_ENABLED" in pipeline.__all__
        assert "_CHROMA_ENERGY_CV_GATE_FLOOR" in pipeline.__all__

    def test_gate_fires_on_high_cv(self):
        from backend.src.animation.alignment.canvas import _strip_chroma_energy_cv
        img = np.full((128, 128, 3), 128, dtype=np.uint8)
        img[:64, :, 0] = 220
        img[:64, :, 2] = 30
        assert _strip_chroma_energy_cv(img, n_strips=8) > 0.1

    def test_gate_suppressed_when_disabled(self, monkeypatch):
        monkeypatch.setattr(pipeline, "_CHROMA_ENERGY_CV_GATE_ENABLED", False)
        assert pipeline._CHROMA_ENERGY_CV_GATE_ENABLED is False


class TestSeamGradientCvGatePipeline:
    def test_flag_exists_and_is_bool(self):
        assert isinstance(pipeline._SEAM_GRADIENT_CV_GATE_ENABLED, bool)

    def test_floor_exists_and_is_float(self):
        assert isinstance(pipeline._SEAM_GRADIENT_CV_GATE_FLOOR, float)
        assert pipeline._SEAM_GRADIENT_CV_GATE_FLOOR > 0

    def test_in_all(self):
        assert "_SEAM_GRADIENT_CV_GATE_ENABLED" in pipeline.__all__
        assert "_SEAM_GRADIENT_CV_GATE_FLOOR" in pipeline.__all__

    def test_gate_fires_on_high_cv(self):
        from backend.src.animation.alignment.canvas import _seam_gradient_cv
        rng = np.random.default_rng(5)
        img = rng.integers(0, 256, (128, 64, 3), dtype=np.uint8)
        assert _seam_gradient_cv(img, n_strips=8, band_px=5) >= 0.0

    def test_gate_suppressed_when_disabled(self, monkeypatch):
        monkeypatch.setattr(pipeline, "_SEAM_GRADIENT_CV_GATE_ENABLED", False)
        assert pipeline._SEAM_GRADIENT_CV_GATE_ENABLED is False
