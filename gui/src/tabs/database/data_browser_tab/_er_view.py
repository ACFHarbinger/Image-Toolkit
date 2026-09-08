"""Schema/ER view for ``DataBrowserTab`` -- DB.9.

Renders every table as a titled column-list card (PK starred, FK
annotated) with relationship lines between them, in a pannable/zoomable
``QGraphicsView``.

Simplifications vs. the roadmap's original text (documented here rather
than silently dropped):
  - The wallpaper tab's existing graph-view infrastructure
    (``elements/graph/wallpaper_graph_view.py``/``wallpaper_graph_scene.py``)
    turned out to be tightly coupled to its node-drag/connection-editing
    workflow (media-file drag-drop, node "connecting" mode, NodeItem/
    EdgeItem classes with wallpaper-specific behavior) -- not a clean fit
    to import and reuse for a read-only schema diagram. This view is a
    small, self-contained ``QGraphicsView``/``QGraphicsScene`` instead,
    reusing only the wheel-zoom idiom.
  - Relationship lines are plain lines with a simple arrowhead at the
    "one" (referenced) end, not full crow's-foot fork glyphs -- an
    accurate crow's-foot glyph was judged not worth the round's remaining
    budget versus a clearly-legible, correctly-directional simplification.
  - Layout is a simple domain-clustered grid (tables grouped into
    media/image/shared-vocab/search buckets by name, buckets arranged
    left-to-right, cards stacked top-to-bottom within a bucket) rather
    than a real force-directed layout -- deterministic and never drifts,
    per the roadmap's own stated goal for the underlying PRAGMA-driven
    metadata, even though it isn't a general graph-layout algorithm.
"""

from __future__ import annotations

import math
from typing import Dict, List

from PySide6.QtCore import QLineF, QPointF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (
    QGraphicsLineItem,
    QGraphicsPolygonItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QVBoxLayout,
    QWidget,
)

from gui.src.constants.elements import (
    _BUCKET_ORDER,
    _BUCKET_TABLES,
    _CARD_MARGIN_X,
    _CARD_MARGIN_Y,
    _CARD_WIDTH,
    _ROW_HEIGHT,
    _TITLE_HEIGHT,
)

from ._tab_bound import TabBoundController


def _bucket_for(table: str) -> str:
    for bucket, names in _BUCKET_TABLES.items():
        if table in names:
            return bucket
    return "media"


class _TableCardItem(QGraphicsRectItem):
    """Visual card for a single table in the schema view: header with table
    name, followed by rows for each column. PK columns have a star; FK
    columns show the target table. Clicking the card navigates the grid
    to that table."""

    def __init__(self, table_name: str, columns: List[Dict], fk_by_column: Dict[str, Dict], on_click):
        height = _TITLE_HEIGHT + max(1, len(columns)) * _ROW_HEIGHT
        super().__init__(0, 0, _CARD_WIDTH, height)
        self.table_name = table_name
        self.on_click = on_click
        self.setBrush(QBrush(QColor("#2f3136")))
        self.setPen(QPen(QColor("#7289da"), 1.5))
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        # Title bar
        title_rect = QGraphicsRectItem(0, 0, _CARD_WIDTH, _TITLE_HEIGHT, parent=self)
        title_rect.setBrush(QBrush(QColor("#202225")))
        title_rect.setPen(QPen(Qt.PenStyle.NoPen))
        title_text = QGraphicsSimpleTextItem(table_name, parent=self)
        font = QFont()
        font.setBold(True)
        title_text.setFont(font)
        title_text.setBrush(QBrush(QColor("#ffffff")))
        title_text.setPos(8, 4)

        # Columns
        y = _TITLE_HEIGHT
        for col in columns:
            name = col["name"]
            prefix = "★ " if col["pk"] else "  "
            suffix = ""
            if name in fk_by_column:
                suffix = f" → {fk_by_column[name]['ref_table']}"
            label = f"{prefix}{name}{suffix}"
            item = QGraphicsSimpleTextItem(label, parent=self)
            item.setBrush(QBrush(QColor("#e0e0e0") if col["pk"] else QColor("#b9bbbe")))
            item.setPos(8, y + 2)
            y += _ROW_HEIGHT

    def anchor_point_toward(self, other_center: QPointF) -> QPointF:
        """Find the edge intersection point on this card that faces
        *other_center*, so relationship lines anchor to the card perimeter
        instead of pointing into its center."""
        card_center = self.sceneBoundingRect().center()
        rect = self.sceneBoundingRect()
        dx = other_center.x() - card_center.x()
        dy = other_center.y() - card_center.y()
        if abs(dx) > abs(dy):
            # Exits left or right
            x = rect.right() if dx > 0 else rect.left()
            # Intercept on the vertical edge
            y = card_center.y() + (dy / (dx if dx != 0 else 1.0)) * (x - card_center.x())
            y = max(rect.top(), min(rect.bottom(), y))
            return QPointF(x, y)
        # Exits top or bottom
        y = rect.bottom() if dy > 0 else rect.top()
        x = card_center.x() + (dx / (dy if dy != 0 else 1.0)) * (y - card_center.y())
        x = max(rect.left(), min(rect.right(), x))
        return QPointF(x, y)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.on_click:
            self.on_click(self.table_name)
        super().mousePressEvent(event)


class ERGraphicsView(QGraphicsView):
    """Pannable/zoomable view over the schema scene (see the containing
    module's docstring)."""

    def __init__(self, scene: QGraphicsScene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setBackgroundBrush(QBrush(QColor("#23272a")))
        self.setMinimumSize(400, 300)

    def wheelEvent(self, event) -> None:
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)


class DataBrowserERViewController(TabBoundController):
    """Builds and populates the Schema (ER) sub-view."""

    def _build_er_view(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)

        self.er_scene = QGraphicsScene()
        self.er_view = ERGraphicsView(self.er_scene)
        layout.addWidget(self.er_view)
        return container

    def _refresh_er_view(self) -> None:
        if not self.browser_repo:
            return
        try:
            tables = self.browser_repo.list_tables()
        except Exception:
            return

        self.er_scene.clear()
        cards: Dict[str, _TableCardItem] = {}
        fks_by_table: Dict[str, List[Dict]] = {}

        buckets: Dict[str, List[str]] = {b: [] for b in _BUCKET_ORDER}
        for table in tables:
            buckets[_bucket_for(table)].append(table)

        x = 0.0
        for bucket in _BUCKET_ORDER:
            names = buckets[bucket]
            if not names:
                continue
            y = 0.0
            for table in names:
                try:
                    columns = self.browser_repo.table_columns(table)
                    fks = self.browser_repo.table_foreign_keys(table)
                except Exception:
                    continue
                fks_by_table[table] = fks
                fk_by_column = {fk["column"]: fk for fk in fks}
                card = _TableCardItem(table, columns, fk_by_column, self._on_er_table_clicked)
                card.setPos(x, y)
                self.er_scene.addItem(card)
                cards[table] = card
                y += card.rect().height() + _CARD_MARGIN_Y
            x += _CARD_WIDTH + _CARD_MARGIN_X

        # Relationship lines, drawn after every card exists so both
        # endpoints can be anchored to real card geometry.
        for table, fks in fks_by_table.items():
            src_card = cards.get(table)
            if src_card is None:
                continue
            for fk in fks:
                dst_card = cards.get(fk["ref_table"])
                if dst_card is None:
                    continue
                self._draw_relationship(src_card, dst_card)

        self.er_scene.setSceneRect(self.er_scene.itemsBoundingRect().adjusted(-40, -40, 40, 40))

    def _draw_relationship(self, src_card: _TableCardItem, dst_card: _TableCardItem) -> None:
        dst_center = dst_card.sceneBoundingRect().center()
        src_center = src_card.sceneBoundingRect().center()
        start = src_card.anchor_point_toward(dst_center)
        end = dst_card.anchor_point_toward(src_center)

        line = QGraphicsLineItem(QLineF(start, end))
        line.setPen(QPen(QColor("#7289da"), 1.5))
        line.setZValue(-1)
        self.er_scene.addItem(line)

        # Simple arrowhead at the referenced ("one") end -- a documented
        # simplification of a full crow's-foot glyph, see module docstring.
        direction = QLineF(start, end)
        angle = direction.angle()
        arrow_size = 8.0
        a1 = end - QPointF(
            math.cos(math.radians(angle - 150)) * arrow_size,
            -math.sin(math.radians(angle - 150)) * arrow_size,
        )
        a2 = end - QPointF(
            math.cos(math.radians(angle + 150)) * arrow_size,
            -math.sin(math.radians(angle + 150)) * arrow_size,
        )
        arrow_head = QGraphicsPolygonItem(QPolygonF([end, a1, a2]))
        arrow_head.setBrush(QBrush(QColor("#7289da")))
        arrow_head.setPen(QPen(Qt.PenStyle.NoPen))
        arrow_head.setZValue(-1)
        self.er_scene.addItem(arrow_head)

    def _on_er_table_clicked(self, table_name: str) -> None:
        self.view_tabs.setCurrentIndex(0)  # switch to the Grid sub-tab
        self.table_combo.setCurrentText(table_name)


_ERViewMixin = DataBrowserERViewController  # COMPAT(ui-arch-23): remove after callers drop the mixin name

__all__ = ["DataBrowserERViewController", "_ERViewMixin", "ERGraphicsView"]
