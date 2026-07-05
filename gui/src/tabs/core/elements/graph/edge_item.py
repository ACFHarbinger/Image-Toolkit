import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPainterPathStroker, QPen, QPolygonF
from PySide6.QtWidgets import QGraphicsItem, QGraphicsObject

from .data import EdgeData
from .node_item import NODE_H, NODE_W, NodeItem


class EdgeItem(QGraphicsObject):
    """Visual directed edge (arrow) between two NodeItems, with an ID label."""

    def __init__(self, edge_data: EdgeData, src: NodeItem, tgt: NodeItem):
        super().__init__()
        self.edge_data = edge_data
        self.src = src
        self.tgt = tgt
        self._path = QPainterPath()
        self._arrow_tip = QPointF(0, 0)
        self._arrow_angle = 0.0
        self._label_pos = QPointF(0, 0)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setZValue(-1)
        self._update_path()

    def _is_self(self) -> bool:
        return self.edge_data.source_id == self.edge_data.target_id

    def update_path(self):
        self.prepareGeometryChange()
        self._update_path()
        self.update()

    def _node_center(self, item: NodeItem) -> QPointF:
        return item.mapToScene(QPointF(NODE_W / 2, NODE_H / 2))

    def _update_path(self):
        if self._is_self():
            self._build_self_loop()
        else:
            self._build_arrow()

    def _build_self_loop(self):
        cx = self.src.mapToScene(QPointF(NODE_W / 2, 0)).x()
        top = self.src.mapToScene(QPointF(NODE_W / 2, 0)).y()
        r = 28
        self._path = QPainterPath()
        self._path.moveTo(cx - 15, top)
        self._path.cubicTo(
            QPointF(cx - 15, top - r * 2.5),
            QPointF(cx + 15, top - r * 2.5),
            QPointF(cx + 15, top),
        )
        self._arrow_tip = QPointF(cx + 15, top)
        self._arrow_angle = math.pi / 2
        self._label_pos = QPointF(cx, top - r * 2.0)

    def _rect_edge_point(self, item: NodeItem, towards: QPointF) -> QPointF:
        center = self._node_center(item)
        dx = towards.x() - center.x()
        dy = towards.y() - center.y()
        hw, hh = NODE_W / 2 + 4, NODE_H / 2 + 4
        t = (hw / abs(dx) if dx != 0 else 1.0) if abs(dx) * hh >= abs(dy) * hw else hh / abs(dy) if dy != 0 else 1.0
        return QPointF(center.x() + dx * t, center.y() + dy * t)

    def _build_arrow(self):
        sc = self._node_center(self.src)
        tc = self._node_center(self.tgt)
        sp = self._rect_edge_point(self.src, tc)
        tp = self._rect_edge_point(self.tgt, sc)

        dx = tp.x() - sp.x()
        dy = tp.y() - sp.y()
        length = math.hypot(dx, dy) or 1.0
        # Perpendicular offset for a slight curve to distinguish parallel edges
        offset = min(40.0, length * 0.15)
        mx = (sp.x() + tp.x()) / 2 - dy * offset / length
        my = (sp.y() + tp.y()) / 2 + dx * offset / length

        self._path = QPainterPath()
        self._path.moveTo(sp)
        self._path.quadTo(QPointF(mx, my), tp)

        self._arrow_tip = tp
        self._arrow_angle = math.atan2(tp.y() - my, tp.x() - mx)
        self._label_pos = QPointF(mx, my)

    def boundingRect(self) -> QRectF:
        return self._path.boundingRect().adjusted(-20, -20, 20, 20)

    def shape(self) -> QPainterPath:
        # Widen path for easier clicking
        stroker = QPainterPathStroker()
        stroker.setWidth(12)
        shape_path = stroker.createStroke(self._path)

        # Add the label rectangle to the clickable shape
        lp = self._label_pos
        repeat = getattr(self.edge_data, "repeat_count", 1)
        label_w = 28 if repeat <= 1 else 28 + 9 * len(str(repeat))
        text_rect = QRectF(lp.x() - label_w / 2, lp.y() - 9, label_w, 18)
        shape_path.addRect(text_rect)
        return shape_path

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        is_sel = self.isSelected()
        is_active = getattr(self, "_edge_active", True)  # default True until first style refresh

        if is_sel:
            color = QColor("#f39c12")   # amber — selected (always visible)
            line_w = 2.5
        elif is_active:
            color = QColor("#7289da")   # soft indigo — active/live edge
            line_w = 2
        else:
            color = QColor("#6b2d2d")   # muted dark-red — dead/skipped edge
            line_w = 1.5

        pen = QPen(color, line_w)
        if not is_active and not is_sel:
            pen.setStyle(Qt.PenStyle.DashLine)  # dashed to reinforce "dead" status
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(self._path)
        self._draw_arrowhead(painter, color)

        # Edge ID label (with repeat count suffix when > 1)
        lp = self._label_pos
        repeat = getattr(self.edge_data, "repeat_count", 1)
        label = f"#{self.edge_data.edge_id}" if repeat <= 1 else f"#{self.edge_data.edge_id} ×{repeat}"
        bg = QColor("#2c2f33") if is_active or is_sel else QColor("#1e1212")
        label_w = 28 if repeat <= 1 else 28 + 9 * len(str(repeat))
        text_rect = QRectF(lp.x() - label_w / 2, lp.y() - 9, label_w, 18)
        painter.fillRect(text_rect, bg)
        painter.setPen(QPen(color))
        painter.setFont(QFont("Arial", 8, QFont.Weight.Bold))
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, label)

    def _draw_arrowhead(self, painter: QPainter, color: QColor):
        tip = self._arrow_tip
        angle = self._arrow_angle
        arrow_len, half_spread = 10, 0.45
        p1 = QPointF(tip.x() - arrow_len * math.cos(angle - half_spread),
                     tip.y() - arrow_len * math.sin(angle - half_spread))
        p2 = QPointF(tip.x() - arrow_len * math.cos(angle + half_spread),
                     tip.y() - arrow_len * math.sin(angle + half_spread))
        painter.setBrush(QBrush(color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon(QPolygonF([tip, p1, p2]))

    def contextMenuEvent(self, event):
        sc = self.scene()
        if sc and hasattr(sc, "_edge_context_menu"):
            sc._edge_context_menu(self.edge_data.edge_id, event.screenPos())
        event.accept()
