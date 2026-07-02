import os

from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QBrush, QColor, QPainter, QMouseEvent
from PySide6.QtWidgets import QGraphicsView, QGraphicsItem

from backend.src.constants import SUPPORTED_VIDEO_FORMATS, SUPPORTED_IMG_FORMATS
from .node_item import NODE_W
from .wallpaper_graph_scene import WallpaperGraphScene


class WallpaperGraphView(QGraphicsView):
    # How far beyond the panned-to viewport edge (and beyond actual node
    # content) the scene rect is grown, in scene px. Large enough that
    # panning doesn't immediately hit the new wall again.
    _CANVAS_GROW_MARGIN = 600
    # Generous starting canvas so panning/dropping nodes works comfortably
    # even before any growth has happened yet.
    _INITIAL_CANVAS_HALF_SIZE = 2000

    def __init__(self, scene: WallpaperGraphScene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setBackgroundBrush(QBrush(QColor("#23272a")))
        self.setMinimumSize(400, 300)
        self._is_panning = False
        self._pan_start_pos = None
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)

        h = self._INITIAL_CANVAS_HALF_SIZE
        scene.setSceneRect(-h, -h, 2 * h, 2 * h)

    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)
        self._grow_scene_rect_to_viewport()

    def _grow_scene_rect_to_viewport(self):
        """Expand the scene rect to comfortably cover whatever is currently
        visible (plus a margin) and whatever nodes actually exist.

        QGraphicsScene normally auto-shrinks its rect to the items' bounding
        box once one is explicitly set (which __init__ does, to get a
        comfortable starting canvas), so without this, panning toward empty
        space -- or a node dropped right at the current edge -- hits a hard
        wall with the node flush against the scroll boundary and no room to
        centre it.
        """
        scene = self.scene()
        if scene is None:
            return
        margin = self._CANVAS_GROW_MARGIN
        visible = self.mapToScene(self.viewport().rect()).boundingRect()
        visible = visible.adjusted(-margin, -margin, margin, margin)
        items_rect = scene.itemsBoundingRect().adjusted(-margin, -margin, margin, margin)
        current = scene.sceneRect()
        target = current.united(visible).united(items_rect)
        if target != current:
            scene.setSceneRect(target)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            sc = self.scene()
            if sc is None or not hasattr(sc, "_graph") or sc._graph is None:
                return
            scene_pos = self.mapToScene(event.position().toPoint())
            for url in event.mimeData().urls():
                path = url.toLocalFile()
                if not path:
                    continue
                ext = os.path.splitext(path)[1].lower()
                all_exts = set(SUPPORTED_VIDEO_FORMATS) | {
                    f".{e.lower().lstrip('.')}" for e in SUPPORTED_IMG_FORMATS
                }
                if ext in all_exts:
                    sc.add_node(path, scene_pos)
                    scene_pos = QPointF(scene_pos.x() + NODE_W + 20, scene_pos.y())
            self._grow_scene_rect_to_viewport()
            event.acceptProposedAction()
        else:
            super().dropEvent(event)

    def mousePressEvent(self, event):
        sc = self.scene()
        if sc and getattr(sc, "_connecting_source_node_id", None):
            scene_pos = self.mapToScene(event.position().toPoint())
            sc.handle_connection_press(scene_pos, event.button())
            event.accept()
            return

        if event.button() == Qt.MouseButton.LeftButton:
            item = self.itemAt(event.position().toPoint())
            is_interactive = False
            curr = item
            while curr:
                if curr.__class__.__name__ in ("NodeItem", "EdgeItem", "MergeCanvasItem"):
                    is_interactive = True
                    break
                if curr.flags() & (QGraphicsItem.GraphicsItemFlag.ItemIsMovable | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable):
                    if not (hasattr(self, "_bg") and curr is self._bg):
                        is_interactive = True
                        break
                curr = curr.parentItem()
            
            if is_interactive:
                super().mousePressEvent(event)
            else:
                self._pan_start_pos = event.position().toPoint()
                self._is_panning = True
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
                event.accept()
        elif event.button() == Qt.MouseButton.RightButton:
            self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
            fake_event = QMouseEvent(
                event.type(),
                event.position(),
                event.globalPosition(),
                Qt.MouseButton.LeftButton,
                event.buttons() | Qt.MouseButton.LeftButton,
                event.modifiers()
            )
            super().mousePressEvent(fake_event)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        sc = self.scene()
        if sc and getattr(sc, "_connecting_source_node_id", None):
            scene_pos = self.mapToScene(event.position().toPoint())
            sc.handle_connection_move(scene_pos)
            event.accept()
            return

        if getattr(self, "_is_panning", False):
            # Grow the scene rect *before* moving the scrollbars, so the
            # scrollbar range already covers the panned-to area instead of
            # clamping the move at the old edge.
            self._grow_scene_rect_to_viewport()
            delta = event.position().toPoint() - self._pan_start_pos
            self._pan_start_pos = event.position().toPoint()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
        elif event.buttons() & Qt.MouseButton.RightButton:
            fake_event = QMouseEvent(
                event.type(),
                event.position(),
                event.globalPosition(),
                Qt.MouseButton.LeftButton,
                (event.buttons() & ~Qt.MouseButton.RightButton) | Qt.MouseButton.LeftButton,
                event.modifiers()
            )
            super().mouseMoveEvent(fake_event)
            event.accept()
        else:
            super().mouseMoveEvent(event)

        # Also cover dragging a node (or the right-click rubber-band path)
        # out toward the current edge -- not just background panning.
        if event.buttons():
            self._grow_scene_rect_to_viewport()

    def mouseReleaseEvent(self, event):
        sc = self.scene()
        if sc and getattr(sc, "_connecting_source_node_id", None):
            event.accept()
            return

        if getattr(self, "_is_panning", False):
            self._is_panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
        elif event.button() == Qt.MouseButton.RightButton:
            fake_event = QMouseEvent(
                event.type(),
                event.position(),
                event.globalPosition(),
                Qt.MouseButton.LeftButton,
                event.buttons() & ~Qt.MouseButton.LeftButton,
                event.modifiers()
            )
            super().mouseReleaseEvent(fake_event)
            event.accept()
        else:
            super().mouseReleaseEvent(event)
