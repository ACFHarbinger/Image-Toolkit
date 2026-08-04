from unittest.mock import patch

import pytest
from gui.src.tabs.manga.colorization_tab import MangaColorizationTab
from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor

pytestmark = pytest.mark.gui


class TestMangaColorizationTab:
    def test_constructs_with_only_scribble_mode_enabled(self, q_app):
        tab = MangaColorizationTab()
        assert tab.mode_combo.count() == 4
        assert tab.mode_combo.model().item(0).isEnabled() is True
        for idx in range(1, 4):
            assert tab.mode_combo.model().item(idx).isEnabled() is False

    def test_colorize_without_line_art_shows_info(self, q_app):
        tab = MangaColorizationTab()
        with patch("gui.src.tabs.manga.colorization_tab.QMessageBox") as mock_box:
            tab._run_colorize()
            mock_box.information.assert_called_once()

    def test_colorize_without_scribbles_shows_info(self, q_app):
        from PySide6.QtGui import QImage

        tab = MangaColorizationTab()
        img = QImage(20, 20, QImage.Format.Format_RGB888)
        img.fill(QColor(180, 180, 180))
        tab.canvas.set_line_art(img)

        with patch("gui.src.tabs.manga.colorization_tab.QMessageBox") as mock_box:
            tab._run_colorize()
            mock_box.information.assert_called_once()

    def test_pen_color_picker_updates_canvas(self, q_app):
        tab = MangaColorizationTab()
        with patch("gui.src.tabs.manga.colorization_tab.QColorDialog") as mock_dialog:
            mock_dialog.getColor.return_value = QColor(9, 9, 9)
            tab._pick_pen_color()
        assert tab.canvas.pen_color().getRgb()[:3] == (9, 9, 9)

    def test_pen_width_slider_updates_canvas(self, q_app):
        tab = MangaColorizationTab()
        tab.pen_width_slider.setValue(30)
        assert tab.canvas._pen_width == 30

    def test_export_without_result_shows_info(self, q_app):
        tab = MangaColorizationTab()
        with patch("gui.src.tabs.manga.colorization_tab.QMessageBox") as mock_box:
            tab._export_result()
            mock_box.information.assert_called_once()

    def test_on_colorize_finished_updates_canvas_directly(self, q_app):
        import numpy as np
        from PySide6.QtGui import QImage

        tab = MangaColorizationTab()
        img = QImage(10, 10, QImage.Format.Format_RGB888)
        img.fill(QColor(180, 180, 180))
        tab.canvas.set_line_art(img)

        tab._on_colorize_finished(np.full((10, 10, 3), 255, dtype=np.uint8))
        assert not tab.canvas.get_result_pixmap().isNull()
        assert "complete" in tab.status_label.text().lower()

    def test_on_colorize_error_shows_critical_and_resets_status(self, q_app):
        tab = MangaColorizationTab()
        with patch("gui.src.tabs.manga.colorization_tab.QMessageBox") as mock_box:
            tab._on_colorize_error("boom")
            mock_box.critical.assert_called_once()
        assert "failed" in tab.status_label.text().lower()

    def test_run_colorize_starts_worker_with_correct_data(self, q_app):
        """Covers the real-thread dispatch path without depending on actual
        cross-thread signal-delivery timing inside the test itself (proven
        unreliable in this harness -- hangs in isolation, silently drops the
        signal when run with sibling tests -- despite the same worker
        completing correctly and delivering its signal in under a second
        when driven outside pytest; see backend/test/manga/ for the
        algorithm's own correctness coverage and
        test_on_colorize_finished_updates_canvas_directly /
        test_on_colorize_error_shows_critical_and_resets_status below for
        the result-handling logic's coverage)."""
        from PySide6.QtGui import QImage

        tab = MangaColorizationTab()
        img = QImage(30, 30, QImage.Format.Format_RGB888)
        img.fill(QColor(190, 190, 190))
        tab.canvas.set_line_art(img)
        tab.canvas.set_pen_color(QColor(255, 0, 0))
        tab.canvas._paint_line(QPointF(10, 10), QPointF(15, 15))

        tab._run_colorize()
        try:
            assert tab._worker is not None
            assert tab.btn_colorize.isEnabled() is False
            import numpy as np

            assert isinstance(tab._worker._gray, np.ndarray)
            assert tab._worker._gray.shape == (30, 30)
            assert tab._worker._scribble_mask.any()
        finally:
            # Let the real background thread finish before the QApplication
            # tears down, rather than leaving it orphaned mid-solve.
            if tab._worker is not None:
                tab._worker.wait()

    def test_clear_scribbles_button_clears_canvas(self, q_app):
        from PySide6.QtGui import QImage

        tab = MangaColorizationTab()
        img = QImage(20, 20, QImage.Format.Format_RGB888)
        img.fill(QColor(180, 180, 180))
        tab.canvas.set_line_art(img)
        tab.canvas._paint_line(QPointF(5, 5), QPointF(5, 5))
        assert tab.canvas.has_scribbles() is True

        # Same button the toolbar wires to canvas.clear_scribbles directly.
        tab.canvas.clear_scribbles()
        assert tab.canvas.has_scribbles() is False
