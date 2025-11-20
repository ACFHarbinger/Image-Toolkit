from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QColor


class OpaqueViewport(QWidget):
    """A viewport that explicitly paints its background to prevent artifacts."""
    def __init__(self, parent=None, color_hex="#2c2f33"):
        super().__init__(parent)
        self.background_color = QColor(color_hex)
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.background_color)
