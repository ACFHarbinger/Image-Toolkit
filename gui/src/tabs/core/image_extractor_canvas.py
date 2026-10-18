"""Deep-zoom frame-boundary canvas for the Extractor tab's Image sub-tab.

Moved out of ``image_extractor_subtab.py`` unchanged (the sub-tab module
re-exports it).
"""

from typing import Any, List, Optional

from PySide6.QtCore import QRect, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsScene, QGraphicsView, QWidget

from gui.src.constants.elements import _MAX_SCALE, _MIN_SCALE

from ...theming.theme_api import color, qss

# Absolute zoom bounds for the canvas. 0.01x shows a ~40k-pixel-tall strip
# whole; 80x makes a single source pixel ~80 screen pixels wide, which is
# far past what is needed to eyeball a boundary to +/-1 px.


class FrameSliceCanvas(QGraphicsView):
    """Deep-zoom image canvas with a frame-boundary overlay.

    - Mouse wheel zooms (anchored under the cursor) across the full
      0.01x-80x range so the user can flip between whole-sheet overview
      and single-pixel detail quickly.
    - Left-drag pans (ScrollHandDrag).
    - Double-click toggles between fit-to-view and 1:1 pixels at the
      clicked point, which is the fastest "overview <-> pixel detail"
      round trip when checking one boundary after another.
    - At scale >= 1 smoothing is disabled so source pixels render as hard
      squares (pixel-accurate boundary verification); below 1 smoothing is
      enabled so the overview stays readable.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._pixmap_item: Optional[QGraphicsPixmapItem] = None
        self._overlay_items: List[Any] = []

        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setBackgroundBrush(QColor(color("window_bg")))
        self.setStyleSheet(qss("extractor_scene_border"))
        self.setMinimumHeight(420)

    # --- Image / overlay management ---

    def set_image(self, image: QImage) -> None:
        self._scene.clear()
        self._overlay_items = []
        self._pixmap_item = self._scene.addPixmap(QPixmap.fromImage(image))
        self._scene.setSceneRect(QRectF(image.rect()))
        self.fit_image()

    def clear_image(self) -> None:
        self._scene.clear()
        self._overlay_items = []
        self._pixmap_item = None

    def set_frame_rects(self, rects: List[QRect], leftover: List[QRect]) -> None:
        """Redraws the cut-boundary overlay.

        `rects` are the frames that will be extracted (solid alternating
        cyan/magenta cosmetic outlines — alternating colors make shared
        edges between adjacent frames readable at any zoom); `leftover`
        marks image regions the current parameters leave uncut (dashed
        amber), so an off-by-a-few-pixels frame size is visible at the
        overview zoom before the user even zooms in.
        """
        for item in self._overlay_items:
            self._scene.removeItem(item)
        self._overlay_items = []
        if self._pixmap_item is None:
            return

        colors = (QColor(color("accent")), QColor(color("accent_hover")))
        for i, rect in enumerate(rects):
            pen = QPen(colors[i % 2])
            pen.setCosmetic(True)  # stays 1 device px wide at any zoom
            item = self._scene.addRect(QRectF(rect), pen)
            self._overlay_items.append(item)

        leftover_pen = QPen(QColor(color("accent_hover")))
        leftover_pen.setCosmetic(True)
        leftover_pen.setStyle(Qt.PenStyle.DashLine)
        for rect in leftover:
            item = self._scene.addRect(QRectF(rect), leftover_pen)
            self._overlay_items.append(item)

    # --- Zoom helpers ---

    def current_scale(self) -> float:
        return self.transform().m11()

    def fit_image(self) -> None:
        if self._pixmap_item is None:
            return
        self.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        self._apply_render_hints()

    def zoom_1to1(self) -> None:
        self._set_absolute_scale(1.0)

    def zoom_in(self) -> None:
        self._zoom_by(1.6)

    def zoom_out(self) -> None:
        self._zoom_by(1 / 1.6)

    def _set_absolute_scale(self, scale: float) -> None:
        scale = max(_MIN_SCALE, min(_MAX_SCALE, scale))
        current = self.current_scale()
        if current > 0:
            self.scale(scale / current, scale / current)
        self._apply_render_hints()

    def _zoom_by(self, factor: float) -> None:
        target = self.current_scale() * factor
        if target < _MIN_SCALE:
            factor = _MIN_SCALE / self.current_scale()
        elif target > _MAX_SCALE:
            factor = _MAX_SCALE / self.current_scale()
        self.scale(factor, factor)
        self._apply_render_hints()

    def _apply_render_hints(self) -> None:
        smooth = self.current_scale() < 1.0
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, smooth)

    def wheelEvent(self, event):
        if self._pixmap_item is None:
            return
        # Faster per-notch factor than typical viewers: the whole point of
        # this canvas is covering a huge zoom range in few wheel ticks.
        factor = 1.3 if event.angleDelta().y() > 0 else 1 / 1.3
        self._zoom_by(factor)
        event.accept()

    def mouseDoubleClickEvent(self, event):
        if self._pixmap_item is None:
            return
        if self.current_scale() < 1.0:
            scene_pos = self.mapToScene(event.position().toPoint())
            self.zoom_1to1()
            self.centerOn(scene_pos)
        else:
            self.fit_image()
        event.accept()
