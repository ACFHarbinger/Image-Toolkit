import os
import tempfile
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPainter
from gui.src.components.dialogs.thumbnail_file_picker import ThumbnailFilePicker


def test_thumbnail_file_picker_initialization(q_app, tmp_path):
    # Create test image files
    img1 = tmp_path / "test1.png"
    img2 = tmp_path / "test2.jpg"
    txt = tmp_path / "note.txt"
    
    # Save a small valid PNG
    image = QImage(64, 64, QImage.Format.Format_RGB32)
    image.fill(QColor("red"))
    image.save(str(img1))
    image.save(str(img2))
    txt.write_text("not an image")
    
    dialog = ThumbnailFilePicker(
        caption="Test Picker",
        start_dir=str(tmp_path),
        single_selection=True,
    )
    
    assert dialog.windowTitle() == "Test Picker"
    assert dialog._current_dir == str(tmp_path)
    assert len(dialog._item_map) == 2
    assert str(img1) in dialog._item_map
    assert str(img2) in dialog._item_map
    assert str(txt) not in dialog._item_map
    
    dialog.close()


def test_thumbnail_file_picker_selection(q_app, tmp_path):
    img1 = tmp_path / "photo.png"
    image = QImage(32, 32, QImage.Format.Format_RGB32)
    image.fill(QColor("blue"))
    image.save(str(img1))
    
    dialog = ThumbnailFilePicker(
        start_dir=str(tmp_path),
        single_selection=True,
    )
    
    # Select item in grid
    item = dialog._item_map[str(img1)]
    item.setSelected(True)
    dialog._update_status()
    
    assert "photo.png" in dialog._status_label.text()
    dialog._accept()
    assert dialog.selected_path() == str(img1)
    
    dialog.close()
