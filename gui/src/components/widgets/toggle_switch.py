"""Animated pill toggle switch widget for modern creative suite settings (§2.37)."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Property, QEasingCurve, QPropertyAnimation, QRectF, QSize, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPaintEvent
from PySide6.QtWidgets import QAbstractButton, QWidget


class ToggleSwitch(QAbstractButton):
    """Sleek animated toggle switch (iOS / Fluent style) replacing checkboxes."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(False)
        self.setFixedSize(46, 24)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._thumb_position: float = 3.0
        self._anim = QPropertyAnimation(self, b"thumb_position", self)
        self._anim.setDuration(160)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

        self.toggled.connect(self._on_toggled)

    def sizeHint(self) -> QSize:
        return QSize(46, 24)

    def _get_thumb_position(self) -> float:
        return self._thumb_position

    def _set_thumb_position(self, pos: float) -> None:
        self._thumb_position = pos
        self.update()

    thumb_position = Property(float, _get_thumb_position, _set_thumb_position)

    def _on_toggled(self, checked: bool) -> None:
        end_pos = 25.0 if checked else 3.0
        self._anim.stop()
        self._anim.setStartValue(self._thumb_position)
        self._anim.setEndValue(end_pos)
        self._anim.start()

    def setChecked(self, checked: bool) -> None:
        super().setChecked(checked)
        self._thumb_position = 25.0 if checked else 3.0
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        radius = h / 2.0

        # Background track color
        track_color = QColor("#00bcd4") if self.isChecked() else QColor("#3e3e42")
        p.setBrush(QBrush(track_color))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(0, 0, w, h), radius, radius)

        # Thumb circle
        thumb_color = QColor("#ffffff")
        thumb_radius = 9.0
        p.setBrush(QBrush(thumb_color))
        p.drawEllipse(QRectF(self._thumb_position, (h - 2 * thumb_radius) / 2.0, 2 * thumb_radius, 2 * thumb_radius))
        p.end()


__all__ = ["ToggleSwitch"]
