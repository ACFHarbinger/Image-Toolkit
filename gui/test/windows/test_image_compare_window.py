"""Tests for ImageCompareWindow and multi-image comparison view (GUI/UX §2.27)."""

import pytest
from gui.src.components.virtual_gallery import VirtualGallery
from gui.src.windows.image_compare_window import ImageCompareWindow
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QImage, QKeyEvent

pytestmark = pytest.mark.gui


@pytest.fixture
def sample_images(tmp_path):
    """Create two test images with distinct colors and patterns for comparison."""
    path1 = str(tmp_path / "img1.png")
    path2 = str(tmp_path / "img2.png")

    img1 = QImage(200, 100, QImage.Format.Format_RGB32)
    img1.fill(QColor(255, 0, 0))  # Red
    img1.save(path1)

    img2 = QImage(200, 100, QImage.Format.Format_RGB32)
    img2.fill(QColor(0, 0, 255))  # Blue
    img2.save(path2)

    return path1, path2


def test_compare_window_initialization(sample_images, q_app):
    path1, path2 = sample_images
    win = ImageCompareWindow([path1, path2])
    win.show()

    assert len(win.image_paths) == 2
    assert len(win.panes) == 2
    assert win.current_mode == ImageCompareWindow.MODE_SIDE_BY_SIDE
    assert win.btn_side_by_side.isChecked()
    assert not win.btn_overlay.isChecked()
    assert not win.btn_diff.isChecked()
    assert win.btn_diff.isEnabled()
    win.close()


def test_compare_window_mode_switching(sample_images, q_app):
    path1, path2 = sample_images
    win = ImageCompareWindow([path1, path2])
    win.show()

    # 1. Switch to Overlay mode
    win.set_mode(ImageCompareWindow.MODE_OVERLAY)
    assert win.current_mode == ImageCompareWindow.MODE_OVERLAY
    assert win.btn_overlay.isChecked()
    assert win.stack.currentWidget() == win.single_viewport_scroll
    assert not win.sub_bar.isHidden()
    assert not win.btn_flip.isHidden()

    # Flip image in overlay mode
    assert win._active_overlay_index == 0
    win.flip_overlay_image()
    assert win._active_overlay_index == 1
    win.flip_overlay_image()
    assert win._active_overlay_index == 0

    # Opacity slider blend
    win.slider_opacity.setValue(50)
    assert win.slider_opacity.value() == 50

    # 2. Switch to Difference mode
    win.set_mode(ImageCompareWindow.MODE_DIFFERENCE)
    assert win.current_mode == ImageCompareWindow.MODE_DIFFERENCE
    assert win.btn_diff.isChecked()
    assert not win.combo_diff_boost.isHidden()

    # Diff amplification
    win.combo_diff_boost.setCurrentIndex(2)  # 5x
    assert win._diff_multiplier == 5.0
    win.close()


def test_compare_window_zoom_controls(sample_images, q_app):
    path1, path2 = sample_images
    win = ImageCompareWindow([path1, path2])
    win.show()

    initial_zoom = win.current_zoom_factor
    win.adjust_zoom(win.ZOOM_STEP)
    assert win.current_zoom_factor > initial_zoom
    assert "110%" in win.lbl_zoom.text() or f"{int(win.current_zoom_factor * 100)}%" in win.lbl_zoom.text()

    win.set_zoom(1.0)
    assert win.current_zoom_factor == 1.0
    assert win.lbl_zoom.text() == "100%"
    win.close()


def test_compare_window_pan_synchronization(sample_images, q_app):
    path1, path2 = sample_images
    win = ImageCompareWindow([path1, path2])
    win.show()

    pane0 = win.panes[0]
    pane1 = win.panes[1]

    # Set large zoom so scrollbars activate
    win.set_zoom(4.0)

    # Sync is enabled by default
    assert win.sync_pan_zoom is True
    pane0.scroll_by(QPoint(20, 20))
    win._on_pane_panned(pane0, QPoint(20, 20))

    rx0, ry0 = pane0.get_scroll_ratios()
    rx1, ry1 = pane1.get_scroll_ratios()
    assert abs(rx0 - rx1) < 0.05
    assert abs(ry0 - ry1) < 0.05
    win.close()


def test_compare_window_keyboard_navigation(sample_images, q_app):
    path1, path2 = sample_images
    win = ImageCompareWindow([path1, path2])
    win.show()

    # Key 2 -> Overlay
    event_2 = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_2, Qt.KeyboardModifier.NoModifier)
    win.keyPressEvent(event_2)
    assert win.current_mode == ImageCompareWindow.MODE_OVERLAY

    # Key Tab -> Flip image in overlay
    event_tab = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Tab, Qt.KeyboardModifier.NoModifier)
    win.keyPressEvent(event_tab)
    assert win._active_overlay_index == 1

    # Key 3 -> Difference
    event_3 = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_3, Qt.KeyboardModifier.NoModifier)
    win.keyPressEvent(event_3)
    assert win.current_mode == ImageCompareWindow.MODE_DIFFERENCE

    # Key 1 -> Side by side
    event_1 = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_1, Qt.KeyboardModifier.NoModifier)
    win.keyPressEvent(event_1)
    assert win.current_mode == ImageCompareWindow.MODE_SIDE_BY_SIDE
    win.close()


def test_compare_window_invalid_and_empty_paths(q_app):
    win = ImageCompareWindow(["/nonexistent/file1.png", "/nonexistent/file2.png"])
    win.show()
    assert len(win.panes) == 2
    assert win.panes[0].pixmap.isNull()
    win.close()


def test_virtual_gallery_compare_selected(sample_images, q_app):
    path1, path2 = sample_images
    vg = VirtualGallery()
    vg.show()
    vg.set_paths([path1, path2])

    # No selection -> returns None
    assert vg.compare_selected() is None

    # Select all -> returns ImageCompareWindow
    vg.select_all()
    win = vg.compare_selected()
    assert win is not None
    assert len(win.image_paths) == 2
    win.close()
    vg.close()
