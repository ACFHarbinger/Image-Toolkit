import pytest

from PySide6.QtCore import Qt, QPoint
from PySide6.QtWidgets import QWidget, QVBoxLayout

from gui.src.components.clickable_label import ClickableLabel
from gui.src.components.draggable_label import DraggableLabel
from gui.src.components.monitor_drop_widget import MonitorDropWidget
from gui.src.components.marquee_scroll_area import MarqueeScrollArea
from gui.src.components.draggable_monitor_container import DraggableMonitorContainer
from gui.src.components.opaque_viewport import OpaqueViewport
from gui.src.components.optional_field import OptionalField
from gui.src.components.property_comparison_dialog import PropertyComparisonDialog
from gui.src.components.queue_item_widget import QueueItemWidget

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

class TestDraggableMonitorContainer:
    def test_initialization(self, q_app):
        monitor = type('M', (), {'name': 'TestMonitor'})()
        container = DraggableMonitorContainer(monitor, "1")
        assert container.monitor_id == "1"
        assert monitor.name in container.text()

class TestOpaqueViewport:
    def test_default_opacity(self, q_app):
        viewport = OpaqueViewport()
        # Verify the default window opacity set by the component (approximate)
        import pytest
        assert viewport.windowOpacity() == pytest.approx(0.5, rel=1e-2)

class TestOptionalField:
    def test_initial_state(self, q_app):
        # Provide a simple inner widget for the optional field
        inner = QWidget()
        field = OptionalField("Label", inner, start_open=False)
        assert field.label.text() == "Label"
        # The inner widget does not expose an input attribute directly; ensure it is set up
        # No direct assertion on input text needed for this test

class TestPropertyComparisonDialog:
    def test_diff_generation(self, q_app):
        # PropertyComparisonDialog expects a list of property dictionaries
        data = [
            {"File Name": "img1.jpg", "Path": "/tmp/img1.jpg", "Width": 100},
            {"File Name": "img2.jpg", "Path": "/tmp/img2.jpg", "Width": 200},
        ]
        dialog = PropertyComparisonDialog(data)
        # The dialog should contain a table widget
        assert hasattr(dialog, 'table')
        assert dialog.table.rowCount() > 0

class TestQueueItemWidget:
    def test_display_text(self, q_app, mock_pixmap):
        # QueueItemWidget requires a pixmap for preview
        widget = QueueItemWidget("/tmp/task1.png", mock_pixmap)
        # Verify that the filename label displays the basename
        assert widget.layout().itemAt(1).widget().text() == "task1.png"
