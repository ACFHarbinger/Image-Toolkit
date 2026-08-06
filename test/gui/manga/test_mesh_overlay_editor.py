import numpy as np
import pytest
from manga.gui.elements.manga.mesh_overlay_editor import MeshOverlayEditor
from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor, QImage

pytestmark = pytest.mark.gui


def _make_image(w=150, h=150, color=(220, 220, 220)):
    img = QImage(w, h, QImage.Format.Format_RGB888)
    img.fill(QColor(*color))
    return img


def _painted_mask_editor(size=150, grid_step=20) -> MeshOverlayEditor:
    editor = MeshOverlayEditor()
    editor.set_image(_make_image(size, size))
    editor.set_paint_mode(True)
    editor.set_pen_width(30)
    editor._paint_line(QPointF(20, 20), QPointF(size - 20, size - 20))
    editor._paint_line(QPointF(20, size - 20), QPointF(size - 20, 20))
    return editor


class TestMeshOverlayEditorBasics:
    def test_no_image_initially(self, q_app):
        editor = MeshOverlayEditor()
        assert editor.has_image() is False

    def test_set_image_resets_mask_and_mesh(self, q_app):
        editor = MeshOverlayEditor()
        editor.set_image(_make_image())
        assert editor.has_image() is True
        assert editor.has_mask() is False
        assert editor.has_mesh() is False

    def test_painting_produces_mask(self, q_app):
        editor = _painted_mask_editor()
        assert editor.has_mask() is True
        assert editor.get_mask().any()

    def test_clear_mask_empties_it(self, q_app):
        editor = _painted_mask_editor()
        editor.clear_mask()
        assert editor.has_mask() is False


class TestMeshGeneration:
    def test_generate_mesh_populates_vertices_and_triangles(self, q_app):
        editor = _painted_mask_editor()
        editor.generate_mesh(grid_step=20)
        assert editor.has_mesh() is True
        assert editor.get_rest_vertices().shape[0] > 0
        assert editor.get_triangles().shape[0] > 0

    def test_live_vertices_start_equal_to_rest(self, q_app):
        editor = _painted_mask_editor()
        editor.generate_mesh(grid_step=20)
        assert np.array_equal(editor.get_live_vertices(), editor.get_rest_vertices())

    def test_generate_mesh_emits_signal(self, q_app):
        editor = _painted_mask_editor()
        received = []
        editor.mesh_generated.connect(lambda: received.append(True))
        editor.generate_mesh(grid_step=20)
        assert received == [True]

    def test_generate_mesh_resets_anchors(self, q_app):
        editor = _painted_mask_editor()
        editor.generate_mesh(grid_step=20)
        editor._anchors[0] = (10.0, 10.0)
        editor.generate_mesh(grid_step=20)
        assert editor.get_anchors() == {}


class TestPosing:
    def test_dragging_a_vertex_pins_it_as_an_anchor_at_the_target(self, q_app):
        editor = _painted_mask_editor()
        editor.generate_mesh(grid_step=20)
        rest = editor.get_rest_vertices()

        idx = 0
        target = QPointF(float(rest[idx, 0] + 15), float(rest[idx, 1] - 10))
        editor._dragging_idx = idx
        editor._drag_vertex_to(idx, target)

        assert idx in editor.get_anchors()
        live = editor.get_live_vertices()
        assert np.allclose(live[idx], [target.x(), target.y()], atol=1e-6)

    def test_drag_solve_is_relative_to_rest_pose_not_previous_pose(self, q_app):
        """arap_deform() has no incremental mode -- every drag call must be
        solved from the original rest positions against the accumulated
        anchor set, not from whatever the live positions currently are."""
        editor = _painted_mask_editor()
        editor.generate_mesh(grid_step=20)
        rest_before = editor.get_rest_vertices().copy()

        idx = 0
        editor._dragging_idx = idx
        editor._drag_vertex_to(idx, QPointF(float(rest_before[idx, 0] + 5), float(rest_before[idx, 1])))
        editor._drag_vertex_to(idx, QPointF(float(rest_before[idx, 0] + 25), float(rest_before[idx, 1])))

        # rest_vertices must be untouched by dragging -- only live_vertices
        # (the solve output) should change.
        assert np.array_equal(editor.get_rest_vertices(), rest_before)

    def test_pose_changed_signal_emitted_on_drag(self, q_app):
        editor = _painted_mask_editor()
        editor.generate_mesh(grid_step=20)
        rest = editor.get_rest_vertices()

        received = []
        editor.pose_changed.connect(lambda: received.append(True))
        editor._dragging_idx = 0
        editor._drag_vertex_to(0, QPointF(float(rest[0, 0] + 5), float(rest[0, 1])))
        assert received == [True]

    def test_drag_target_clipped_to_canvas_bounds(self, q_app):
        editor = _painted_mask_editor(size=150)
        editor.generate_mesh(grid_step=20)

        editor._dragging_idx = 0
        editor._drag_vertex_to(0, QPointF(-500, -500))
        anchor_x, anchor_y = editor.get_anchors()[0]
        assert anchor_x >= 0
        assert anchor_y >= 0

    def test_reset_pose_clears_anchors_and_restores_rest_positions(self, q_app):
        editor = _painted_mask_editor()
        editor.generate_mesh(grid_step=20)
        rest = editor.get_rest_vertices()

        editor._dragging_idx = 0
        editor._drag_vertex_to(0, QPointF(float(rest[0, 0] + 15), float(rest[0, 1])))
        assert editor.get_anchors() != {}

        editor.reset_pose()
        assert editor.get_anchors() == {}
        assert np.array_equal(editor.get_live_vertices(), rest)

    def test_reset_pose_emits_signal(self, q_app):
        editor = _painted_mask_editor()
        editor.generate_mesh(grid_step=20)
        received = []
        editor.pose_changed.connect(lambda: received.append(True))
        editor.reset_pose()
        assert received == [True]

    def test_reset_pose_before_any_mesh_is_a_no_op(self, q_app):
        editor = MeshOverlayEditor()
        editor.set_image(_make_image())
        editor.reset_pose()  # should not raise


class TestNearestVertex:
    def test_finds_vertex_within_pick_radius(self, q_app):
        editor = _painted_mask_editor()
        editor.generate_mesh(grid_step=20)
        rest = editor.get_rest_vertices()

        point = QPointF(float(rest[0, 0]), float(rest[0, 1]))
        assert editor._nearest_vertex(point) == 0

    def test_returns_none_when_far_from_every_vertex(self, q_app):
        editor = _painted_mask_editor()
        editor.generate_mesh(grid_step=20)
        assert editor._nearest_vertex(QPointF(-1000, -1000)) is None

    def test_returns_none_before_mesh_exists(self, q_app):
        editor = MeshOverlayEditor()
        editor.set_image(_make_image())
        assert editor._nearest_vertex(QPointF(10, 10)) is None
