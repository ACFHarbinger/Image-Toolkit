import os
from typing import Dict
from PySide6.QtCore import Qt, Signal, QRectF, QPointF
from PySide6.QtGui import QPixmap, QPen, QBrush, QColor, QPainter
from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsObject


class _HandleItem(QGraphicsRectItem):
    """Resize handle shown at the four corners of a selected MergeCanvasItem."""

    _SIZE = 8

    def __init__(self, parent_item: "MergeCanvasItem", corner: str):
        half = self._SIZE // 2
        super().__init__(-half, -half, self._SIZE, self._SIZE, parent_item)
        self._parent = parent_item
        self.corner = corner  # "tl", "tr", "bl", "br"
        self.setFlags(
            QGraphicsRectItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsRectItem.GraphicsItemFlag.ItemSendsScenePositionChanges
        )
        self.setBrush(QBrush(Qt.GlobalColor.white))
        self.setPen(QPen(QColor("#5865f2"), 1))
        self.setZValue(10)

    def mouseMoveEvent(self, event):
        delta = event.scenePos() - event.lastScenePos()
        self._parent.resize_by_corner(self.corner, delta)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self._parent.reposition_handles()


class MergeCanvasItem(QGraphicsObject):
    """A movable, resizable image tile placed on the merge canvas."""

    geometry_changed = Signal()

    def __init__(self, path: str, pixmap: QPixmap, width: int, height: int):
        super().__init__()
        self.path = path
        self._pixmap = pixmap
        self._w = max(10, width)
        self._h = max(10, height)

        self.setFlags(
            QGraphicsObject.GraphicsItemFlag.ItemIsMovable
            | QGraphicsObject.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsObject.GraphicsItemFlag.ItemSendsGeometryChanges
        )

        self._highlighted = False
        self._handles: Dict[str, _HandleItem] = {}
        for corner in ("tl", "tr", "bl", "br"):
            self._handles[corner] = _HandleItem(self, corner)
        self.reposition_handles()
        self._set_handle_visible(False)

    # ── QGraphicsItem overrides ─────────────────────────────────────────────────

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, self._w, self._h)

    def paint(self, painter: QPainter, option, widget=None):
        if self._pixmap and not self._pixmap.isNull():
            painter.drawPixmap(QRectF(0, 0, self._w, self._h).toRect(), self._pixmap)
        else:
            painter.fillRect(QRectF(0, 0, self._w, self._h), QColor("#3a3d42"))
            painter.setPen(QColor("#888"))
            painter.drawText(
                QRectF(0, 0, self._w, self._h),
                Qt.AlignmentFlag.AlignCenter,
                os.path.basename(self.path),
            )

        if self.isSelected():
            painter.setPen(QPen(QColor("#5865f2"), 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(QRectF(1, 1, self._w - 2, self._h - 2))

        if self._highlighted:
            pen = QPen(QColor("#ffaa00"), 2, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(QRectF(3, 3, self._w - 6, self._h - 6))

    def itemChange(self, change, value):
        if change == QGraphicsObject.GraphicsItemChange.ItemPositionHasChanged:
            self.geometry_changed.emit()
        if change == QGraphicsObject.GraphicsItemChange.ItemSelectedHasChanged:
            self._set_handle_visible(bool(value))
        return super().itemChange(change, value)

    # ── Geometry ────────────────────────────────────────────────────────────────

    def reposition_handles(self):
        self._handles["tl"].setPos(0, 0)
        self._handles["tr"].setPos(self._w, 0)
        self._handles["bl"].setPos(0, self._h)
        self._handles["br"].setPos(self._w, self._h)

    def resize_by_corner(self, corner: str, delta: QPointF):
        dx, dy = delta.x(), delta.y()
        new_w = self._w
        new_h = self._h

        if "r" in corner:
            new_w = max(10, self._w + dx)
        elif "l" in corner:
            candidate = max(10, self._w - dx)
            if candidate != self._w:
                self.setX(self.x() + (self._w - candidate))
                new_w = candidate

        if "b" in corner:
            new_h = max(10, self._h + dy)
        elif "t" in corner:
            candidate = max(10, self._h - dy)
            if candidate != self._h:
                self.setY(self.y() + (self._h - candidate))
                new_h = candidate

        self.prepareGeometryChange()
        self._w = new_w
        self._h = new_h
        self.reposition_handles()
        self.update()
        self.geometry_changed.emit()

    def set_geometry(self, x: int, y: int, w: int, h: int):
        self.prepareGeometryChange()
        self._w = max(10, w)
        self._h = max(10, h)
        self.setPos(x, y)
        self.reposition_handles()
        self.update()

    def get_scene_rect(self) -> QRectF:
        return QRectF(self.x(), self.y(), self._w, self._h)

    def _set_handle_visible(self, visible: bool):
        for h in self._handles.values():
            h.setVisible(visible)

    def set_highlighted(self, val: bool):
        if self._highlighted != val:
            self._highlighted = val
            self.update()
