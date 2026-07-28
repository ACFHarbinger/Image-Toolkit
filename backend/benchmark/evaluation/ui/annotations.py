"""Cross-panel edge annotations + the annotation list/removal widget.

An Edge connects a point in one panel's image to a point in another (e.g.
"this seam in ASP corresponds to this clean region in ground truth") with a
short textual comparison. Two different panels each own their own
QGraphicsScene, so an edge line can't be a QGraphicsItem in either scene —
instead it's painted on a transparent overlay widget stacked on top of the
whole panel row; ``sync_geometry()`` must be called (by the container) any
time the row is resized so the overlay always exactly covers it.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QInputDialog, QListWidget, QPushButton, QVBoxLayout, QWidget

from ..other.schema import Edge, EdgePoint
from .panel_base import ImagePanel


class EdgeOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._panels: Dict[str, ImagePanel] = {}
        self._edges: List[Edge] = []

    def register_panel(self, key: str, panel: ImagePanel) -> None:
        self._panels[key] = panel

    def sync_geometry(self) -> None:
        if self.parentWidget() is not None:
            self.setGeometry(self.parentWidget().rect())

    def set_edges(self, edges: List[Edge]) -> None:
        self._edges = edges
        self.update()

    def _to_overlay_point(self, ep: EdgePoint) -> Optional[QPoint]:
        panel = self._panels.get(ep.image)
        if panel is None:
            return None
        view_pt = panel.scene_point_to_view(ep.x, ep.y)
        if view_pt is None:
            return None
        container = self.parentWidget()
        if container is None:
            return None
        return panel.mapTo(container, view_pt.toPoint())

    def paintEvent(self, event) -> None:  # noqa: D102 - Qt override
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor("#00e5ff"), 2, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setFont(QFont("Sans", 9))
        for edge in self._edges:
            pa, pb = self._to_overlay_point(edge.a), self._to_overlay_point(edge.b)
            if pa is None or pb is None:
                continue
            painter.drawLine(pa, pb)
            painter.drawEllipse(pa, 4, 4)
            painter.drawEllipse(pb, 4, 4)
            if edge.label:
                mid = QPoint((pa.x() + pb.x()) // 2, (pa.y() + pb.y()) // 2)
                painter.drawText(mid, edge.label)
        painter.end()


class EdgeBuilder:
    """Holds the first endpoint of an in-progress edge across two
    ``pointPicked`` signals from (possibly) two different panels."""

    def __init__(self):
        self._first: Optional[EdgePoint] = None

    def reset(self) -> None:
        self._first = None

    def add_point(self, image_key: str, x: float, y: float, prompt_parent) -> Optional[Edge]:
        if self._first is None:
            self._first = EdgePoint(image=image_key, x=x, y=y)
            return None
        second = EdgePoint(image=image_key, x=x, y=y)
        first = self._first
        self._first = None
        label, ok = QInputDialog.getText(
            prompt_parent, "Misalignment", "Describe the relationship between these two points:"
        )
        if not ok:
            return None
        return Edge(a=first, b=second, label=label)


class AnnotationListWidget(QWidget):
    """Read-only summary of the current test's bboxes/edges with per-row
    removal, so a mis-drawn annotation doesn't require restarting the test."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)
        remove_btn = QPushButton("Remove selected")
        remove_btn.clicked.connect(self._remove_selected)
        layout.addWidget(remove_btn)
        self._on_remove = None

    def set_remove_callback(self, callback) -> None:
        self._on_remove = callback

    def refresh(self, bboxes: List, edges: List) -> None:
        self.list_widget.clear()
        for i, b in enumerate(bboxes):
            self.list_widget.addItem(f"[bbox:{i}] {b.image} — {b.label or '(no description)'}")
        for i, e in enumerate(edges):
            self.list_widget.addItem(f"[edge:{i}] {e.a.image} <-> {e.b.image} — {e.label or '(no description)'}")

    def _remove_selected(self) -> None:
        item = self.list_widget.currentItem()
        if item is None or self._on_remove is None:
            return
        text = item.text()
        kind, rest = text[1:].split("]", 1)
        kind_name, idx = kind.split(":")
        self._on_remove(kind_name, int(idx))
