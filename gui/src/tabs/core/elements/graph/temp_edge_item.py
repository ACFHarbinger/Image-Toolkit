from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPen, QPainter, QPainterPath
from PySide6.QtWidgets import QGraphicsObject

from .node_item import NodeItem, NODE_W, NODE_H


class TempEdgeItem(QGraphicsObject):
    """Temporary dashed edge that follows the mouse cursor during connection mode."""
    def __init__(self, source_item: NodeItem):
        super().__init__()
        self.source_item = source_item
        self.target_pos = QPointF(0, 0)
        self.setZValue(-1)

    def set_target_pos(self, pos: QPointF):
        self.target_pos = pos
        self.prepareGeometryChange()
        self.update()

    def boundingRect(self) -> QRectF:
        sp = self.source_item.pos() + QPointF(NODE_W / 2, NODE_H / 2)
        tp = self.target_pos
        rect = QRectF(sp, tp).normalized()
        return rect.adjusted(-50, -50, 50, 50)

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        sp = self.source_item.pos() + QPointF(NODE_W / 2, NODE_H / 2)
        tp = self.target_pos
        
        mx = (sp.x() + tp.x()) / 2
        my = (sp.y() + tp.y()) / 2 - 30
        path = QPainterPath()
        path.moveTo(sp)
        path.quadTo(QPointF(mx, my), tp)
        
        color = QColor("#f39c12")
        pen = QPen(color, 2, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)
