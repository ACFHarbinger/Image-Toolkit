from unittest.mock import patch

import pytest
from gui.src.tabs.manga.colorization_tab import MangaColorizationTab
from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor

pytestmark = pytest.mark.gui


class TestMangaColorizationTab:
    def test_constructs_with_only_implemented_modes_enabled(self, q_app):
        tab = MangaColorizationTab()
        assert tab.mode_combo.count() == 4
        # Scribble (Levin), Screentone-aware, and Reference/Optimal-Transport
        # have working backends.
        assert tab.mode_combo.model().item(0).isEnabled() is True
        assert tab.mode_combo.model().item(1).isEnabled() is True
        assert tab.mode_combo.model().item(2).isEnabled() is True
        # Reference/Graph-QP doesn't yet.
        assert tab.mode_combo.model().item(3).isEnabled() is False

    def test_screentone_mode_dispatches_to_screentone_backend(self, q_app):
        from backend.src.manga import colorize_scribble, colorize_scribble_screentone
        from gui.src.tabs.manga.colorization_tab import _MODE_BACKENDS

        assert _MODE_BACKENDS[0] is colorize_scribble
        assert _MODE_BACKENDS[1] is colorize_scribble_screentone

    def test_reference_mode_dispatches_to_optimal_transport_backend(self, q_app):
        from backend.src.manga import colorize_reference
        from gui.src.tabs.manga.colorization_tab import _REFERENCE_MODE_BACKENDS

        assert _REFERENCE_MODE_BACKENDS[2] is colorize_reference

    def test_selecting_reference_mode_enables_load_reference_button(self, q_app):
        tab = MangaColorizationTab()
        assert tab.btn_load_reference.isEnabled() is False
        tab.mode_combo.setCurrentIndex(2)
        assert tab.btn_load_reference.isEnabled() is True
        tab.mode_combo.setCurrentIndex(0)
        assert tab.btn_load_reference.isEnabled() is False

    def test_reference_mode_without_reference_image_shows_info(self, q_app):
        from PySide6.QtGui import QImage

        tab = MangaColorizationTab()
        img = QImage(20, 20, QImage.Format.Format_RGB888)
        img.fill(QColor(180, 180, 180))
        tab.canvas.set_line_art(img)
        tab.mode_combo.setCurrentIndex(2)

        with patch("gui.src.tabs.manga.colorization_tab.QMessageBox") as mock_box:
            tab._run_colorize()
            mock_box.information.assert_called_once()
        assert tab.btn_colorize.isEnabled() is True

    def test_run_colorize_in_reference_mode_starts_reference_worker(self, q_app):
        import numpy as np
        from gui.src.helpers.manga import ReferenceColorizeWorker
        from PySide6.QtGui import QImage

        tab = MangaColorizationTab()
        img = QImage(20, 20, QImage.Format.Format_RGB888)
        img.fill(QColor(180, 180, 180))
        tab.canvas.set_line_art(img)
        tab.mode_combo.setCurrentIndex(2)
        tab._reference_rgb = np.full((20, 20, 3), 128, dtype=np.uint8)

        tab._run_colorize()
        try:
            assert isinstance(tab._worker, ReferenceColorizeWorker)
            assert tab._worker._target_gray.shape == (20, 20)
            assert tab._worker._reference_rgb.shape == (20, 20, 3)
        finally:
            if tab._worker is not None:
                tab._worker.wait()

    def test_run_colorize_uses_selected_mode_backend(self, q_app):
        from backend.src.manga import colorize_scribble_screentone
        from PySide6.QtGui import QImage

        tab = MangaColorizationTab()
        img = QImage(20, 20, QImage.Format.Format_RGB888)
        img.fill(QColor(180, 180, 180))
        tab.canvas.set_line_art(img)
        tab.canvas._paint_line(QPointF(5, 5), QPointF(5, 5))

        tab.mode_combo.setCurrentIndex(1)
        try:
            tab._run_colorize()
            assert tab._worker is not None
            assert tab._worker._colorize_fn is colorize_scribble_screentone
        finally:
            if tab._worker is not None:
                tab._worker.wait()

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

    def test_browse_reference_loads_reference_array(self, q_app, tmp_path):
        from PySide6.QtGui import QImage

        tab = MangaColorizationTab()
        ref_path = tmp_path / "ref.png"
        img = QImage(15, 15, QImage.Format.Format_RGB888)
        img.fill(QColor(50, 100, 150))
        img.save(str(ref_path))

        with patch("gui.src.tabs.manga.colorization_tab.QFileDialog") as mock_dialog:
            mock_dialog.getOpenFileName.return_value = (str(ref_path), "")
            tab._browse_reference()

        assert tab._reference_rgb is not None
        assert tab._reference_rgb.shape == (15, 15, 3)
        assert "reference" in tab.status_label.text().lower()

    def test_clear_scribbles_button_clears_canvas(self, q_app):
        from PySide6.QtGui import QImage

        tab = MangaColorizationTab()
        img = QImage(20, 20, QImage.Format.Format_RGB888)
        img.fill(QColor(180, 180, 180))
        tab.canvas.set_line_art(img)
        tab.canvas._paint_line(QPointF(5, 5), QPointF(5, 5))
        assert tab.canvas.has_scribbles() is True

        # Same handler the toolbar's "Clear Scribbles" button is wired to.
        tab._on_clear_scribbles()
        assert tab.canvas.has_scribbles() is False

    def test_clear_scribbles_resets_incremental_baseline(self, q_app):
        import numpy as np

        tab = MangaColorizationTab()
        tab._prev_result = np.zeros((10, 10, 3), dtype=np.uint8)
        tab._on_clear_scribbles()
        assert tab._prev_result is None


class TestMangaColorizationTabLivePreview:
    """Issue #191: quadtree-accelerated incremental resolve wiring."""

    def _tab_with_line_art(self, size=40):
        from PySide6.QtGui import QImage

        tab = MangaColorizationTab()
        img = QImage(size, size, QImage.Format.Format_RGB888)
        img.fill(QColor(180, 180, 180))
        tab.canvas.set_line_art(img)
        return tab

    def test_live_preview_enabled_only_for_scribble_based_modes(self, q_app):
        tab = self._tab_with_line_art()
        assert tab.chk_live_preview.isEnabled() is True

        tab.mode_combo.setCurrentIndex(2)  # Reference / Optimal-Transport
        assert tab.chk_live_preview.isEnabled() is False
        assert tab.chk_live_preview.isChecked() is False

        tab.mode_combo.setCurrentIndex(0)
        assert tab.chk_live_preview.isEnabled() is True

    def test_selecting_reference_mode_unchecks_live_preview(self, q_app):
        tab = self._tab_with_line_art()
        tab.chk_live_preview.setChecked(True)
        tab.mode_combo.setCurrentIndex(2)
        assert tab.chk_live_preview.isChecked() is False

    def test_scribble_changed_with_live_preview_off_does_nothing(self, q_app):
        tab = self._tab_with_line_art()
        tab.canvas._paint_line(QPointF(5, 5), QPointF(5, 5))
        tab._on_scribble_changed()
        assert tab._worker is None

    def test_scribble_changed_without_baseline_triggers_full_solve(self, q_app):
        tab = self._tab_with_line_art()
        tab.canvas._paint_line(QPointF(5, 5), QPointF(5, 5))
        tab.chk_live_preview.setChecked(True)

        try:
            assert tab._worker is not None
            from gui.src.helpers.manga import ColorizeWorker

            assert isinstance(tab._worker, ColorizeWorker)
        finally:
            if tab._worker is not None:
                tab._worker.wait()

    def test_scribble_changed_with_baseline_starts_incremental_worker(self, q_app):
        import numpy as np

        tab = self._tab_with_line_art()
        tab.canvas._paint_line(QPointF(5, 5), QPointF(5, 5))
        tab._prev_result = np.full((40, 40, 3), 200, dtype=np.uint8)
        tab.canvas._last_stroke_bbox = (0, 0, 10, 10)
        tab.chk_live_preview.setChecked(True)

        tab._on_scribble_changed()
        try:
            from gui.src.helpers.manga import IncrementalColorizeWorker

            assert isinstance(tab._worker, IncrementalColorizeWorker)
        finally:
            if tab._worker is not None:
                tab._worker.wait()

    def test_scribble_changed_skips_when_a_worker_is_already_running(self, q_app):
        import numpy as np

        tab = self._tab_with_line_art()
        tab.canvas._paint_line(QPointF(5, 5), QPointF(5, 5))
        tab._prev_result = np.full((40, 40, 3), 200, dtype=np.uint8)
        tab.canvas._last_stroke_bbox = (0, 0, 10, 10)
        tab.chk_live_preview.setChecked(True)

        sentinel = object()
        tab._worker = sentinel
        tab._on_scribble_changed()
        assert tab._worker is sentinel

    def test_scribble_changed_without_dirty_bbox_does_nothing(self, q_app):
        import numpy as np

        tab = self._tab_with_line_art()
        tab.canvas._paint_line(QPointF(5, 5), QPointF(5, 5))
        tab._prev_result = np.full((40, 40, 3), 200, dtype=np.uint8)
        tab.canvas._last_stroke_bbox = None
        tab.chk_live_preview.setChecked(True)

        tab._on_scribble_changed()
        assert tab._worker is None

    def test_on_colorize_finished_seeds_incremental_baseline(self, q_app):
        import numpy as np

        tab = self._tab_with_line_art()
        assert tab._prev_result is None

        result = np.full((40, 40, 3), 128, dtype=np.uint8)
        tab._on_colorize_finished(result)
        assert tab._prev_result is result

    def test_on_incremental_finished_updates_canvas_and_baseline(self, q_app):
        import numpy as np

        tab = self._tab_with_line_art()
        result = np.full((40, 40, 3), 64, dtype=np.uint8)
        tab._on_incremental_finished(result)

        assert tab._prev_result is result
        assert not tab.canvas.get_result_pixmap().isNull()
        assert "live preview" in tab.status_label.text().lower()

    def test_loading_new_line_art_resets_incremental_baseline(self, q_app, tmp_path):
        import numpy as np
        from PySide6.QtGui import QImage

        tab = self._tab_with_line_art()
        tab._prev_result = np.zeros((40, 40, 3), dtype=np.uint8)
        tab._quadtree_leaves = [(0, 0, 40, 40)]

        img_path = tmp_path / "line_art.png"
        img = QImage(20, 20, QImage.Format.Format_RGB888)
        img.fill(QColor(180, 180, 180))
        img.save(str(img_path))

        with patch("gui.src.tabs.manga.colorization_tab.QFileDialog") as mock_dialog:
            mock_dialog.getOpenFileName.return_value = (str(img_path), "")
            tab._browse_line_art()

        assert tab._prev_result is None
        assert tab._quadtree_leaves is None
