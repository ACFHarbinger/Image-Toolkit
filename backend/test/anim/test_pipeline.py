"""
Tests for pipeline.py module-level functions:
  §1.9A — _spatial_dedup_frames (scans_frames sync bug fix)
  §2.9C — _filter_high_conf_edges (high-confidence BA re-solve)
  §1.9C — _reload_scans_frames (on-demand SCANS frame reload)
"""

import numpy as np
import pytest
import cv2

from backend.src.anim.pipeline import (
    _spatial_dedup_frames,
    _filter_high_conf_edges,
    _reload_scans_frames,
)
from backend.src.constants.anim import HIGH_CONF_EDGE_THRESH


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
