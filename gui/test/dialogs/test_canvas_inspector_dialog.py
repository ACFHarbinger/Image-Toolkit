"""Tests for CanvasInspectorDialog drag-to-reposition (S90) and rotation/scale (S91)."""

from __future__ import annotations

import math
import pytest

from PySide6.QtCore import QPointF

from gui.src.dialogs.canvas_inspector_dialog import (
    CanvasInspectorDialog,
)

pytestmark = pytest.mark.gui


def _make_data(n_frames: int = 3, canvas_h: int = 1000, canvas_w: int = 800) -> dict:
    affines = []
    for i in range(n_frames):
        aff = [[1.0, 0.0, 0.0], [0.0, 1.0, float(i * 200)]]
        affines.append(aff)
    return {
        "canvas_h": canvas_h,
        "canvas_w": canvas_w,
        "frame_h": 180,
        "frame_w": 320,
        "affines": affines,
        "image_paths": [f"/tmp/frame_{i:02d}.png" for i in range(n_frames)],
        "thumbnails": [],  # skip thumbnail rendering in tests
    }


class TestCanvasInspectorDrag:
    def test_adjusted_affines_no_nudge_returns_original(self, q_app):
        data = _make_data(3)
        dlg = CanvasInspectorDialog(data)
        result = dlg.adjusted_affines()
        assert len(result) == 3
        for idx, (orig, adj) in enumerate(zip(data["affines"], result)):
            assert adj[0][2] == pytest.approx(orig[0][2])
            assert adj[1][2] == pytest.approx(orig[1][2])

    def test_nudge_button_updates_adjusted_affines(self, q_app):
        data = _make_data(2)
        dlg = CanvasInspectorDialog(data)
        dlg._list.setCurrentRow(0)
        # Simulate nudge right by step (default 10)
        dlg._nudge(10.0, 0.0)
        result = dlg.adjusted_affines()
        assert result[0][0][2] == pytest.approx(10.0)
        assert result[0][1][2] == pytest.approx(0.0)
        # Frame 1 unchanged
        assert result[1][0][2] == pytest.approx(0.0)
        assert result[1][1][2] == pytest.approx(200.0)

    def test_drag_item_setpos_updates_nudge(self, q_app):
        data = _make_data(2)
        dlg = CanvasInspectorDialog(data)
        item = dlg._drag_items[1]
        orig_ty = float(data["affines"][1][1][2])  # 200.0
        # Simulate drag: move item 30px down
        item.setPos(QPointF(0.0, orig_ty + 30.0))
        assert dlg._nudges[1][1] == pytest.approx(30.0)
        result = dlg.adjusted_affines()
        assert result[1][1][2] == pytest.approx(orig_ty + 30.0)

    def test_reset_frame_zeroes_nudge(self, q_app):
        data = _make_data(2)
        dlg = CanvasInspectorDialog(data)
        dlg._list.setCurrentRow(0)
        dlg._nudge(50.0, 25.0)
        assert dlg._nudges[0] == pytest.approx([50.0, 25.0])
        dlg._reset_frame()
        assert dlg._nudges[0] == pytest.approx([0.0, 0.0])

    def test_step_spinbox_controls_nudge_amount(self, q_app):
        data = _make_data(2)
        dlg = CanvasInspectorDialog(data)
        dlg._step_spin.setValue(1)
        dlg._list.setCurrentRow(1)
        dlg._nudge(0.0, -dlg._step_spin.value())
        result = dlg.adjusted_affines()
        assert result[1][1][2] == pytest.approx(200.0 - 1.0)


class TestCanvasInspectorRotScale:
    def test_adjusted_affines_default_rot_scale_is_identity(self, q_app):
        # With 0° rotation and 1.0 scale, adjusted_affines should match input 2x2 block
        data = _make_data(2)
        dlg = CanvasInspectorDialog(data)
        result = dlg.adjusted_affines()
        for idx in range(2):
            assert result[idx][0][0] == pytest.approx(1.0)
            assert result[idx][0][1] == pytest.approx(0.0)
            assert result[idx][1][0] == pytest.approx(0.0)
            assert result[idx][1][1] == pytest.approx(1.0)

    def test_adjusted_affines_90deg_rotation(self, q_app):
        # 90° CW rotation on a pure-translation affine (identity 2x2 block):
        # R(90°) @ I = [[cos90, -sin90], [sin90, cos90]] = [[0, -1], [1, 0]]
        data = _make_data(1)
        dlg = CanvasInspectorDialog(data)
        dlg._rot_angles[0] = 90.0
        result = dlg.adjusted_affines()
        assert result[0][0][0] == pytest.approx(0.0, abs=1e-9)
        assert result[0][0][1] == pytest.approx(-1.0, abs=1e-9)
        assert result[0][1][0] == pytest.approx(1.0, abs=1e-9)
        assert result[0][1][1] == pytest.approx(0.0, abs=1e-9)

    def test_adjusted_affines_scale_2x(self, q_app):
        # scale=2.0 with 0° rotation on identity 2x2 → diagonal becomes 2.0
        data = _make_data(1)
        dlg = CanvasInspectorDialog(data)
        dlg._scale_factors[0] = 2.0
        result = dlg.adjusted_affines()
        assert result[0][0][0] == pytest.approx(2.0)
        assert result[0][1][1] == pytest.approx(2.0)
        assert result[0][0][1] == pytest.approx(0.0, abs=1e-9)
        assert result[0][1][0] == pytest.approx(0.0, abs=1e-9)

    def test_reset_frame_clears_rot_and_scale(self, q_app):
        data = _make_data(2)
        dlg = CanvasInspectorDialog(data)
        dlg._list.setCurrentRow(1)
        dlg._rot_angles[1] = 45.0
        dlg._scale_factors[1] = 1.5
        dlg._nudge(20.0, 10.0)
        dlg._reset_frame()
        assert dlg._rot_angles[1] == pytest.approx(0.0)
        assert dlg._scale_factors[1] == pytest.approx(1.0)
        assert dlg._nudges[1] == pytest.approx([0.0, 0.0])
        result = dlg.adjusted_affines()
        # After reset, frame 1 affine should equal the original
        assert result[1][0][0] == pytest.approx(1.0)
        assert result[1][1][1] == pytest.approx(1.0)
        assert result[1][1][2] == pytest.approx(200.0)

    def test_rot_scale_and_nudge_all_applied(self, q_app):
        # 45° rotation + scale 1.5 + nudge should compose correctly
        data = _make_data(1)
        dlg = CanvasInspectorDialog(data)
        dlg._list.setCurrentRow(0)
        dlg._rot_angles[0] = 45.0
        dlg._scale_factors[0] = 1.5
        dlg._nudge(100.0, 50.0)
        result = dlg.adjusted_affines()
        # Check tx/ty nudge applied
        assert result[0][0][2] == pytest.approx(100.0)
        assert result[0][1][2] == pytest.approx(50.0)
        # Check 2x2 block: R(45°, 1.5) @ I = 1.5*[[cos45, -sin45],[sin45,cos45]]
        c = math.cos(math.radians(45.0)) * 1.5
        s = math.sin(math.radians(45.0)) * 1.5
        assert result[0][0][0] == pytest.approx(c)
        assert result[0][0][1] == pytest.approx(-s)
        assert result[0][1][0] == pytest.approx(s)
        assert result[0][1][1] == pytest.approx(c)
