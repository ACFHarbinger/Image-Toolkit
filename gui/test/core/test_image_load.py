from pathlib import Path
from unittest.mock import patch

import pytest
from gui.src.utils.image_load import IMAGE_FILE_DIALOG_FILTER, load_qimage
from PIL import Image
from PySide6.QtGui import QImage

pytestmark = pytest.mark.gui


def test_image_file_dialog_filter_includes_avif():
    assert "*.avif" in IMAGE_FILE_DIALOG_FILTER
    assert "*.webp" in IMAGE_FILE_DIALOG_FILTER
    assert "*.tiff" in IMAGE_FILE_DIALOG_FILTER


def test_load_qimage_reads_avif_via_pillow(q_app, tmp_path):
    avif_path = tmp_path / "thumb.avif"
    Image.new("RGB", (8, 8), color=(255, 0, 0)).save(avif_path, format="AVIF")

    assert QImage(str(avif_path)).isNull()

    img = load_qimage(str(avif_path))
    assert not img.isNull()
    assert img.width() == 8
    assert img.height() == 8


def test_browse_reference_image_uses_avif_filter(q_app, tmp_path):
    from gui.src.tabs.core.elements.display.common.base_detail_panel import (
        BaseDetailPanel,
    )

    panel = BaseDetailPanel()
    avif_path = tmp_path / "cover.avif"
    Image.new("RGB", (4, 4), color=(0, 128, 255)).save(avif_path, format="AVIF")

    with patch(
        "gui.src.tabs.core.elements.display.common.base_detail_panel.QFileDialog.getOpenFileName",
        return_value=(str(avif_path), IMAGE_FILE_DIALOG_FILTER),
    ) as mock_dialog:
        result = panel._browse_image_helper("entry-123")

    mock_dialog.assert_called_once()
    assert mock_dialog.call_args[0][3] == IMAGE_FILE_DIALOG_FILTER
    assert result.endswith(".avif")
    assert Path(result).exists()