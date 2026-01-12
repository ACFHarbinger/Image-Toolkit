from PySide6.QtWidgets import QWidget, QLabel
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QPixmap


class DragPreviewWindow(QWidget):
    """
    A frameless, transparent window that displays a drag preview
    and follows the cursor during manual drag operations.
    """

    def __init__(self, pixmap: QPixmap, parent=None):
        super().__init__(parent)

        # Make window frameless and stay on top
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.BypassWindowManagerHint
        )

        # Make background transparent
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        # Create label to display the pixmap
        self.label = QLabel(self)
        self.label.setPixmap(pixmap)
        self.label.resize(pixmap.size())

        # Resize window to fit pixmap
        self.resize(pixmap.size())

    def update_position(self, global_pos: QPoint):
        """Move the preview window to follow the cursor."""
        # Offset slightly so cursor isn't directly on the preview
        offset = QPoint(10, 10)
        self.move(global_pos + offset)
