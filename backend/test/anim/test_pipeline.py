"""
Tests for pipeline.py module-level functions:
  §1.9A — _spatial_dedup_frames (scans_frames sync bug fix)
  §2.9C — _filter_high_conf_edges (high-confidence BA re-solve)
  §1.9C — _reload_scans_frames (on-demand SCANS frame reload)
  §1.13 — _reject_scene_change_edges (scene-change luma gate)
  §1.3C — _normalize_frame_scales (scale normalisation before BA)
"""

import numpy as np
import pytest
import cv2

from backend.src.anim.pipeline import (
    _check_edge_graph_connectivity,
    _compute_mst_weight,
    _spatial_dedup_frames,
    _filter_high_conf_edges,
    _reload_scans_frames,
    _reject_scene_change_edges,
    _normalize_frame_scales,
)
from backend.src.constants.anim import HIGH_CONF_EDGE_THRESH, SCALE_NORM_THRESH, SCENE_CHANGE_LUMA_THRESH


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
            _make_edge_with_weight(1, 2, weight=HIGH_CONF_EDGE_THRESH),  # exactly at floor
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
            {"i": 0, "j": 1, "M": _make_affine(dy=50.0)},   # no weight key
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
        out_frames, out_edges = _normalize_frame_scales(frames, edges, scale_thresh=0.05)
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
        out_frames, out_edges = _normalize_frame_scales(frames, edges, scale_thresh=0.05)
        assert out_frames is frames
        assert out_edges is edges

    def test_disconnected_graph_returns_unchanged(self):
        """A graph where frame 2 cannot be reached from frame 0 must be left unchanged."""
        frames = [self._frame() for _ in range(3)]
        # Only edge 0→1; frame 2 is isolated
        edges = [self._edge(0, 1, scale=1.3, dy=50.0)]
        out_frames, out_edges = _normalize_frame_scales(frames, edges, scale_thresh=0.05)
        assert out_frames is frames
        assert out_edges is edges

    def test_edge_affines_reset_to_unit_scale(self):
        """After normalisation the updated edge M must have diagonal elements ≈ 1.0."""
        frames = [self._frame() for _ in range(2)]
        edges = [self._edge(0, 1, scale=1.3, dy=60.0)]
        _, out_edges = _normalize_frame_scales(frames, edges, scale_thresh=0.05)
        M = out_edges[0]["M"]
        assert abs(float(M[0, 0]) - 1.0) < 1e-4, f"M[0,0]={M[0,0]}, expected 1.0"
        assert abs(float(M[1, 1]) - 1.0) < 1e-4, f"M[1,1]={M[1,1]}, expected 1.0"
        assert abs(float(M[0, 1])) < 1e-4, f"M[0,1]={M[0,1]}, expected ~0"
        assert abs(float(M[1, 0])) < 1e-4, f"M[1,0]={M[1,0]}, expected ~0"


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
        result = _reject_scene_change_edges(edges, frames, max_luma_diff=60.0, use_bgr=True)
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
        bgr_result = _reject_scene_change_edges(edges, frames, max_luma_diff=60.0, use_bgr=True)
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
        luma_result = _reject_scene_change_edges(edges, frames, max_luma_diff=60.0, use_bgr=False)
        assert len(luma_result) == 1, "Luma gate should keep this hue-shifted pair"

    def test_bgr_threshold_zero_disabled(self):
        """max_luma_diff=0 disables the gate regardless of channel mismatch."""
        frames = [self._uniform_frame(0, 0, 0), self._uniform_frame(255, 255, 255)]
        edges = [self._edge(0, 1)]
        result = _reject_scene_change_edges(edges, frames, max_luma_diff=0.0, use_bgr=True)
        assert len(result) == 1

    def test_bgr_small_channel_diff_kept(self):
        """Frames with channel diffs below threshold → kept."""
        frame_a = self._uniform_frame(100, 100, 100)
        frame_b = self._uniform_frame(140, 140, 140)  # diff = 40 < 60
        frames = [frame_a, frame_b]
        edges = [self._edge(0, 1)]
        result = _reject_scene_change_edges(edges, frames, max_luma_diff=60.0, use_bgr=True)
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
            self._edge(0, 1), self._edge(0, 2), self._edge(0, 3),
            self._edge(1, 2), self._edge(1, 3), self._edge(2, 3),
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
