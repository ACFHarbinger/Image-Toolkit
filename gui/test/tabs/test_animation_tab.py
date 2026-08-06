from unittest.mock import patch

import numpy as np
import pytest
from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor, QImage

from cel_shaded_generator_gui.tabs.animation_tab import MangaAnimationTab

pytestmark = pytest.mark.gui


def _save_frame(path, w=20, h=20, color=(180, 180, 180)):
    img = QImage(w, h, QImage.Format.Format_RGB888)
    img.fill(QColor(*color))
    img.save(str(path))
    return str(path)


def _make_frame_files(tmp_path, n=3, w=20, h=20):
    paths = []
    for i in range(n):
        p = tmp_path / f"frame_{i:02d}.png"
        paths.append(_save_frame(p, w=w, h=h))
    return paths


class TestMangaAnimationTab:
    def test_constructs_with_no_frames(self, q_app):
        tab = MangaAnimationTab()
        assert tab._frames == []
        assert tab.frame_slider.isEnabled() is False
        assert tab.preview_slider.isEnabled() is False

    def test_load_frames_populates_slider_and_canvas(self, q_app, tmp_path):
        tab = MangaAnimationTab()
        paths = _make_frame_files(tmp_path, n=4)

        with patch("cel_shaded_generator_gui.tabs.animation_tab.QFileDialog") as mock_dialog:
            mock_dialog.getOpenFileNames.return_value = (paths, "")
            tab._browse_frames()

        assert len(tab._frames) == 4
        assert tab.frame_slider.isEnabled() is True
        assert tab.frame_slider.maximum() == 3
        assert tab.canvas.has_line_art() is True
        assert "4 frames" in tab.status_label.text()

    def test_load_too_few_frames_shows_info(self, q_app, tmp_path):
        tab = MangaAnimationTab()
        paths = _make_frame_files(tmp_path, n=1)

        with patch("cel_shaded_generator_gui.tabs.animation_tab.QFileDialog") as mock_dialog:
            mock_dialog.getOpenFileNames.return_value = (paths, "")
            with patch("cel_shaded_generator_gui.tabs.animation_tab.QMessageBox") as mock_box:
                tab._browse_frames()
                mock_box.information.assert_called_once()
        assert tab._frames == []

    def test_load_mismatched_dimensions_shows_warning(self, q_app, tmp_path):
        tab = MangaAnimationTab()
        p1 = _save_frame(tmp_path / "a.png", w=20, h=20)
        p2 = _save_frame(tmp_path / "b.png", w=30, h=30)

        with patch("cel_shaded_generator_gui.tabs.animation_tab.QFileDialog") as mock_dialog:
            mock_dialog.getOpenFileNames.return_value = ([p1, p2], "")
            with patch("cel_shaded_generator_gui.tabs.animation_tab.QMessageBox") as mock_box:
                tab._browse_frames()
                mock_box.warning.assert_called_once()
        assert tab._frames == []

    def test_switching_frames_commits_and_restores_scribbles(self, q_app, tmp_path):
        tab = MangaAnimationTab()
        paths = _make_frame_files(tmp_path, n=3)
        with patch("cel_shaded_generator_gui.tabs.animation_tab.QFileDialog") as mock_dialog:
            mock_dialog.getOpenFileNames.return_value = (paths, "")
            tab._browse_frames()

        # Paint on frame 0.
        tab.canvas.set_pen_color(QColor(10, 200, 30))
        tab.canvas._paint_line(QPointF(5, 5), QPointF(5, 5))
        assert tab.canvas.has_scribbles() is True

        # Switch to frame 1 -- frame 0's scribble should be committed to the
        # store, and the canvas should show a blank (unscribbled) frame 1.
        tab.frame_slider.setValue(1)
        assert tab._current_frame_index == 1
        assert 0 in tab._scribble_images
        assert tab.canvas.has_scribbles() is False

        # Switch back to frame 0 -- the scribble should be restored.
        tab.frame_slider.setValue(0)
        assert tab.canvas.has_scribbles() is True

    def test_clear_current_scribbles_removes_from_store(self, q_app, tmp_path):
        tab = MangaAnimationTab()
        paths = _make_frame_files(tmp_path, n=2)
        with patch("cel_shaded_generator_gui.tabs.animation_tab.QFileDialog") as mock_dialog:
            mock_dialog.getOpenFileNames.return_value = (paths, "")
            tab._browse_frames()

        tab.canvas._paint_line(QPointF(5, 5), QPointF(5, 5))
        tab._commit_current_scribble()
        assert 0 in tab._scribble_images

        tab._clear_current_scribbles()
        assert 0 not in tab._scribble_images
        assert tab.canvas.has_scribbles() is False

    def test_pen_color_and_width_update_canvas(self, q_app):
        tab = MangaAnimationTab()
        with patch("cel_shaded_generator_gui.tabs.animation_tab.QColorDialog") as mock_dialog:
            mock_dialog.getColor.return_value = QColor(7, 8, 9)
            tab._pick_pen_color()
        assert tab.canvas.pen_color().getRgb()[:3] == (7, 8, 9)

        tab.pen_width_slider.setValue(25)
        assert tab.canvas._pen_width == 25

    def test_colorize_without_frames_shows_info(self, q_app):
        tab = MangaAnimationTab()
        with patch("cel_shaded_generator_gui.tabs.animation_tab.QMessageBox") as mock_box:
            tab._run_colorize()
            mock_box.information.assert_called_once()

    def test_colorize_without_scribbles_shows_info(self, q_app, tmp_path):
        tab = MangaAnimationTab()
        paths = _make_frame_files(tmp_path, n=2)
        with patch("cel_shaded_generator_gui.tabs.animation_tab.QFileDialog") as mock_dialog:
            mock_dialog.getOpenFileNames.return_value = (paths, "")
            tab._browse_frames()

        with patch("cel_shaded_generator_gui.tabs.animation_tab.QMessageBox") as mock_box:
            tab._run_colorize()
            mock_box.information.assert_called_once()

    def test_run_colorize_starts_worker_with_correct_data(self, q_app, tmp_path):
        tab = MangaAnimationTab()
        paths = _make_frame_files(tmp_path, n=3, w=15, h=15)
        with patch("cel_shaded_generator_gui.tabs.animation_tab.QFileDialog") as mock_dialog:
            mock_dialog.getOpenFileNames.return_value = (paths, "")
            tab._browse_frames()

        tab.canvas.set_pen_color(QColor(255, 0, 0))
        tab.canvas._paint_line(QPointF(3, 3), QPointF(3, 3))

        # `AnimationColorizeWorker` is mocked here rather than letting a real
        # background QThread run colorize_scribble_sequence() -- unlike
        # test_colorization_tab.py's equivalent real-thread test (which is
        # safe because it uses colorize_scribble()'s own solve path),
        # gui/test/conftest.py globally mocks `cv2` (`sys.modules["cv2"] =
        # MagicMock()`), and colorize_scribble_sequence() calling
        # cv2.cvtColor() from inside a real background thread against that
        # mock reproducibly corrupted memory ("double free or corruption")
        # while developing this test -- confirmed via a minimal repro, not
        # guessed. See test_animation_worker.py's note on the same
        # constraint for the worker-level tests, and the codebase's own
        # documented "real cross-thread signal delivery is unreliable inside
        # a test's own control flow" constraint for why dispatch-only
        # coverage (args, button state, .start() called) is the right bar
        # here regardless.
        with patch(
            "cel_shaded_generator_gui.tabs.animation_tab.AnimationColorizeWorker"
        ) as mock_worker_cls:
            mock_worker = mock_worker_cls.return_value
            tab._run_colorize()

            assert tab.btn_colorize.isEnabled() is False
            args, kwargs = mock_worker_cls.call_args
            gray_stack, scribble_rgb_stack, scribble_mask_stack = args
            assert gray_stack.shape == (3, 15, 15)
            assert scribble_rgb_stack.shape == (3, 15, 15, 3)
            assert scribble_mask_stack.shape == (3, 15, 15)
            assert scribble_mask_stack[0].any()
            assert kwargs["refine"] is False
            mock_worker.start.assert_called_once()

    def test_run_colorize_passes_refine_flag_to_worker(self, q_app, tmp_path):
        """Verifies the checkbox -> worker-constructor wiring without
        letting a real worker thread run (see the note on
        test_run_colorize_starts_worker_with_correct_data above for why a
        real graph-cut-refine background solve is avoided in tests)."""
        tab = MangaAnimationTab()
        paths = _make_frame_files(tmp_path, n=2, w=10, h=10)
        with patch("cel_shaded_generator_gui.tabs.animation_tab.QFileDialog") as mock_dialog:
            mock_dialog.getOpenFileNames.return_value = (paths, "")
            tab._browse_frames()

        tab.canvas._paint_line(QPointF(2, 2), QPointF(2, 2))
        tab.chk_refine.setChecked(True)

        with patch(
            "cel_shaded_generator_gui.tabs.animation_tab.AnimationColorizeWorker"
        ) as mock_worker_cls:
            mock_worker = mock_worker_cls.return_value
            tab._run_colorize()
            _, kwargs = mock_worker_cls.call_args
            assert kwargs["refine"] is True
            mock_worker.start.assert_called_once()

    def test_on_colorize_finished_enables_preview(self, q_app):
        tab = MangaAnimationTab()
        result = np.full((3, 10, 10, 3), 255, dtype=np.uint8)
        tab._on_colorize_finished(result)

        assert tab._result_stack is result
        assert tab.preview_slider.isEnabled() is True
        assert tab.preview_slider.maximum() == 2
        assert not tab.preview_label.pixmap().isNull()
        assert "complete" in tab.status_label.text().lower()

    def test_on_colorize_error_shows_critical(self, q_app):
        tab = MangaAnimationTab()
        with patch("cel_shaded_generator_gui.tabs.animation_tab.QMessageBox") as mock_box:
            tab._on_colorize_error("boom")
            mock_box.critical.assert_called_once()
        assert "failed" in tab.status_label.text().lower()

    def test_preview_slider_updates_label(self, q_app):
        tab = MangaAnimationTab()
        result = np.stack([np.full((10, 10, 3), v, dtype=np.uint8) for v in (0, 128, 255)], axis=0)
        tab._on_colorize_finished(result)

        tab.preview_slider.setValue(2)
        assert "3/3" in tab.preview_frame_label.text()

    def test_export_without_result_shows_info(self, q_app):
        tab = MangaAnimationTab()
        with patch("cel_shaded_generator_gui.tabs.animation_tab.QMessageBox") as mock_box:
            tab._export_result()
            mock_box.information.assert_called_once()

    def test_export_writes_frame_files(self, q_app, tmp_path):
        tab = MangaAnimationTab()
        result = np.full((2, 10, 10, 3), 200, dtype=np.uint8)
        tab._on_colorize_finished(result)

        out_dir = tmp_path / "export"
        out_dir.mkdir()
        with patch("cel_shaded_generator_gui.tabs.animation_tab.QFileDialog") as mock_dialog:
            mock_dialog.getExistingDirectory.return_value = str(out_dir)
            tab._export_result()

        assert (out_dir / "frame_0000.png").exists()
        assert (out_dir / "frame_0001.png").exists()
        assert "Exported 2 frames" in tab.status_label.text()
