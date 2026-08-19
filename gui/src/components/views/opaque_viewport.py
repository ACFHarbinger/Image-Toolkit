from PySide6.QtCore import QEvent, QPoint, QRect, Qt
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QWidget


class OpaqueViewport(QWidget):
    """Opaque, cached gallery backing that preserves the background artwork.

    Qt can scroll-blit this viewport because every pixel is painted.  The
    cached backing still contains the window-aligned background plus a theme
    tint, so glassmorphism does not require transparent widget ancestry.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("gallery_viewport")
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self._backing = QPixmap()

        # Import lazily to avoid making the low-level components package and
        # the styles package depend on each other during module import.
        from ...styles.background_canvas import BackgroundCanvasController

        BackgroundCanvasController.instance().background_changed.connect(
            self._invalidate_backing
        )

    def _invalidate_backing(self):
        self._backing = QPixmap()
        self.update()

    def _rebuild_backing(self):
        if self.width() <= 0 or self.height() <= 0:
            return

        backing = QPixmap(self.size())
        base = self.palette().window().color()
        base.setAlpha(255)
        backing.fill(base)

        painter = QPainter(backing)
        root = self.window()
        offset = self.mapTo(root, QPoint(0, 0))

        from ...styles.background_canvas import BackgroundCanvasController

        controller = BackgroundCanvasController.instance()
        controller.render_background(
            painter,
            QRect(-offset.x(), -offset.y(), root.width(), root.height()),
        )

        # The opaque base below this translucent tint guarantees alpha=255.
        tint = (
            QColor(20, 24, 32, 72)
            if base.lightness() < 128
            else QColor(255, 255, 255, 72)
        )
        painter.fillRect(backing.rect(), tint)
        painter.end()
        self._backing = backing

    def paintEvent(self, event):
        if self._backing.size() != self.size() or self._backing.isNull():
            self._rebuild_backing()
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self._backing)
        painter.end()

    def resizeEvent(self, event):
        self._invalidate_backing()
        super().resizeEvent(event)

    def moveEvent(self, event):
        self._invalidate_backing()
        super().moveEvent(event)

    def changeEvent(self, event):
        if event.type() in (QEvent.Type.PaletteChange, QEvent.Type.StyleChange):
            self._invalidate_backing()
        super().changeEvent(event)
