from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QWidget
from .monitor_drop_widget import MonitorDropWidget


class DraggableMonitorContainer(QWidget):
    """
    A Custom Container that accepts MonitorDropWidget drops and reorders them.
    It relies on MonitorDropWidget IGNORING the drag event so it bubbles up here.
    """

    def __init__(self, monitor=None, monitor_id=None, parent=None):
        super().__init__(parent)
        self.monitor = monitor
        self.monitor_id = monitor_id
        self.layout_hbox = QHBoxLayout(self)
        self.layout_hbox.setSpacing(15)
        self.layout_hbox.setAlignment(Qt.AlignCenter)
        self.setAcceptDrops(True)

    def text(self) -> str:
        """Return a simple textual representation for testing.
        Includes monitor name if available.
        """
        if self.monitor is not None:
            return f"{self.monitor.name}"
        return ""


    def addWidget(self, widget):
        self.layout_hbox.addWidget(widget)

    def dragEnterEvent(self, event):
        # We accept drops if the source is a MonitorDropWidget
        if event.source() and isinstance(event.source(), MonitorDropWidget):
            event.accept()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.source() and isinstance(event.source(), MonitorDropWidget):
            event.setDropAction(Qt.MoveAction)
            event.accept()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        source = event.source()
        if isinstance(source, MonitorDropWidget):
            pos = event.position().toPoint()

            # Determine new index
            target_index = -1
            count = self.layout_hbox.count()

            # Find insertion point
            for i in range(count):
                item = self.layout_hbox.itemAt(i)
                widget = item.widget()
                if widget is None or widget == source:
                    continue

                # Check if we dropped to the left of this widget's center
                widget_center = widget.x() + (widget.width() / 2)
                if pos.x() < widget_center:
                    target_index = i
                    break

            if target_index == -1:
                target_index = count

            # Reorder
            self.layout_hbox.removeWidget(source)
            self.layout_hbox.insertWidget(target_index, source)
            event.accept()

            # Force visual refresh
            self.update()
        else:
            super().dropEvent(event)

    def clear_widgets(self):
        while self.layout_hbox.count():
            item = self.layout_hbox.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
