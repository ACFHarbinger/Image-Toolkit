import pytest
from gui.src.components import (
    ClickableLabel,
    DraggableLabel,
    DraggableMonitorContainer,
    MarqueeScrollArea,
    MonitorDropView,
    OpaqueViewport,
    OptionalField,
    PropertyComparisonDialog,
    QueueItemView,
)
from PySide6.QtCore import QPoint, Qt

# --- ClickableLabel Tests ---
from PySide6.QtTest import QTest as QTestUtils
from PySide6.QtWidgets import QVBoxLayout, QWidget

pytestmark = pytest.mark.gui


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

        QTestUtils.mouseClick(label, Qt.MouseButton.LeftButton)
        assert received_clicks == [path]

        QTestUtils.mouseDClick(label, Qt.MouseButton.LeftButton)
        assert received_doubles == [path]


# --- DraggableLabel Tests ---


class TestDraggableLabel:
    def test_init(self, q_app):
        label = DraggableLabel("test.jpg", 100)
        assert label.file_path == "test.jpg"
        assert label.width() == 100


# --- MonitorDropView Tests ---


class MockMonitor:
    def __init__(self, name="TestMonitor"):
        self.name = name


class TestMonitorDropView:
    def test_init_and_set_image(self, q_app, mock_pixmap):
        monitor = MockMonitor()
        widget = MonitorDropView(monitor, "1")  # pyrefly: ignore [bad-argument-type]

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
        QTestUtils.mousePress(viewport, Qt.MouseButton.LeftButton, pos=QPoint(10, 10))
        QTestUtils.mouseMove(viewport, pos=QPoint(50, 50))
        QTestUtils.mouseRelease(viewport, Qt.MouseButton.LeftButton)


class TestDraggableMonitorContainer:
    def test_initialization(self, q_app):
        monitor = type("M", (), {"name": "TestMonitor"})()
        container = DraggableMonitorContainer(monitor, "1")
        assert container.monitor_id == "1"
        assert monitor.name in container.text()


class TestOpaqueViewport:
    def test_default_opacity(self, q_app):
        from PySide6.QtCore import Qt
        viewport = OpaqueViewport()
        assert viewport.testAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        assert viewport.objectName() == "gallery_viewport"
        assert viewport.windowOpacity() == 1.0

    def test_rendered_backing_is_fully_opaque(self, q_app):
        viewport = OpaqueViewport()
        viewport.resize(64, 64)
        viewport._rebuild_backing()
        img = viewport._backing.toImage()
        assert img.pixelColor(10, 10).alpha() == 255

    def test_backing_fill_is_not_black_with_no_background_configured(self, q_app):
        # Regression: reading self.palette().window().color() as the base
        # fill produced a pitch-black backing on some setups, since QSS
        # background-color rules never write back into QPalette. The base
        # fill must come from the DARK_BG/LIGHT_BG theme constants instead.
        viewport = OpaqueViewport()
        viewport.resize(64, 64)
        viewport._rebuild_backing()
        img = viewport._backing.toImage()
        pixel = img.pixelColor(10, 10)
        assert (pixel.red(), pixel.green(), pixel.blue()) != (0, 0, 0)


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
        assert hasattr(dialog, "table")
        assert dialog.table.rowCount() > 0


class TestQueueItemView:
    def test_display_text(self, q_app, mock_pixmap):
        # QueueItemView requires a pixmap for preview
        widget = QueueItemView("/tmp/task1.png", mock_pixmap)
        # Verify that the filename label displays the basename
        assert widget.layout().itemAt(2).widget().text() == "task1.png" # pyrefly: ignore [missing-attribute]
