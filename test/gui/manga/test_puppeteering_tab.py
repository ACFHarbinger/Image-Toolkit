from unittest.mock import patch

import pytest
from gui.src.tabs.manga.puppeteering_tab import MangaPuppeteeringTab
from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor, QImage

pytestmark = pytest.mark.gui


def _make_image(w=150, h=150, color=(220, 220, 220)):
    img = QImage(w, h, QImage.Format.Format_RGB888)
    img.fill(QColor(*color))
    return img


def _tab_with_mask(size=150):
    tab = MangaPuppeteeringTab()
    tab.editor.set_image(_make_image(size, size))
    tab.editor.set_paint_mode(True)
    tab.editor.set_pen_width(30)
    tab.editor._paint_line(QPointF(20, 20), QPointF(size - 20, size - 20))
    tab.editor._paint_line(QPointF(20, size - 20), QPointF(size - 20, 20))
    return tab


class TestMangaPuppeteeringTab:
    def test_constructs_without_image(self, q_app):
        tab = MangaPuppeteeringTab()
        assert tab.editor.has_image() is False

    def test_browse_image_loads_into_editor(self, q_app, tmp_path):
        tab = MangaPuppeteeringTab()
        img_path = tmp_path / "panel.png"
        _make_image().save(str(img_path))

        with patch("gui.src.tabs.manga.puppeteering_tab.QFileDialog") as mock_dialog:
            mock_dialog.getOpenFileName.return_value = (str(img_path), "")
            tab._browse_image()

        assert tab.editor.has_image() is True
        assert "loaded" in tab.status_label.text().lower()

    def test_paint_mask_checkbox_toggles_editor_paint_mode(self, q_app):
        tab = MangaPuppeteeringTab()
        tab.chk_paint_mask.setChecked(True)
        assert tab.editor._paint_mode is True
        tab.chk_paint_mask.setChecked(False)
        assert tab.editor._paint_mode is False

    def test_pen_width_slider_updates_editor(self, q_app):
        tab = MangaPuppeteeringTab()
        tab.pen_width_slider.setValue(40)
        assert tab.editor._pen_width == 40

    def test_clear_mask_button_clears_editor_mask(self, q_app):
        tab = _tab_with_mask()
        assert tab.editor.has_mask() is True
        tab._on_clear_mask()
        assert tab.editor.has_mask() is False

    def test_generate_mesh_without_image_shows_info(self, q_app):
        tab = MangaPuppeteeringTab()
        with patch("gui.src.tabs.manga.puppeteering_tab.QMessageBox") as mock_box:
            tab._on_generate_mesh()
            mock_box.information.assert_called_once()

    def test_generate_mesh_without_mask_shows_info(self, q_app):
        tab = MangaPuppeteeringTab()
        tab.editor.set_image(_make_image())
        with patch("gui.src.tabs.manga.puppeteering_tab.QMessageBox") as mock_box:
            tab._on_generate_mesh()
            mock_box.information.assert_called_once()

    def test_generate_mesh_builds_mesh_and_updates_status(self, q_app):
        tab = _tab_with_mask()
        tab.grid_step_spin.setValue(20)
        tab._on_generate_mesh()

        assert tab.editor.has_mesh() is True
        assert "vertices" in tab.status_label.text().lower()

    def test_generate_mesh_switches_off_paint_mode(self, q_app):
        tab = _tab_with_mask()
        tab.chk_paint_mask.setChecked(True)
        tab.grid_step_spin.setValue(20)
        tab._on_generate_mesh()
        assert tab.chk_paint_mask.isChecked() is False

    def test_generate_mesh_too_few_grid_points_shows_warning(self, q_app):
        tab = MangaPuppeteeringTab()
        tab.editor.set_image(_make_image(30, 30))
        tab.editor.set_paint_mode(True)
        tab.editor.set_pen_width(4)
        tab.editor._paint_line(QPointF(5, 5), QPointF(5, 5))
        tab.grid_step_spin.setValue(64)

        with patch("gui.src.tabs.manga.puppeteering_tab.QMessageBox") as mock_box:
            tab._on_generate_mesh()
            mock_box.warning.assert_called_once()

    def test_reset_pose_button_resets_editor(self, q_app):
        tab = _tab_with_mask()
        tab.grid_step_spin.setValue(20)
        tab._on_generate_mesh()
        rest = tab.editor.get_rest_vertices()

        tab.editor._dragging_idx = 0
        tab.editor._drag_vertex_to(0, QPointF(float(rest[0, 0] + 15), float(rest[0, 1])))
        assert tab.editor.get_anchors() != {}

        tab._on_reset_pose()
        assert tab.editor.get_anchors() == {}

    def test_pose_changed_updates_status_label(self, q_app):
        tab = _tab_with_mask()
        tab.grid_step_spin.setValue(20)
        tab._on_generate_mesh()
        rest = tab.editor.get_rest_vertices()

        tab.editor._dragging_idx = 0
        tab.editor._drag_vertex_to(0, QPointF(float(rest[0, 0] + 15), float(rest[0, 1])))
        assert "posing" in tab.status_label.text().lower()
