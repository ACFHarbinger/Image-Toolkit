"""Mesh overlay editor for ARAP rigging (roadmap §3.3, issue #194).

The remaining half of §3.3's scope after `src/rigging/arap.py` shipped
the deterministic algorithmic core: a rigging UI to actually drive it. This
widget lets a user load an image, paint a binary mask over the region to
puppeteer (reusing the same freehand-paint mechanism as
`MangaCanvasEditor`'s scribble layer, at a coarser default pen width since a
mask region is usually much larger than a colorization scribble), generate
an ARAP mesh over that mask (`generate_mesh()`), and then drag any mesh
vertex to pose it -- every mouse-move during a drag re-solves
`arap_deform()` from the ORIGINAL rest pose against the full accumulated set
of dragged/pinned vertices (not incrementally from the previous frame's
pose), exactly matching `arap_deform()`'s own contract and giving the
"real-time re-solve as vertices move" behavior issue #194 asks for.
The mouse handler uses a persistent isolated solver process: it pays spawn
cost once, retains serial low-latency updates, and protects the Qt host from a
native NumPy/SciPy failure. The worker is automatically replaced after failure.

New feature, not code motion.
"""

from __future__ import annotations

import atexit

import numpy as np
from execution import JobRequest, Operation, PersistentIsolatedRunner
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QGraphicsItem, QGraphicsPixmapItem, QGraphicsScene, QGraphicsView
from rigging.arap import generate_mesh

from .canvas_editor import qimage_alpha_to_mask

_ARAP_RUNNER = PersistentIsolatedRunner()
atexit.register(_ARAP_RUNNER.close)

_VERTEX_RADIUS = 4.0
_PICK_RADIUS = 10.0  # mouse-to-vertex hit tolerance, in scene (pixel) coords
_DRAG_ITERS = 6  # fewer than arap_deform's own default (10) -- trades a bit
# of pose accuracy for per-mouse-move responsiveness while dragging.


class _MeshOverlayItem(QGraphicsItem):
    """Draws the mesh (triangle edges + vertex dots, anchored vertices
    highlighted) directly from the parent editor's live vertex array on
    every `update()` -- one custom item redrawn in place rather than one
    QGraphicsItem per vertex/edge, since a mesh can have a few hundred of
    each and per-item overhead would add up for no benefit here."""

    def __init__(self, editor: MeshOverlayEditor):
        super().__init__()
        self._editor = editor

    def boundingRect(self) -> QRectF:  # noqa: D102
        w, h = self._editor._image_size
        return QRectF(0, 0, w, h)

    def paint(self, painter: QPainter, option, widget=None) -> None:  # noqa: D102
        editor = self._editor
        triangles = editor._triangles
        verts = editor._live_vertices
        if triangles is None or verts is None:
            return

        pen = QPen(QColor(80, 200, 255, 180))
        pen.setWidthF(1.0)
        painter.setPen(pen)
        for va, vb, vc in triangles:
            pa, pb, pc = verts[va], verts[vb], verts[vc]
            painter.drawLine(
                QPointF(float(pa[0]), float(pa[1])), QPointF(float(pb[0]), float(pb[1]))
            )
            painter.drawLine(
                QPointF(float(pb[0]), float(pb[1])), QPointF(float(pc[0]), float(pc[1]))
            )
            painter.drawLine(
                QPointF(float(pc[0]), float(pc[1])), QPointF(float(pa[0]), float(pa[1]))
            )

        painter.setPen(Qt.PenStyle.NoPen)
        for idx in range(verts.shape[0]):
            x, y = float(verts[idx, 0]), float(verts[idx, 1])
            color = QColor(255, 80, 80) if idx in editor._anchors else QColor(80, 200, 255)
            painter.setBrush(QBrush(color))
            painter.drawEllipse(QPointF(x, y), _VERTEX_RADIUS, _VERTEX_RADIUS)


class MeshOverlayEditor(QGraphicsView):
    """Load an image, paint a mask, generate an ARAP mesh, drag vertices to
    pose it in real time."""

    mesh_generated = Signal()
    pose_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)

        self._image_item = QGraphicsPixmapItem()
        self._mask_item = QGraphicsPixmapItem()
        self._mask_item.setOpacity(0.4)
        self._mesh_item = _MeshOverlayItem(self)
        for item in (self._image_item, self._mask_item, self._mesh_item):
            self._scene.addItem(item)

        self._image_qimage: QImage | None = None
        self._mask_qimage: QImage | None = None
        self._image_size: tuple[int, int] = (0, 0)

        self._pen_width = 24
        self._paint_mode = False  # True: paint the mask; False: drag vertices
        self._painting = False
        self._last_point: QPointF | None = None

        self._rest_vertices: np.ndarray | None = None
        self._triangles: np.ndarray | None = None
        self._live_vertices: np.ndarray | None = None
        self._anchors: dict[int, tuple[float, float]] = {}
        self._dragging_idx: int | None = None

    # ------------------------------------------------------------------
    # Loading / clearing
    # ------------------------------------------------------------------
    def set_image(self, image: QImage) -> None:
        """Load a new base image, resetting the mask and any existing mesh."""
        self._image_qimage = image
        w, h = image.width(), image.height()
        self._image_size = (w, h)

        self._image_item.setPixmap(QPixmap.fromImage(image))
        self._image_item.setPos(0, 0)

        self._mask_qimage = QImage(w, h, QImage.Format.Format_ARGB32)
        self._mask_qimage.fill(Qt.GlobalColor.transparent)
        self._mask_item.setPixmap(QPixmap.fromImage(self._mask_qimage))
        self._mask_item.setPos(0, 0)

        self._rest_vertices = None
        self._triangles = None
        self._live_vertices = None
        self._anchors = {}

        self._scene.setSceneRect(QRectF(0, 0, w, h))
        self.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        self._mesh_item.update()

    def has_image(self) -> bool:
        return self._image_qimage is not None and not self._image_qimage.isNull()

    def has_mask(self) -> bool:
        return self._mask_qimage is not None and bool(self.get_mask().any())

    def has_mesh(self) -> bool:
        return self._triangles is not None

    def set_paint_mode(self, enabled: bool) -> None:
        self._paint_mode = enabled

    def set_pen_width(self, width: int) -> None:
        self._pen_width = max(4, width)

    def clear_mask(self) -> None:
        if self._mask_qimage is None:
            return
        self._mask_qimage.fill(Qt.GlobalColor.transparent)
        self._mask_item.setPixmap(QPixmap.fromImage(self._mask_qimage))

    def get_mask(self) -> np.ndarray:
        if self._mask_qimage is None:
            raise RuntimeError("No image loaded")
        return qimage_alpha_to_mask(self._mask_qimage)

    # ------------------------------------------------------------------
    # Mesh generation / pose control
    # ------------------------------------------------------------------
    def generate_mesh(self, grid_step: int = 16) -> None:
        mask = self.get_mask()
        vertices, triangles = generate_mesh(mask, grid_step=grid_step)
        self._rest_vertices = vertices
        self._triangles = triangles
        self._live_vertices = vertices.copy()
        self._anchors = {}
        self._mesh_item.update()
        self.mesh_generated.emit()

    def reset_pose(self) -> None:
        if self._rest_vertices is None:
            return
        self._anchors = {}
        self._live_vertices = self._rest_vertices.copy()
        self._mesh_item.update()
        self.pose_changed.emit()

    def get_rest_vertices(self) -> np.ndarray | None:
        return self._rest_vertices

    def get_live_vertices(self) -> np.ndarray | None:
        return self._live_vertices

    def get_triangles(self) -> np.ndarray | None:
        return self._triangles

    def get_anchors(self) -> dict[int, tuple[float, float]]:
        return dict(self._anchors)

    # ------------------------------------------------------------------
    # Mouse handling
    # ------------------------------------------------------------------
    def mousePressEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton or not self.has_image():
            super().mousePressEvent(event)
            return

        point = self.mapToScene(event.pos())
        if self._paint_mode:
            self._painting = True
            self._last_point = point
            self._paint_dot(point)
            return

        if self._triangles is not None:
            idx = self._nearest_vertex(point)
            if idx is not None:
                self._dragging_idx = idx
                self._drag_vertex_to(idx, point)

    def mouseMoveEvent(self, event) -> None:
        point = self.mapToScene(event.pos())
        if self._paint_mode and self._painting and self._last_point is not None:
            self._paint_line(self._last_point, point)
            self._last_point = point
            return
        if self._dragging_idx is not None:
            self._drag_vertex_to(self._dragging_idx, point)
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._painting = False
            self._last_point = None
            self._dragging_idx = None
        else:
            super().mouseReleaseEvent(event)

    def _nearest_vertex(self, point: QPointF) -> int | None:
        if self._live_vertices is None or self._live_vertices.shape[0] == 0:
            return None
        px, py = point.x(), point.y()
        d = np.hypot(self._live_vertices[:, 0] - px, self._live_vertices[:, 1] - py)
        idx = int(np.argmin(d))
        return idx if d[idx] <= _PICK_RADIUS else None

    def _drag_vertex_to(self, idx: int, point: QPointF) -> None:
        w, h = self._image_size
        x = float(np.clip(point.x(), 0, max(w - 1, 0)))
        y = float(np.clip(point.y(), 0, max(h - 1, 0)))
        self._anchors[idx] = (x, y)
        # Always solved from the ORIGINAL rest pose against the full
        # accumulated anchor set -- arap_deform() has no incremental/
        # from-previous-pose mode, and mixing the two would double-count
        # deformation.
        self._live_vertices = _ARAP_RUNNER.run(
            JobRequest(
                Operation.ARAP_DEFORM,
                inputs={
                    "vertices": self._rest_vertices,
                    "triangles": self._triangles,
                    "anchors": self._anchors,
                },
                options={"n_iters": _DRAG_ITERS},
            )
        )
        self._mesh_item.update()
        self.pose_changed.emit()

    def _paint_dot(self, point: QPointF) -> None:
        self._paint_line(point, point)

    def _paint_line(self, p1: QPointF, p2: QPointF) -> None:
        if self._mask_qimage is None:
            return
        painter = QPainter(self._mask_qimage)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        white = QColor(255, 255, 255, 255)
        if p1 == p2:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(white)
            radius = self._pen_width / 2
            painter.drawEllipse(p1, radius, radius)
        else:
            pen = QPen(white, self._pen_width)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.drawLine(p1, p2)
        painter.end()
        self._mask_item.setPixmap(QPixmap.fromImage(self._mask_qimage))


__all__ = ["MeshOverlayEditor"]
