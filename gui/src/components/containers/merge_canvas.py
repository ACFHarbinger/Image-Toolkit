import os
from typing import Any, Dict, List, Optional

from gui.src.components.elements.merge_canvas_item import MergeCanvasItem
from PySide6.QtCore import QPointF, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QBrush, QColor, QImageReader, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView, QMenu


class MergeCanvas(QGraphicsView):
    """Interactive canvas where selected images are laid out for compositing."""

    item_selected = Signal(object)  # emits MergeCanvasItem or None on selection change

    def __init__(self, canvas_w: int = 1920, canvas_h: int = 1080):
        super().__init__()
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._canvas_w = canvas_w
        self._canvas_h = canvas_h

        self._bg = self._scene.addRect(
            0,
            0,
            canvas_w,
            canvas_h,
            QPen(QColor("#5865f2"), 2),
            QBrush(QColor("#2c2f33")),
        )
        self._bg.setZValue(-1)

        self.setSceneRect(-50, -50, canvas_w + 100, canvas_h + 100)
        self.setRenderHints(
            QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform
        )
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setStyleSheet(
            "QGraphicsView { border: 1px solid #4f545c; background-color: #1a1c1e; border-radius: 8px; }"
        )

        self._items: Dict[str, MergeCanvasItem] = {}
        self._scene.selectionChanged.connect(self._on_scene_selection_changed)
        self._is_panning = False
        self._pan_start_pos = None

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self._fit_canvas)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit_canvas()

    def _fit_canvas(self):
        self.fitInView(self._bg, Qt.AspectRatioMode.KeepAspectRatioByExpanding)

    # ── Public API ──────────────────────────────────────────────────────────────

    def add_image(self, path: str, thumbnail: QPixmap) -> MergeCanvasItem:
        if path in self._items:
            return self._items[path]

        reader = QImageReader(path)
        sz = reader.size()
        if sz.isValid() and sz.width() > 0:
            w, h = sz.width(), sz.height()
        elif thumbnail and not thumbnail.isNull():
            # rough estimate from thumbnail
            w, h = thumbnail.width() * 4, thumbnail.height() * 4
        else:
            w, h = 400, 300

        if w > self._canvas_w or h > self._canvas_h:
            scale = min(self._canvas_w / w, self._canvas_h / h)
            w, h = int(w * scale), int(h * scale)

        n = len(self._items)
        x_off = (n * 30) % max(1, self._canvas_w - w - 1)
        y_off = (n * 20) % max(1, self._canvas_h - h - 1)

        item = MergeCanvasItem(path, thumbnail, w, h)
        item.setPos(x_off, y_off)
        item.geometry_changed.connect(self._on_item_geometry_changed)
        self._scene.addItem(item)
        self._items[path] = item
        return item

    def remove_item(self, path: str):
        item = self._items.pop(path, None)
        if item:
            self._scene.removeItem(item)

    def remove_selected(self) -> List[str]:
        removed = []
        for item in list(self._scene.selectedItems()):
            if isinstance(item, MergeCanvasItem):
                self._items.pop(item.path, None)
                self._scene.removeItem(item)
                removed.append(item.path)
        return removed

    def clear_canvas(self) -> List[str]:
        paths = list(self._items.keys())
        for path in paths:
            item = self._items.pop(path)
            self._scene.removeItem(item)
        return paths

    def get_layout(self) -> List[Dict[str, Any]]:
        return [
            {
                "path": path,
                "x": int(item.x()),
                "y": int(item.y()),
                "w": item._w,
                "h": item._h,
            }
            for path, item in self._items.items()
        ]

    def resize_canvas(self, w: int, h: int):
        self._canvas_w = w
        self._canvas_h = h
        self._bg.setRect(0, 0, w, h)
        self.setSceneRect(-50, -50, w + 100, h + 100)
        self._fit_canvas()

    def get_selected_item(self) -> Optional[MergeCanvasItem]:
        sel = [i for i in self._scene.selectedItems() if isinstance(i, MergeCanvasItem)]
        return sel[0] if sel else None

    # ── Private ─────────────────────────────────────────────────────────────────

    def contextMenuEvent(self, event):
        scene_pos = self.mapToScene(event.pos())
        anchor = self._get_canvas_item_at(scene_pos)
        if anchor is None:
            super().contextMenuEvent(event)
            return

        others = [it for it in self._items.values() if it is not anchor]
        if not others:
            return

        menu = QMenu(self)
        menu.aboutToHide.connect(self._clear_highlights)

        for direction, label in (
            ("top", "Join Top"),
            ("bottom", "Join Bottom"),
            ("left", "Join Left"),
            ("right", "Join Right"),
        ):
            submenu = menu.addMenu(label)
            for target_item in others:
                name = os.path.basename(target_item.path)
                action = QAction(name, submenu)
                action.hovered.connect(lambda ti=target_item: self._highlight_item(ti))
                action.triggered.connect(
                    lambda checked=False,
                    a=anchor,
                    t=target_item,
                    d=direction: self._snap_items(t, a, d)
                )
                submenu.addAction(action)

        menu.exec(event.globalPos())
        self._clear_highlights()

    def _get_canvas_item_at(self, scene_pos: QPointF) -> Optional[MergeCanvasItem]:
        for item in self._scene.items(scene_pos):
            if isinstance(item, MergeCanvasItem):
                return item
        return None

    def _highlight_item(self, item: MergeCanvasItem):
        for it in self._items.values():
            it.set_highlighted(False)
        item.set_highlighted(True)

    def _clear_highlights(self):
        for it in self._items.values():
            it.set_highlighted(False)

    def _snap_items(
        self, anchor: MergeCanvasItem, target: MergeCanvasItem, direction: str
    ):
        """Move `target` to touch `anchor` on the given side with 0 px gap."""
        ax, ay, aw, ah = anchor.x(), anchor.y(), anchor._w, anchor._h
        tw, th = target._w, target._h

        if direction == "top":
            nx, ny = ax, ay - th
        elif direction == "bottom":
            nx, ny = ax, ay + ah
        elif direction == "left":
            nx, ny = ax - tw, ay
        else:  # "right"
            nx, ny = ax + aw, ay

        target.setPos(nx, ny)
        self._scene.clearSelection()
        target.setSelected(True)

    def _on_scene_selection_changed(self):
        self.item_selected.emit(self.get_selected_item())

    def _on_item_geometry_changed(self):
        item = self.get_selected_item()
        self.item_selected.emit(item)

    def mousePressEvent(self, event):
        from PySide6.QtGui import QMouseEvent
        from PySide6.QtWidgets import QGraphicsItem

        if event.button() == Qt.MouseButton.LeftButton:
            item = self.itemAt(event.position().toPoint())
            is_interactive = False
            curr = item
            while curr:
                if curr.__class__.__name__ in ("NodeItem", "EdgeItem", "MergeCanvasItem"):
                    is_interactive = True
                    break
                if (
                    (curr.flags() and (
                        QGraphicsItem.GraphicsItemFlag.ItemIsMovable | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable))
                    and not (hasattr(self, "_bg") and curr is self._bg)
                ):
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
        from PySide6.QtGui import QMouseEvent

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
        from PySide6.QtGui import QMouseEvent

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
