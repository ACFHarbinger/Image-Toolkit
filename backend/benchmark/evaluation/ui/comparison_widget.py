"""Interactive slider (swipe) comparison — a QSlider revealing image A on
the left and image B on the right of a moving split line, the classic
Fiji/ImageMagick "before/after" compositing tool.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QPen, QPixmap
from PySide6.QtWidgets import QLabel, QSlider, QVBoxLayout, QWidget

from .panel_base import bgr_to_qimage


class SwipeCompareWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._img_a: Optional[np.ndarray] = None
        self._img_b: Optional[np.ndarray] = None
        self._split = 0.5

        layout = QVBoxLayout(self)
        self._canvas = QLabel()
        self._canvas.setMinimumSize(280, 220)
        layout.addWidget(self._canvas)
        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, 100)
        self._slider.setValue(50)
        self._slider.valueChanged.connect(self._on_slider)
        layout.addWidget(self._slider)

    def set_images(self, a: Optional[np.ndarray], b: Optional[np.ndarray]) -> None:
        self._img_a, self._img_b = a, b
        self._render()

    def _on_slider(self, value: int) -> None:
        self._split = value / 100.0
        self._render()

    def _render(self) -> None:
        if self._img_a is None or self._img_b is None:
            self._canvas.clear()
            return
        import cv2

        h, w = self._img_a.shape[:2]
        b = self._img_b
        if b.shape[:2] != (h, w):
            b = cv2.resize(b, (w, h), interpolation=cv2.INTER_AREA)
        split_x = int(w * self._split)
        composite = self._img_a.copy()
        composite[:, split_x:] = b[:, split_x:]

        pix = QPixmap.fromImage(bgr_to_qimage(composite))
        painter = QPainter(pix)
        painter.setPen(QPen(Qt.GlobalColor.yellow, 3))
        painter.drawLine(split_x, 0, split_x, h)
        painter.end()
        self._canvas.setPixmap(pix.scaled(
            self._canvas.width() or w, self._canvas.height() or h,
            Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation,
        ))

    def resizeEvent(self, event) -> None:  # noqa: D102 - Qt override
        super().resizeEvent(event)
        self._render()
