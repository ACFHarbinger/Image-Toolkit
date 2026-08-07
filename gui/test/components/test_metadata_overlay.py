import pytest
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from gui.src.components.labels.metadata_overlay import MetadataOverlay
from gui.src.components.labels.clickable_label import ClickableLabel
import sys

# Ensure QApplication exists
if not QApplication.instance():
    app = QApplication(sys.argv)

def test_metadata_overlay_initialization(tmp_path):
    test_file = tmp_path / "test.jpg"
    test_file.write_text("dummy")
    
    overlay = MetadataOverlay(str(test_file))
    
    assert overlay.file_path == str(test_file)
    assert overlay.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    assert overlay.isHidden()
    assert overlay.filename_label.text() == "test.jpg"

def test_metadata_overlay_file_size(tmp_path):
    test_file = tmp_path / "test2.jpg"
    with open(test_file, 'wb') as f:
        f.write(b'0' * 2048) # 2KB
        
    overlay = MetadataOverlay(str(test_file))
    assert overlay.size_label.text() == "2.0 KB"

def test_metadata_overlay_invalid_image(tmp_path):
    test_file = tmp_path / "invalid.jpg"
    test_file.write_text("not an image")
    
    overlay = MetadataOverlay(str(test_file))
    # Should say "Unknown dims" for invalid image
    assert overlay.dim_label.text() == "Unknown dims"

def test_metadata_overlay_missing_file():
    overlay = MetadataOverlay("/path/that/does/not/exist.jpg")
    assert overlay.dim_label.text() == "Unknown dims"
    assert overlay.size_label.text() == "Unknown size"

def test_clickable_label_integration(tmp_path):
    test_file = tmp_path / "test3.jpg"
    test_file.write_text("dummy")
    
    label = ClickableLabel(str(test_file))
    
    assert hasattr(label, '_metadata_overlay')
    overlay = label._metadata_overlay
    
    assert overlay.isHidden()
    
    # Fake enter event
    label.enterEvent(None)
    assert not overlay.isHidden()
    assert overlay.size() == label.size()
    
    # Fake leave event
    label.leaveEvent(None)
    assert overlay.isHidden()

