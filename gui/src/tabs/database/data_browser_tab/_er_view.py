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

from typing import Dict, List

from PySide6.QtCore import QLineF, QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsPolygonItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QVBoxLayout,
    QWidget,
)

_CARD_WIDTH = 200
_ROW_HEIGHT = 18
_TITLE_HEIGHT = 26
_CARD_MARGIN_X = 60
_CARD_MARGIN_Y = 40
_BUCKET_ORDER = ("media", "image", "shared", "search", "other")
_BUCKET_LABELS = {
    "media": "Media / Entity domain",
    "image": "Image domain",
    "shared": "Shared vocabulary",
    "search": "Search infrastructure",
    "other": "Other",
}
_BUCKET_TABLES = {
    "media": {
        "media_items", "episodes", "entities", "credits",
        "media_entity", "entity_entity",
    },
    "image": {"groups", "subgroups", "images"},
    "shared": {"tags", "image_tags", "media_tags", "media_groups", "entity_images"},
    "search": {"embeddings", "vector_index", "media_fts", "entity_fts", "image_fts"},
}


def _bucket_for(table: str) -> str:
    for bucket, names in _BUCKET_TABLES.items():
        if table in names:
            return bucket
    return "other"


class _TableCardItem(QGraphicsRectItem):
    """One table's card: title bar + PK-starred/FK-annotated column rows.
    Clicking anywhere on the card notifies *on_click* with the table name."""

    def __init__(self, table_name: str, columns: List[Dict], fk_by_column: Dict[str, Dict], on_click):
        height = _TITLE_HEIGHT + max(1, len(columns)) * _ROW_HEIGHT + 8
        super().__init__(0, 0, _CARD_WIDTH, height)
        self.table_name = table_name
        self._on_click = on_click
        self.setBrush(QBrush(QColor("#2c2f33")))
        self.setPen(QPen(QColor("#4f545c"), 1))
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(f"Click to open {table_name!r} in the Grid view")

        title = QGraphicsSimpleTextItem(table_name, self)
        title_font = QFont()
        title_font.setBold(True)
        title.setFont(title_font)
        title.setBrush(QBrush(QColor("#ffffff")))
        title.setPos(6, 4)

        divider = QGraphicsLineItem(0, _TITLE_HEIGHT, _CARD_WIDTH, _TITLE_HEIGHT, self)
        divider.setPen(QPen(QColor("#4f545c"), 1))

        for i, col in enumerate(columns):
            name = col["name"]
            label = f"★ {name}" if col.get("pk") else name
            fk = fk_by_column.get(name)
            if fk:
                label = f"{label}  -> {fk['ref_table']}.{fk['ref_column']}"
            row = QGraphicsSimpleTextItem(label, self)
            row.setBrush(QBrush(QColor("#f2b900" if col.get("pk") else "#dcddde")))
            row.setPos(6, _TITLE_HEIGHT + i * _ROW_HEIGHT + 2)

    def anchor_point_toward(self, other_center: QPointF) -> QPointF:
        """Point on this card's border closest to *other_center* -- edges
        connect card edges, not arbitrary card interiors."""
        rect = self.sceneBoundingRect()
        center = rect.center()
        line = QLineF(center, other_center)
        for edge in (
            QLineF(rect.topLeft(), rect.topRight()),
            QLineF(rect.topRight(), rect.bottomRight()),
            QLineF(rect.bottomRight(), rect.bottomLeft()),
            QLineF(rect.bottomLeft(), rect.topLeft()),
        ):
            # PySide6's QLineF.intersects(other) takes one argument and
            # returns (IntersectionType, QPointF) -- not the PyQt5-style
            # out-parameter signature.
            intersection_type, point = line.intersects(edge)
            if intersection_type == QLineF.IntersectionType.BoundedIntersection:
                return point
        return center

    def mousePressEvent(self, event) -> None:
        super().mousePressEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
            self._on_click(self.table_name)


class ERGraphicsView(QGraphicsView):
    """Minimal pan/zoom view for the schema scene -- deliberately not a
    reuse of the wallpaper tab's node-editor graph view (see this
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


class _ERViewMixin:
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
        import math
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


__all__ = ["_ERViewMixin", "ERGraphicsView"]
