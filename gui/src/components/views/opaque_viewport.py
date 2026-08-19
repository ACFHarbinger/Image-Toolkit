from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget


class OpaqueViewport(QWidget):
    """A viewport for scroll areas that supports translucent and transparent backgrounds."""

    def __init__(self, parent=None, color_hex="transparent"):
        super().__init__(parent)
        self.setObjectName("gallery_viewport")
        self.background_color = (
            QColor(color_hex) if color_hex != "transparent" else QColor(0, 0, 0, 0)
        )
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)

    def paintEvent(self, event):
        if self.background_color.alpha() > 0:
            painter = QPainter(self)
            painter.fillRect(self.rect(), self.background_color)
            painter.end()
