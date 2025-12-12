import pytest
import os
from PySide6.QtCore import Qt, QPoint, QMimeData, QUrl, QSize
from PySide6.QtGui import QMouseEvent, QPixmap
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

from gui.components.clickable_label import ClickableLabel
from gui.components.draggable_label import DraggableLabel
from gui.components.monitor_drop_widget import MonitorDropWidget
from gui.components.marquee_scroll_area import MarqueeScrollArea

# --- ClickableLabel Tests ---

from PySide6.QtTest import QTest as QTestUtils

class TestClickableLabel:
    def test_signals(self, q_app):
        path = "test.jpg"
        label = ClickableLabel(path)
        
        # Test Click
        # We can't easily spy on signals without QSignalSpy which is not in PySide6 standard? 
        # Actually PySide6.QtTest.QSignalSpy exists? No, it's usually separate.
        # But we can connect a slot.
        
        received_clicks = []
        label.path_clicked.connect(lambda p: received_clicks.append(p))
        
        received_doubles = []
        label.path_double_clicked.connect(lambda p: received_doubles.append(p))
        
        QTestUtils.mouseClick(label, Qt.LeftButton)
        assert received_clicks == [path]
        
        QTestUtils.mouseDClick(label, Qt.LeftButton)
        assert received_doubles == [path]

# --- DraggableLabel Tests ---

class TestDraggableLabel:
    def test_init(self, q_app):
        label = DraggableLabel("test.jpg", 100)
        assert label.file_path == "test.jpg"
        assert label.width() == 100

# --- MonitorDropWidget Tests ---

class MockMonitor:
    def __init__(self, name="TestMonitor"):
        self.name = name

class TestMonitorDropWidget:
    def test_init_and_set_image(self, q_app, mock_pixmap):
        monitor = MockMonitor()
        widget = MonitorDropWidget(monitor, "1")
        
        assert widget.monitor_id == "1"
        assert "Monitor 1" in widget.text()
        
        # Test set_image with explicit pixmap (simulate success)
        widget.set_image("image.jpg", mock_pixmap)
        assert widget._current_pixmap is not None
        assert widget.pixmap() is not None
        
        # Test clear
        widget.clear()
        assert widget.image_path is None
        assert widget.pixmap().isNull()

# --- MarqueeScrollArea Tests ---

class TestMarqueeScrollArea:
    def test_marquee_logic(self, q_app):
        area = MarqueeScrollArea()
        container = QWidget()
        layout = QVBoxLayout(container)
        area.setWidget(container)
        area.resize(400, 400)
        area.show()

        # Add items
        label1 = ClickableLabel("item1.jpg")
        layout.addWidget(label1)
        
        # Simulate drag
        viewport = area.viewport()
        QTestUtils.mousePress(viewport, Qt.LeftButton, pos=QPoint(10, 10))
        QTestUtils.mouseMove(viewport, pos=QPoint(50, 50))
        QTestUtils.mouseRelease(viewport, Qt.LeftButton)
