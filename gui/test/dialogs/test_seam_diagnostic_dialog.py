"""Tests for SeamDiagnosticDialog waypoint click tool (§2.11B, S124)."""

from __future__ import annotations

import numpy as np
import pytest

from PySide6.QtGui import QPixmap

pytestmark = pytest.mark.gui


# ── helpers ────────────────────────────────────────────────────────────────────


def _make_data(
    n_seams: int = 3,
    canvas_h: int = 900,
    canvas_w: int = 400,
    with_preview: bool = True,
) -> dict:
    """Minimal data dict for SeamDiagnosticDialog."""
    boundaries = [float((i + 1) * canvas_h // (n_seams + 1)) for i in range(n_seams)]
    seam_post_diffs = {k: float(k * 5) for k in range(n_seams)}
    preview = (
        np.zeros((canvas_h, canvas_w, 3), dtype=np.uint8) if with_preview else None
    )
    return {
        "canvas_preview": preview,
        "boundaries": boundaries,
        "seam_post_diffs": seam_post_diffs,
        "seam_single_pose_keys": [],
        "canvas_h": canvas_h,
        "canvas_w": canvas_w,
        "seam_crops": {},
    }


# ── WaypointCanvas unit tests ──────────────────────────────────────────────────


class TestWaypointCanvas:
    """Tests for _WaypointCanvas internals (no QApplication needed for non-paint ops)."""

    def test_nearest_seam_finds_closest(self, q_app):
        from gui.src.dialogs.seam_diagnostic_dialog import _WaypointCanvas

        pix = QPixmap(260, 400)
        canvas = _WaypointCanvas(
            pix, canvas_w=260, canvas_h=900, boundaries=[200.0, 500.0, 800.0]
        )
        # y=210 → seam 0 (boundary 200) is closer than seam 1 (boundary 500)
        assert canvas._nearest_seam(210) == 0
        # y=750 → seam 2 (boundary 800) is closer than seam 1 (boundary 500)
        assert canvas._nearest_seam(750) == 2

    def test_clear_seam_waypoints_removes_entry(self, q_app):
        from gui.src.dialogs.seam_diagnostic_dialog import _WaypointCanvas

        pix = QPixmap(260, 400)
        canvas = _WaypointCanvas(pix, canvas_w=260, canvas_h=900, boundaries=[200.0])
        canvas._waypoints = {0: [(100, 200), (50, 210)]}
        canvas.clear_seam_waypoints(0)
        assert canvas.all_waypoints() == {}

    def test_all_waypoints_returns_shallow_copy(self, q_app):
        from gui.src.dialogs.seam_diagnostic_dialog import _WaypointCanvas

        pix = QPixmap(260, 400)
        canvas = _WaypointCanvas(pix, canvas_w=260, canvas_h=900, boundaries=[200.0])
        canvas._waypoints = {0: [(50, 200)]}
        wp = canvas.all_waypoints()
        wp[0].append((99, 99))  # mutate copy
        assert (99, 99) not in canvas._waypoints[0], "should be a copy, not a view"

    def test_waypoint_count_per_seam(self, q_app):
        from gui.src.dialogs.seam_diagnostic_dialog import _WaypointCanvas

        pix = QPixmap(260, 400)
        canvas = _WaypointCanvas(
            pix, canvas_w=260, canvas_h=900, boundaries=[300.0, 600.0]
        )
        canvas._waypoints = {0: [(10, 300), (20, 310)], 1: [(50, 600)]}
        assert canvas.waypoint_count(0) == 2
        assert canvas.waypoint_count(1) == 1
        assert canvas.waypoint_count(2) == 0  # seam 2 not in dict


# ── dialog integration tests ───────────────────────────────────────────────────


class TestSeamDiagnosticDialogWaypoints:
    """Integration tests for get_overrides() including waypoints."""

    def test_get_overrides_includes_waypoints(self, q_app):
        from gui.src.dialogs.seam_diagnostic_dialog import SeamDiagnosticDialog

        data = _make_data(n_seams=2, canvas_h=600, canvas_w=300)
        dlg = SeamDiagnosticDialog(data=data)
        assert dlg._canvas is not None, (
            "canvas widget should exist when preview is provided"
        )

        # Inject waypoints directly (avoids simulating mouse events)
        dlg._canvas._waypoints = {1: [(150, 400)]}

        overrides = dlg.get_overrides()
        assert 1 in overrides, "seam with waypoints must appear in overrides"
        assert overrides[1]["waypoints"] == [(150, 400)]

    def test_get_overrides_no_canvas_no_waypoints(self, q_app):
        from gui.src.dialogs.seam_diagnostic_dialog import SeamDiagnosticDialog

        data = _make_data(n_seams=2, with_preview=False)
        dlg = SeamDiagnosticDialog(data=data)
        assert dlg._canvas is None
        # Without canvas, no waypoints should appear
        overrides = dlg.get_overrides()
        assert all("waypoints" not in v for v in overrides.values())
