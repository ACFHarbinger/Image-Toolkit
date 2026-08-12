import os
from unittest.mock import MagicMock
from gui.src.components.dialogs.crawler_selection_dialogs import ManualSelectionDialog


def test_manual_selection_dialog_path_sanitization(tmp_path):
    # Create a real test image file on disk
    test_img = tmp_path / "1.jpeg"
    test_img.write_bytes(b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xFF\xDB\x00C\x00")

    # Item with query parameters in path
    item = {
        "path": str(test_img) + "?e095fd988a",
        "page_url": "https://example.com/gallery?page=1",
        "page_num": 1,
        "index_on_page": 1,
        "global_id": 1,
    }

def test_manual_selection_dialog_index_fallback(tmp_path):
    # Create real test image files on disk in tmp_path
    test_img = tmp_path / "downloaded_image_001.jpeg"
    test_img.write_bytes(b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xFF\xDB\x00C\x00")

    # Item with unmatched relative slug path
    item = {
        "path": "coser-machi-ma-ji-cyrene-swimsuit-xi-lan-ni-yong-zhuang-125-photos-bcb069cb6ff2828215c8e8d2705f2bd3-55970",
        "page_url": "https://example.com/gallery?page=1",
        "page_num": 1,
        "index_on_page": 1,
        "global_id": 1,
    }

    from PySide6.QtWidgets import QWidget, QLineEdit

    parent = QWidget()
    parent.download_dir_path = QLineEdit()
    parent.download_dir_path.setText(str(tmp_path))

    dialog = ManualSelectionDialog([item], parent=parent)

    assert str(test_img) in dialog.checkboxes
    assert dialog.checkboxes[str(test_img)].isChecked()
