"""Player geometry independent of the graphics scene's changing size hint."""

from PySide6.QtCore import QSize, Signal
from PySide6.QtWidgets import QGraphicsView, QSizePolicy


class VideoView(QGraphicsView):
    viewport_resized = Signal()

    def __init__(self, scene):
        super().__init__(scene)
        self._display_size = QSize(1280, 720)
        self._fullscreen = False
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.set_display_size(1280, 720)

    def sizeHint(self):
        return self._display_size

    def minimumSizeHint(self):
        return QSize(0, 0)

    def set_display_size(self, width, height):
        self._display_size = QSize(width, height)
        self._update_constraints()

    def set_fullscreen(self, enabled):
        self._fullscreen = enabled
        self._update_constraints()

    def _update_constraints(self):
        if self._fullscreen:
            self.setMinimumSize(0, 0)
            self.setMaximumSize(16777215, 16777215)
        else:
            self.setMaximumWidth(self._display_size.width())
            # Scrollable pages provide no surplus height. Reserve the height
            # matching the selected canvas aspect at the width actually given.
            width = min(self.width(), self._display_size.width())
            height = max(1, round(width * self._display_size.height() / self._display_size.width()))
            if self.minimumHeight() != height or self.maximumHeight() != height:
                self.setFixedHeight(height)
        self.updateGeometry()

    def resizeEvent(self, event):
        self._update_constraints()
        super().resizeEvent(event)
        self.viewport_resized.emit()
