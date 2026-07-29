"""``_ClickableImageLabel`` -- source image display with click-to-coordinate mapping.

Extracted from ``entity_recon_tab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QLabel


class _ClickableImageLabel(QLabel):
    """Displays the source image and reports clicks in *original* image
    coordinates (accounting for the letterboxed scale)."""

    clicked = Signal(int, int)  # x, y in original-image pixels

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(320, 320)
        self.setText("Load an image to begin.")
        self.setStyleSheet("color: #999; border: 1px dashed #4f545c; background: #2c2f33;")
        self._src_w = 0
        self._src_h = 0
        self._scaled_w = 0
        self._scaled_h = 0
        self._off_x = 0
        self._off_y = 0

    def set_source_pixmap(self, pixmap: QPixmap, src_w: int, src_h: int):
        self._src_w, self._src_h = src_w, src_h
        self._rescale(pixmap)

    def _rescale(self, pixmap: QPixmap):
        if pixmap.isNull():
            return
        area = self.size()
        scaled = pixmap.scaled(area, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self._scaled_w, self._scaled_h = scaled.width(), scaled.height()
        self._off_x = max(0, (area.width() - self._scaled_w) // 2)
        self._off_y = max(0, (area.height() - self._scaled_h) // 2)
        self.setPixmap(scaled)

    def mousePressEvent(self, event):
        if self._src_w and self._scaled_w and self.pixmap() and not self.pixmap().isNull():
            lx = event.position().x() - self._off_x
            ly = event.position().y() - self._off_y
            if 0 <= lx < self._scaled_w and 0 <= ly < self._scaled_h:
                x = int(lx / self._scaled_w * self._src_w)
                y = int(ly / self._scaled_h * self._src_h)
                self.clicked.emit(x, y)
        super().mousePressEvent(event)


__all__ = ["_ClickableImageLabel"]
