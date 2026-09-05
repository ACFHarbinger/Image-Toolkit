import os
import sys
from pathlib import Path
from unittest.mock import patch

from gui.src.components.gallery.virtual_gallery_model import VirtualGalleryModel
from gui.src.components.gallery.widget import VirtualGallery
from gui.src.utils.undo_manager import UndoManager
from PySide6.QtWidgets import QApplication

# Ensure QApplication exists
if not QApplication.instance():
    app = QApplication(sys.argv)


def test_virtual_gallery_model_rename():
    model = VirtualGalleryModel()
    paths = ["/tmp/test_1.png", "/tmp/test_2.png"]
    model.set_paths(paths)

    # Set some metadata
    model.set_overlay_metadata("/tmp/test_1.png", rating="safe", resolution=(1920, 1080))

    assert model.rename_path("/tmp/test_1.png", "/tmp/test_1_renamed.png")
    assert model.path_at(0) == "/tmp/test_1_renamed.png"
    assert model.data(model.index(0, 0), VirtualGalleryModel.RatingRole) == "safe"
    assert model.data(model.index(0, 0), VirtualGalleryModel.ResolutionRole) == (1920, 1080)

    # Renaming non-existent path returns False
    assert not model.rename_path("/non/existent.png", "/other.png")


def test_virtual_gallery_view_rename_and_undo(tmp_path: Path):
    f1 = tmp_path / "original_image.png"
    f1.write_text("dummy image data")

    gallery = VirtualGallery()
    gallery.set_paths([str(f1)])
    gallery.view.select_all()

    renamed_signals: list[tuple[str, str]] = []
    gallery.path_renamed.connect(lambda old, new: renamed_signals.append((old, new)))

    # Mock QInputDialog.getText to return ("new_image", True)
    with patch("PySide6.QtWidgets.QInputDialog.getText", return_value=("new_image", True)):
        res = gallery.rename_selected_file()
        assert res is not None
        assert os.path.basename(res) == "new_image.png"
        assert not f1.exists()
        assert (tmp_path / "new_image.png").exists()

    assert len(renamed_signals) == 1
    assert renamed_signals[0] == (str(f1), str(tmp_path / "new_image.png"))

    # Undo rename
    undo_mgr = UndoManager.instance()
    assert undo_mgr.can_undo()
    assert undo_mgr.undo()

    assert f1.exists()
    assert not (tmp_path / "new_image.png").exists()


def test_virtual_gallery_view_rename_sanitization(tmp_path: Path):
    # Create valid file
    valid_orig = tmp_path / "sample_file.png"
    valid_orig.write_text("content")

    gallery = VirtualGallery()
    gallery.set_paths([str(valid_orig)])
    gallery.view.select_all()

    with patch("PySide6.QtWidgets.QInputDialog.getText", return_value=("new:name*test?", True)):
        res = gallery.rename_selected_file()
        assert res is not None
        assert "new_name_test_.png" in res
        assert (tmp_path / "new_name_test_.png").exists()
