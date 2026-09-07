"""Tests for ImagePreviewWindow database_service parameter and legacy db_tab_ref shim (ui-arch-32 / #554)."""

from unittest.mock import MagicMock

import pytest
from gui.src.windows.image_preview_window import ImagePreviewWindow
from PySide6.QtGui import QColor, QImage

pytestmark = pytest.mark.gui


@pytest.fixture
def sample_image(tmp_path):
    """Create a temporary test image for previewing."""
    path = str(tmp_path / "test_preview.png")
    img = QImage(100, 100, QImage.Format.Format_RGB32)
    img.fill(QColor(128, 64, 32))
    img.save(path)
    return path


@pytest.fixture
def sample_images(tmp_path):
    """Create two temporary test images for batch navigation."""
    p1 = str(tmp_path / "test_1.png")
    p2 = str(tmp_path / "test_2.png")
    img1 = QImage(50, 50, QImage.Format.Format_RGB32)
    img1.fill(QColor(255, 0, 0))
    img1.save(p1)
    img2 = QImage(50, 50, QImage.Format.Format_RGB32)
    img2.fill(QColor(0, 255, 0))
    img2.save(p2)
    return [p1, p2]


def test_preview_window_database_service_arg(sample_image, q_app):
    mock_service = MagicMock()
    win = ImagePreviewWindow(
        image_path=sample_image,
        database_service=mock_service,
    )
    assert win.database_service is mock_service
    win.close()


def test_preview_window_legacy_db_tab_ref_rejected(sample_image, q_app):
    mock_service = MagicMock()
    with pytest.raises(TypeError, match="unexpected keyword argument 'db_tab_ref'"):
        ImagePreviewWindow(
            image_path=sample_image,
            db_tab_ref=mock_service,
        )


def test_preview_window_navigation(sample_images, q_app):
    mock_service = MagicMock()
    p1, p2 = sample_images
    win = ImagePreviewWindow(
        image_path=p1,
        database_service=mock_service,
        all_paths=[p1, p2],
        start_index=0,
    )
    assert win.current_index == 0
    assert win.image_path == p1

    # Navigate next
    win._navigate(1)
    assert win.current_index == 1
    assert win.image_path == p2

    # Navigate prev
    win._navigate(-1)
    assert win.current_index == 0
    assert win.image_path == p1
    win.close()
