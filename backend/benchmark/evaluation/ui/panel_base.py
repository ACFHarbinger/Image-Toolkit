"""ImagePanel: a QGraphicsView-based zoom/pan display for one stitched test
image (ASP output / Simple stitch / ground truth).

Follows this repo's existing QGraphicsView/QGraphicsScene zoom idiom
(``gui/src/tabs/core/extractor_tab.py``'s ``self.video_view``/
``self.graphics_scene``) as architectural inspiration since that is this
codebase's own established pattern for zoomable image display — this is a
standalone dev tool though, so the widget is written fresh rather than
importing that tab.

This is the single shared base every one of the three test panels uses, so
zoom/pan, display-mode switching, and interactive bbox/point annotation
logic exist exactly once (DRY) instead of once per panel instance.
"""

from __future__ import annotations

from typing import Iterable, Optional

import cv2
import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QImage, QMouseEvent, QPainter, QPen, QPixmap, QWheelEvent
from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsRectItem, QGraphicsScene, QGraphicsView, QInputDialog

from ..other.schema import BoundingBox
from ..constants.user_interface import (
    MODE_NAVIGATE,
    MODE_BBOX,
    MODE_POINT,
    DISPLAY_RAW,
    DISPLAY_PIXEL,
    ZOOM_MIN,
    ZOOM_MAX,
    PIXEL_GRID_ZOOM_THRESHOLD,
)


def bgr_to_qimage(img: np.ndarray) -> QImage:
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    h, w, _ = rgb.shape
    return QImage(rgb.data, w, h, rgb.strides[0], QImage.Format.Format_RGB888).copy()


class ImagePanel(QGraphicsView):
    zoomChanged = Signal(float)
    bboxDrawn = Signal(object)  # dict: x,y,w,h normalized + label (image key added by caller)
    pointPicked = Signal(float, float)  # normalized x, y within this panel's image
    pixelHovered = Signal(int, int, object)  # pixel x, y, BGR tuple (or None off-image)

    def __init__(self, key: str, title: str, parent=None):
        super().__init__(parent)
        self.key = key
        self.title = title
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setMouseTracking(True)
        self.setMinimumSize(280, 220)

        self._pixmap_item: Optional[QGraphicsPixmapItem] = None
        self._image_bgr: Optional[np.ndarray] = None
        self._zoom = 1.0
        self._mode = MODE_NAVIGATE
        self._display_mode = DISPLAY_RAW
        self._rubber_origin: Optional[QPointF] = None
        self._rubber_item: Optional[QGraphicsRectItem] = None
        self._overlay_items: list = []
        self._suppress_zoom_signal = False

    # -- image loading -----------------------------------------------------

    def set_image(self, img: Optional[np.ndarray]) -> None:
        self._image_bgr = img
        self._scene.clear()
        self._pixmap_item = None
        self._overlay_items = []
        if img is None:
            return
        pix = QPixmap.fromImage(bgr_to_qimage(img))
        self._pixmap_item = self._scene.addPixmap(pix)
        self._scene.setSceneRect(QRectF(pix.rect()))
        self.fit_to_view()

    def image_size(self) -> Optional[tuple]:
        if self._pixmap_item is None:
            return None
        pm = self._pixmap_item.pixmap()
        return pm.width(), pm.height()

    def fit_to_view(self) -> None:
        if self._pixmap_item is None:
            return
        self.resetTransform()
        self.fitInView(self._pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)
        self._zoom = 1.0

    # -- modes ---------------------------------------------------------------

    def set_mode(self, mode: str) -> None:
        self._mode = mode
        navigating = mode == MODE_NAVIGATE
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag if navigating else QGraphicsView.DragMode.NoDrag)

    def set_display_mode(self, mode: str) -> None:
        self._display_mode = mode
        self.viewport().update()

    # -- zoom (independent or externally-synced) -----------------------------

    def set_zoom(self, factor: float, emit: bool = True) -> None:
        if self._pixmap_item is None:
            return
        factor = max(ZOOM_MIN, min(ZOOM_MAX, factor))
        self.resetTransform()
        self.scale(factor, factor)
        self._zoom = factor
        if emit and not self._suppress_zoom_signal:
            self.zoomChanged.emit(factor)

    def apply_external_zoom(self, factor: float) -> None:
        """Called by the dashboard when synchronized-zoom mode is on, so this
        panel's own change doesn't re-broadcast and loop."""
        self._suppress_zoom_signal = True
        self.set_zoom(factor, emit=False)
        self._suppress_zoom_signal = False

    def wheelEvent(self, event: QWheelEvent) -> None:
        if self._pixmap_item is None:
            return
        step = 1.15 if event.angleDelta().y() > 0 else (1.0 / 1.15)
        self.set_zoom(self._zoom * step)

    # -- annotation drawing ---------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self._mode == MODE_BBOX and event.button() == Qt.MouseButton.LeftButton and self._pixmap_item:
            self._rubber_origin = self.mapToScene(event.pos())
            self._rubber_item = QGraphicsRectItem(QRectF(self._rubber_origin, self._rubber_origin))
            self._rubber_item.setPen(QPen(QColor("#ff6b6b"), 2))
            self._rubber_item.setBrush(QBrush(QColor(255, 107, 107, 40)))
            self._scene.addItem(self._rubber_item)
            return
        if self._mode == MODE_POINT and event.button() == Qt.MouseButton.LeftButton and self._pixmap_item:
            self._finish_point(self.mapToScene(event.pos()))
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._mode == MODE_BBOX and self._rubber_item is not None and self._rubber_origin is not None:
            self._rubber_item.setRect(QRectF(self._rubber_origin, self.mapToScene(event.pos())).normalized())
        else:
            self._emit_pixel_hover(event.pos())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._mode == MODE_BBOX and self._rubber_item is not None:
            rect = self._rubber_item.rect()
            self._scene.removeItem(self._rubber_item)
            self._rubber_item = None
            self._rubber_origin = None
            if rect.width() > 3 and rect.height() > 3:
                self._finish_bbox(rect)
            return
        super().mouseReleaseEvent(event)

    def _finish_bbox(self, rect: QRectF) -> None:
        label, ok = QInputDialog.getText(
            self, "Failure mode", f"Describe the defect in this {self.title} region:"
        )
        if not ok:
            return
        w, h = self.image_size()
        self._add_bbox_item(rect, QColor("#ffd93d"))
        self.bboxDrawn.emit({
            "x": rect.x() / w, "y": rect.y() / h, "w": rect.width() / w, "h": rect.height() / h,
            "label": label,
        })

    def _finish_point(self, pt: QPointF) -> None:
        w, h = self.image_size()
        if not (0 <= pt.x() <= w and 0 <= pt.y() <= h):
            return
        marker = QGraphicsRectItem(pt.x() - 3, pt.y() - 3, 6, 6)
        marker.setPen(QPen(QColor("#6bffb8"), 2))
        self._scene.addItem(marker)
        self._overlay_items.append(marker)
        self.pointPicked.emit(pt.x() / w, pt.y() / h)

    def _add_bbox_item(self, rect: QRectF, color: QColor) -> None:
        item = QGraphicsRectItem(rect)
        item.setPen(QPen(color, 2))
        self._scene.addItem(item)
        self._overlay_items.append(item)

    def restore_bboxes(self, bboxes: Iterable[BoundingBox]) -> None:
        w, h = self.image_size() or (0, 0)
        if not w or not h:
            return
        for b in bboxes:
            if b.image != self.key:
                continue
            self._add_bbox_item(QRectF(b.x * w, b.y * h, b.w * w, b.h * h), QColor("#ffd93d"))

    def scene_point_to_view(self, x_norm: float, y_norm: float) -> Optional[QPointF]:
        size = self.image_size()
        if size is None:
            return None
        w, h = size
        return self.mapFromScene(QPointF(x_norm * w, y_norm * h))

    # -- pixel value mode ------------------------------------------------------

    def _emit_pixel_hover(self, view_pos) -> None:
        if self._image_bgr is None:
            return
        scene_pt = self.mapToScene(view_pos)
        x, y = int(scene_pt.x()), int(scene_pt.y())
        h, w = self._image_bgr.shape[:2]
        if 0 <= x < w and 0 <= y < h:
            self.pixelHovered.emit(x, y, tuple(int(v) for v in self._image_bgr[y, x]))
        else:
            self.pixelHovered.emit(-1, -1, None)

    def pixel_region(self, x_norm: float, y_norm: float, w_norm: float, h_norm: float) -> Optional[np.ndarray]:
        """BGR crop for a normalized bbox — feeds Pixel Value Mode's numeric
        dump and every comparison/visualization tool's "selected region" input."""
        if self._image_bgr is None:
            return None
        h, w = self._image_bgr.shape[:2]
        x0, y0 = int(x_norm * w), int(y_norm * h)
        x1, y1 = int((x_norm + w_norm) * w), int((y_norm + h_norm) * h)
        x0, y0 = max(0, x0), max(0, y0)
        x1, y1 = min(w, x1), min(h, y1)
        if x1 <= x0 or y1 <= y0:
            return None
        return self._image_bgr[y0:y1, x0:x1].copy()

    def current_image(self) -> Optional[np.ndarray]:
        return self._image_bgr
