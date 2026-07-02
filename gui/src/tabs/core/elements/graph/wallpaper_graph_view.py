import os

from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QBrush, QColor, QPainter, QMouseEvent
from PySide6.QtWidgets import QGraphicsView, QGraphicsItem

from backend.src.constants import SUPPORTED_VIDEO_FORMATS, SUPPORTED_IMG_FORMATS
from .node_item import NODE_W
from .wallpaper_graph_scene import WallpaperGraphScene


class WallpaperGraphView(QGraphicsView):
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

    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)

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
