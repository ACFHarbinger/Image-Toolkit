"""Unit tests for ImagePreviewWindow enhancements (§2.11)."""

import pytest
from gui.src.windows.image_preview_window import ImagePreviewWindow
from PIL import Image
from PySide6.QtGui import QGuiApplication


@pytest.fixture
def test_images(tmp_path):
    img1_path = tmp_path / "test_photo.png"
    img2_path = tmp_path / "test_landscape.jpg"

    im1 = Image.new("RGB", (640, 480), color="blue")
    im1.save(img1_path, "PNG")

    im2 = Image.new("RGB", (1920, 1080), color="red")
    im2.save(img2_path, "JPEG")

    return [str(img1_path), str(img2_path)]


@pytest.mark.gui
def test_image_preview_window_metadata_and_controls(q_app, test_images):
    preview = ImagePreviewWindow(test_images[0], all_paths=test_images, start_index=0)

    # 1. Metadata sidebar inspection (§2.11C)
    assert preview._info_panel.isVisible() is False
    preview._toggle_info_panel()
    assert preview._info_panel.isVisible() is True

    meta = preview._extract_image_metadata(test_images[0])
    assert meta["File Name"] == "test_photo.png"
    assert "640 × 480 px" in meta["Dimensions"]
    assert meta["Format"] == "PNG"

    # 2. Fit and zoom modes (§2.11B)
    preview._zoom_actual_pixels()
    assert preview.current_zoom_factor == 1.0

    preview._fit_to_width()
    assert preview.current_zoom_factor > 0

    preview._fit_to_height()
    assert preview.current_zoom_factor > 0

    # 3. Rotation (§2.11D)
    assert preview._rotation_degrees == 0
    preview._rotate(clockwise=True)
    assert preview._rotation_degrees == 90
    preview._rotate(clockwise=False)
    assert preview._rotation_degrees == 0

    # 4. Fullscreen toggle (§2.11A)
    preview._toggle_fullscreen()
    assert preview.isFullScreen() is True
    assert preview.btn_prev.isVisible() is False
    preview._toggle_fullscreen()
    assert preview.isFullScreen() is False
    assert preview.btn_prev.isVisible() is True

    # 5. Copy path to clipboard (§2.11F)
    preview.copy_path_to_clipboard()
    assert QGuiApplication.clipboard().text() == test_images[0]

    # 6. Navigation
    preview._navigate(1)
    assert preview.current_index == 1
    assert preview.image_path == test_images[1]

    preview.close()
