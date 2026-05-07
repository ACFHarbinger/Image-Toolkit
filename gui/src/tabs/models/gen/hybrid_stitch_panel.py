"""
hybrid_stitch_panel.py
======================
Human-in-the-loop cooperative panorama stitching.

The panel provides a fully manual + assisted pipeline.  Automation is
available at every stage but the human is always in control.

Pipeline stages
---------------
1.  Sequence Manager   – ordered frame list with thumbnails; drag/drop,
                         add/remove.
2.  Control-Point Editor – dual-image canvas; click to place numbered
                         correspondences; solve exact homography via DLT
                         (no RANSAC) or blend manual + auto matches.
                         Auto-suggest proposes the nearest ORB match.
3.  Color Correction   – per-frame brightness / contrast / gamma /
                         saturation / white-balance with live 512-px
                         preview; "Match Adjacent" histogram-matches to
                         neighbour.
4.  Seam Painter       – after computing the warp, paint hard constraints
                         (Force-A / Force-B / Neutral); route final seam
                         via minimum-cost DP path on pixel-difference
                         energy that honours the painted constraints.
5.  Mesh Warp          – deformable grid overlaid on one image; drag
                         intersections as pins; displacements interpolated
                         via thin-plate spline and applied as dense remap.
6.  Render             – compose the approved sequence into a final
                         panorama using the accepted per-pair warps and
                         chosen blending mode.
"""

from __future__ import annotations

import math
import os
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

from PySide6.QtCore import (
    QObject,
    QPointF,
    QRectF,
    QRunnable,
    QSize,
    QSizeF,
    Qt,
    QThreadPool,
    QTimer,
    Signal,
    Slot,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QCursor,
    QFont,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsPathItem,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsTextItem,
    QGraphicsView,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QSizePolicy,
    QFrame,
)

from ....styles.style import apply_shadow_effect

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_THUMB_W = 96  # px  – thumbnail width in frame list
_THUMB_H = 54  # px  – thumbnail height in frame list
_CP_COLORS = [  # per-index colours for control points
    QColor("#F44336"),
    QColor("#2196F3"),
    QColor("#4CAF50"),
    QColor("#FF9800"),
    QColor("#9C27B0"),
    QColor("#00BCD4"),
    QColor("#FFEB3B"),
    QColor("#795548"),
    QColor("#607D8B"),
    QColor("#E91E63"),
]
_DARK_PANEL = "background:#2c2f33;"
_DARK_GROUP = "QGroupBox { background:#2c2f33; color:#ccc; }"
_DARK_TABLE = (
    "QTableWidget { background:#2c2f33; "
    "alternate-background-color:#36393f; } "
    "QHeaderView::section { background:#1e1f22; color:#ccc; padding:4px; }"
)


# ---------------------------------------------------------------------------
# Utility: bgr→QPixmap (cached at fixed size)
# ---------------------------------------------------------------------------


def _load_thumb(path: str, w: int = _THUMB_W, h: int = _THUMB_H) -> QPixmap:
    bgr = cv2.imread(path)
    if bgr is None:
        pm = QPixmap(w, h)
        pm.fill(QColor("#333"))
        return pm
    ih, iw = bgr.shape[:2]
    scale = min(w / iw, h / ih)
    nw, nh = max(1, int(iw * scale)), max(1, int(ih * scale))
    bgr = cv2.resize(bgr, (nw, nh), interpolation=cv2.INTER_AREA)
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    qi = QImage(rgb.data, nw, nh, nw * 3, QImage.Format.Format_RGB888).copy()
    return QPixmap.fromImage(qi)


def _bgr_to_qimage(bgr: np.ndarray) -> QImage:
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    h, w = rgb.shape[:2]
    return QImage(rgb.data, w, h, w * 3, QImage.Format.Format_RGB888).copy()


def _apply_color_correction(bgr: np.ndarray, cc: dict) -> np.ndarray:
    """Apply per-frame color correction dict to a BGR uint8 image."""
    if not cc:
        return bgr
    img = bgr.astype(np.float32)
    # Brightness [-100 .. +100]
    img += float(cc.get("brightness", 0))
    # Contrast  [0.1 .. 3.0, 1.0 = no change]
    img = (img - 127.5) * float(cc.get("contrast", 1.0)) + 127.5
    # Saturation [0.0 .. 3.0, 1.0 = no change]
    sat = float(cc.get("saturation", 1.0))
    if sat != 1.0:
        gray = img.mean(axis=2, keepdims=True)
        img = gray + sat * (img - gray)
    # Gamma [0.2 .. 5.0, 1.0 = no change]
    gamma = float(cc.get("gamma", 1.0))
    if gamma != 1.0:
        img = np.sign(img) * (np.abs(img / 255.0) ** (1.0 / gamma)) * 255.0
    # White balance — temperature offset in blue/red channels [-50 .. +50]
    temp = float(cc.get("temperature", 0))
    img[:, :, 0] -= temp  # blue
    img[:, :, 2] += temp  # red
    return np.clip(img, 0, 255).astype(np.uint8)


# ---------------------------------------------------------------------------
# Async thumbnail loader
# ---------------------------------------------------------------------------


class _ThumbSignals(QObject):
    done = Signal(str, QPixmap)  # path, pixmap


class _ThumbLoader(QRunnable):
    def __init__(self, path: str):
        super().__init__()
        self.setAutoDelete(True)
        self._path = path
        self.signals = _ThumbSignals()

    def run(self):
        pm = _load_thumb(self._path)
        self.signals.done.emit(self._path, pm)


# ---------------------------------------------------------------------------
# Section 3 — Control-Point Infrastructure
# ---------------------------------------------------------------------------


class _CPDot(QGraphicsEllipseItem):
    """A draggable numbered control-point dot."""

    R = 8  # radius in scene pixels

    def __init__(self, canvas: "_CPCanvas", idx: int):
        super().__init__(-self.R, -self.R, 2 * self.R, 2 * self.R)
        self._canvas = canvas
        self._idx = idx
        color = _CP_COLORS[idx % len(_CP_COLORS)]
        self.setBrush(QBrush(color))
        self.setPen(QPen(QColor("white"), 1.5))
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setZValue(20)

    # -- position change hook --
    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self._canvas._on_dot_moved(self._idx)
        return super().itemChange(change, value)

    def paint(self, painter, option, widget=None):
        super().paint(painter, option, widget)
        painter.setPen(QPen(QColor("white")))
        painter.setFont(QFont("Arial", max(6, int(self.R * 0.85)), QFont.Weight.Bold))
        painter.drawText(
            QRectF(-self.R, -self.R, 2 * self.R, 2 * self.R),
            Qt.AlignmentFlag.AlignCenter,
            str(self._idx + 1),
        )

    def contextMenuEvent(self, event):
        self._canvas.remove_point(self._idx)


class _CPCanvas(QGraphicsView):
    """
    Single-image canvas for placing control points.

    Left-click  : add a point (in "add" mode)
    Left-drag   : move an existing point
    Right-click : remove nearest point
    """

    point_added = Signal(int, float, float)  # idx, x_img, y_img
    point_moved = Signal(int, float, float)
    point_removed = Signal(int)

    def __init__(self, label: str = "", parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._label_str = label
        self._pix_item: Optional[QGraphicsPixmapItem] = None
        self._dots: List[_CPDot] = []
        self._img_w = 1
        self._img_h = 1
        self._mode = "add"  # "add" | "view"
        self._current_path: str = ""

        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setBackgroundBrush(QBrush(QColor("#1a1a1a")))
        self.setMinimumSize(300, 220)

    # ── public API ──────────────────────────────────────────────────────

    def load_image(self, path: str, corrections: dict | None = None):
        self._current_path = path
        bgr = cv2.imread(path)
        if bgr is None:
            return
        if corrections:
            bgr = _apply_color_correction(bgr, corrections)
        self._img_h, self._img_w = bgr.shape[:2]
        qi = _bgr_to_qimage(bgr)
        pm = QPixmap.fromImage(qi)
        scene = self._scene
        if self._pix_item is not None:
            scene.removeItem(self._pix_item)
        self._pix_item = QGraphicsPixmapItem(pm)
        scene.addItem(self._pix_item)
        scene.setSceneRect(0, 0, self._img_w, self._img_h)
        self.fitInView(self._pix_item, Qt.AspectRatioMode.KeepAspectRatio)
        QTimer.singleShot(50, self._fit_image)
        QTimer.singleShot(200, self._fit_image)

    def set_mode(self, mode: str):
        self._mode = mode
        if mode == "add":
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.setCursor(QCursor(Qt.CursorShape.CrossCursor))
        else:
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))

    def add_point(self, x_img: float, y_img: float) -> int:
        idx = len(self._dots)
        dot = _CPDot(self, idx)
        dot.setPos(x_img, y_img)
        self._scene.addItem(dot)
        self._dots.append(dot)
        self.point_added.emit(idx, x_img, y_img)
        return idx

    def set_point_pos(self, idx: int, x_img: float, y_img: float):
        if 0 <= idx < len(self._dots):
            self._dots[idx].setPos(x_img, y_img)

    def remove_point(self, idx: int):
        if not (0 <= idx < len(self._dots)):
            return
        dot = self._dots.pop(idx)
        self.scene().removeItem(dot)
        # Renumber remaining dots
        for i, d in enumerate(self._dots):
            d._idx = i
            d.update()
        self.point_removed.emit(idx)

    def clear_points(self):
        for dot in self._dots:
            self.scene().removeItem(dot)
        self._dots.clear()

    def point_positions(self) -> List[Tuple[float, float]]:
        return [(d.pos().x(), d.pos().y()) for d in self._dots]

    # ── internal callbacks ───────────────────────────────────────────

    def _on_dot_moved(self, idx: int):
        if 0 <= idx < len(self._dots):
            p = self._dots[idx].pos()
            self.point_moved.emit(idx, p.x(), p.y())

    # ── event overrides ──────────────────────────────────────────────

    def mousePressEvent(self, event):
        if self._mode == "add" and event.button() == Qt.MouseButton.LeftButton:
            # Only add if not clicking an existing dot
            pt = self.mapToScene(event.position().toPoint())
            items = self._scene.items(pt)
            if not any(isinstance(it, _CPDot) for it in items):
                self.add_point(pt.x(), pt.y())
                return
        if event.button() == Qt.MouseButton.RightButton:
            pt = self.mapToScene(event.position().toPoint())
            self._remove_nearest(pt)
            return
        super().mousePressEvent(event)

    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)

    def _remove_nearest(self, scene_pt: QPointF):
        if not self._dots:
            return
        best_i, best_d = 0, float("inf")
        for i, dot in enumerate(self._dots):
            dx = dot.pos().x() - scene_pt.x()
            dy = dot.pos().y() - scene_pt.y()
            d = dx * dx + dy * dy
            if d < best_d:
                best_d, best_i = d, i
        if best_d < (50**2):
            self.remove_point(best_i)

    def _fit_image(self):
        if self._pix_item is not None:
            self.fitInView(self._pix_item, Qt.AspectRatioMode.KeepAspectRatio)

    def showEvent(self, event):
        super().showEvent(event)
        self._fit_image()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit_image()


# ---------------------------------------------------------------------------
# Section 4 — Dual-pane Control Point Editor
# ---------------------------------------------------------------------------


class ControlPointEditor(QWidget):
    """
    Two _CPCanvas panels side by side.  Manages synchronized point
    lists: left[i] ↔ right[i].

    Solve modes
    -----------
    DLT (exact)   : cv2.findHomography(pts, method=0) — passes through
                    every pair, no outlier rejection.  Use when you trust
                    all your correspondences.
    DLT + RANSAC  : cv2.findHomography(pts, method=cv2.RANSAC) — robust
                    to a few bad user clicks.
    Auto + Manual : run ORB first, then append user pairs on top; re-solve.
    """

    homography_solved = Signal(np.ndarray, float)  # H (3×3), mean_reprojection_err

    def __init__(self, parent=None):
        super().__init__(parent)
        self._H: Optional[np.ndarray] = None
        self._cc_a: dict = {}
        self._cc_b: dict = {}
        self._auto_pts_a: List[Tuple[float, float]] = []
        self._auto_pts_b: List[Tuple[float, float]] = []
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(4)

        # ── Toolbar ──────────────────────────────────────────────────
        tb = QHBoxLayout()
        self._mode_btn = QPushButton("✎ Add Points")
        self._mode_btn.setCheckable(True)
        self._mode_btn.setChecked(True)
        self._mode_btn.toggled.connect(self._on_mode_toggle)
        apply_shadow_effect(self._mode_btn, radius=4, y_offset=2)
        tb.addWidget(self._mode_btn)

        btn_clear = QPushButton("Clear All")
        btn_clear.clicked.connect(self._clear_all)
        apply_shadow_effect(btn_clear, radius=4, y_offset=2)
        tb.addWidget(btn_clear)

        btn_auto = QPushButton("⚡ Auto-Detect (ORB)")
        btn_auto.setToolTip(
            "Run ORB+RANSAC to populate initial correspondences automatically."
        )
        btn_auto.clicked.connect(self._auto_detect)
        apply_shadow_effect(btn_auto, radius=4, y_offset=2)
        tb.addWidget(btn_auto)

        btn_suggest = QPushButton("💡 Suggest Next")
        btn_suggest.setToolTip(
            "Propose the best unused ORB match as the next point pair."
        )
        btn_suggest.clicked.connect(self._suggest_next)
        apply_shadow_effect(btn_suggest, radius=4, y_offset=2)
        tb.addWidget(btn_suggest)

        tb.addStretch()

        self._solve_mode = QComboBox()
        self._solve_mode.addItems(["DLT (exact)", "DLT + RANSAC", "Auto + Manual"])
        self._solve_mode.setToolTip(
            "DLT (exact): homography passes through every pair — "
            "trusts all user points.\n"
            "DLT + RANSAC: robust to a few bad clicks.\n"
            "Auto + Manual: appends user pairs on top of auto-detected ones."
        )
        tb.addWidget(QLabel("Solve:"))
        tb.addWidget(self._solve_mode)

        btn_solve = QPushButton("🔧 Solve Homography")
        btn_solve.setStyleSheet(
            "background:#1976D2; color:white; font-weight:bold; padding:4px 10px;"
        )
        btn_solve.clicked.connect(self._solve)
        apply_shadow_effect(btn_solve, radius=4, y_offset=2)
        tb.addWidget(btn_solve)

        root.addLayout(tb)

        # ── Dual canvas ───────────────────────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)

        left_w = QWidget()
        left_l = QVBoxLayout(left_w)
        left_l.setContentsMargins(0, 0, 0, 0)
        self._lbl_a = QLabel("Frame A  (click to place points)")
        self._lbl_a.setStyleSheet("color:#aaa; font-size:10px;")
        left_l.addWidget(self._lbl_a)
        self._canvas_a = _CPCanvas("A")
        self._canvas_a.point_added.connect(self._on_a_added)
        self._canvas_a.point_moved.connect(self._on_a_moved)
        self._canvas_a.point_removed.connect(self._on_a_removed)
        left_l.addWidget(self._canvas_a)
        splitter.addWidget(left_w)

        right_w = QWidget()
        right_l = QVBoxLayout(right_w)
        right_l.setContentsMargins(0, 0, 0, 0)
        self._lbl_b = QLabel("Frame B  (click to place matching points)")
        self._lbl_b.setStyleSheet("color:#aaa; font-size:10px;")
        right_l.addWidget(self._lbl_b)
        self._canvas_b = _CPCanvas("B")
        self._canvas_b.point_added.connect(self._on_b_added)
        self._canvas_b.point_moved.connect(self._on_b_moved)
        self._canvas_b.point_removed.connect(self._on_b_removed)
        right_l.addWidget(self._canvas_b)
        splitter.addWidget(right_w)

        root.addWidget(splitter, 1)

        # ── Status ───────────────────────────────────────────────────
        self._status = QLabel("Load two frames, then click to place correspondences.")
        self._status.setStyleSheet("color:#aaa; font-size:10px;")
        root.addWidget(self._status)

    # ── Public API ──────────────────────────────────────────────────

    def load_pair(
        self,
        path_a: str,
        path_b: str,
        cc_a: dict | None = None,
        cc_b: dict | None = None,
    ):
        self._path_a = path_a
        self._path_b = path_b
        self._cc_a = cc_a or {}
        self._cc_b = cc_b or {}
        self._auto_pts_a.clear()
        self._auto_pts_b.clear()
        self._canvas_a.clear_points()
        self._canvas_b.clear_points()
        self._canvas_a.load_image(path_a, self._cc_a)
        self._canvas_b.load_image(path_b, self._cc_b)
        self._lbl_a.setText(f"Frame A:  {os.path.basename(path_a)}")
        self._lbl_b.setText(f"Frame B:  {os.path.basename(path_b)}")
        self._status.setText(
            "Frames loaded. Place ≥4 corresponding points, then Solve."
        )

    def get_homography(self) -> Optional[np.ndarray]:
        return self._H

    def fit_views(self):
        """Re-fit both canvases — call after the tab becomes visible."""
        self._canvas_a._fit_image()
        self._canvas_b._fit_image()

    # ── Slots ────────────────────────────────────────────────────────

    @Slot(bool)
    def _on_mode_toggle(self, checked: bool):
        mode = "add" if checked else "view"
        self._canvas_a.set_mode(mode)
        self._canvas_b.set_mode(mode)
        self._mode_btn.setText("✎ Add Points" if checked else "✋ Pan/Zoom")

    def _clear_all(self):
        self._canvas_a.clear_points()
        self._canvas_b.clear_points()
        self._auto_pts_a.clear()
        self._auto_pts_b.clear()
        self._H = None
        self._status.setText("Points cleared.")

    def _auto_detect(self):
        if not hasattr(self, "_path_a"):
            return
        self.setCursor(QCursor(Qt.CursorShape.WaitCursor))
        try:
            pts_a, pts_b = self._run_orb(self._path_a, self._path_b)
            if len(pts_a) < 4:
                self._status.setText("Auto-detect: fewer than 4 matches found.")
                return
            self._canvas_a.clear_points()
            self._canvas_b.clear_points()
            self._auto_pts_a = list(pts_a)
            self._auto_pts_b = list(pts_b)
            for x, y in pts_a:
                self._canvas_a.add_point(x, y)
            for x, y in pts_b:
                self._canvas_b.add_point(x, y)
            self._status.setText(
                f"Auto-detect: {len(pts_a)} ORB+RANSAC matches loaded.  "
                "Add/move points to refine, then Solve."
            )
        finally:
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))

    def _suggest_next(self):
        """Suggest the next best unused ORB match near the least-constrained region."""
        if not hasattr(self, "_path_a"):
            return
        if not self._auto_pts_a:
            self._auto_detect()
            return
        manual_a = set(self._canvas_a.point_positions())
        unused = [
            (i, pa, pb)
            for i, (pa, pb) in enumerate(zip(self._auto_pts_a, self._auto_pts_b))
            if pa not in manual_a
        ]
        if not unused:
            self._status.setText("No unused auto-matches left to suggest.")
            return

        # Pick the one farthest from any existing manual point
        def min_dist_to_existing(xy):
            ex = self._canvas_a.point_positions()
            if not ex:
                return float("inf")
            return min(math.hypot(xy[0] - p[0], xy[1] - p[1]) for p in ex)

        _, pa, pb = max(unused, key=lambda t: min_dist_to_existing(t[1]))
        self._canvas_a.add_point(pa[0], pa[1])
        self._canvas_b.add_point(pb[0], pb[1])
        self._status.setText(f"Suggested pair added at A=({pa[0]:.0f},{pa[1]:.0f}).")

    def _solve(self):
        pts_a_raw = self._canvas_a.point_positions()
        pts_b_raw = self._canvas_b.point_positions()
        n = min(len(pts_a_raw), len(pts_b_raw))
        if n < 4:
            self._status.setText(f"Need ≥4 matching pairs; have {n}.")
            return

        mode = self._solve_mode.currentText()
        pts_a = np.float32(pts_a_raw[:n])
        pts_b = np.float32(pts_b_raw[:n])

        # Append auto-detected pts if "Auto + Manual"
        if mode == "Auto + Manual" and self._auto_pts_a:
            ap = np.float32(self._auto_pts_a)
            bp = np.float32(self._auto_pts_b)
            pts_a = np.vstack([pts_a, ap])
            pts_b = np.vstack([pts_b, bp])

        cv_method = cv2.RANSAC if "RANSAC" in mode else 0
        H, mask = cv2.findHomography(pts_a, pts_b, cv_method, 3.0)

        if H is None:
            self._status.setText("Homography solve failed — collinear points?")
            return

        self._H = H
        # Compute mean reprojection error on inliers
        n_in = int(mask.sum()) if mask is not None else n
        pts_h = cv2.perspectiveTransform(pts_a.reshape(-1, 1, 2), H).reshape(-1, 2)
        errs = np.linalg.norm(pts_h - pts_b, axis=1)
        mean_e = float(errs.mean())

        self._status.setText(
            f"H solved via {mode} — {n} pairs,  "
            f"{n_in} inliers,  mean reprojection error {mean_e:.2f} px."
        )
        self.homography_solved.emit(H, mean_e)

    # ── ORB helper ───────────────────────────────────────────────────

    @staticmethod
    def _run_orb(path_a: str, path_b: str, max_pts: int = 50) -> Tuple[list, list]:
        bgr_a = cv2.imread(path_a)
        bgr_b = cv2.imread(path_b)
        if bgr_a is None or bgr_b is None:
            return [], []

        # Scale to ≤1280px wide
        def _scale(img):
            h, w = img.shape[:2]
            s = min(1.0, 1280 / w)
            if s < 1.0:
                img = cv2.resize(
                    img, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA
                )
            return img, s

        a_s, sa = _scale(bgr_a)
        b_s, sb = _scale(bgr_b)

        orb = cv2.ORB_create(nfeatures=1000)
        bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
        ka, da = orb.detectAndCompute(cv2.cvtColor(a_s, cv2.COLOR_BGR2GRAY), None)
        kb, db = orb.detectAndCompute(cv2.cvtColor(b_s, cv2.COLOR_BGR2GRAY), None)
        if da is None or db is None or len(ka) < 4 or len(kb) < 4:
            return [], []

        matches = bf.knnMatch(da, db, k=2)
        good = [m for m, n in matches if m.distance < 0.75 * n.distance]
        if len(good) < 4:
            return [], []

        src = np.float32([ka[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
        dst = np.float32([kb[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
        _, mask = cv2.findHomography(src, dst, cv2.RANSAC, 5.0)
        if mask is None:
            return [], []

        inlier_idx = [i for i, m in enumerate(good) if mask[i, 0]]
        inlier_idx = inlier_idx[:max_pts]

        pts_a = [
            (ka[good[i].queryIdx].pt[0] / sa, ka[good[i].queryIdx].pt[1] / sa)
            for i in inlier_idx
        ]
        pts_b = [
            (kb[good[i].trainIdx].pt[0] / sb, kb[good[i].trainIdx].pt[1] / sb)
            for i in inlier_idx
        ]
        return pts_a, pts_b

    # ── Point sync callbacks ─────────────────────────────────────────

    def _on_a_added(self, idx, x, y):
        # Ensure canvas_b has a matching (initially identical) placeholder
        while len(self._canvas_b.point_positions()) <= idx:
            self._canvas_b.add_point(x, y)  # placeholder at same coords
        self._status.setText(
            f"Point {idx + 1} added to A.  Now click the matching location in Frame B."
        )

    def _on_b_added(self, idx, x, y):
        n_a = len(self._canvas_a.point_positions())
        if n_a <= idx:
            self._status.setText(
                f"Point {idx + 1} added to B.  "
                "Now click the matching location in Frame A."
            )

    def _on_a_moved(self, idx, x, y):
        pass

    def _on_b_moved(self, idx, x, y):
        pass

    def _on_a_removed(self, idx):
        if idx < len(self._canvas_b.point_positions()):
            self._canvas_b.remove_point(idx)

    def _on_b_removed(self, idx):
        if idx < len(self._canvas_a.point_positions()):
            self._canvas_a.remove_point(idx)


# ---------------------------------------------------------------------------
# Section 5 — Per-Frame Color Correction Widget
# ---------------------------------------------------------------------------


class _CCSlider(QWidget):
    """Label + QSlider row with live value display."""

    changed = Signal(str, float)  # key, value

    def __init__(
        self,
        label: str,
        key: str,
        lo: float,
        hi: float,
        default: float,
        step: float = 1.0,
    ):
        super().__init__()
        self._key = key
        self._lo = lo
        self._range = hi - lo
        self._step = step
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel(f"{label}:")
        lbl.setFixedWidth(90)
        lbl.setStyleSheet("color:#ccc;")
        row.addWidget(lbl)
        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, 200)
        self._slider.setValue(int((default - lo) / (hi - lo) * 200))
        self._slider.valueChanged.connect(self._emit)
        row.addWidget(self._slider, 1)
        self._val_lbl = QLabel(f"{default:.2f}")
        self._val_lbl.setFixedWidth(44)
        self._val_lbl.setStyleSheet("color:#aaa; font-size:10px;")
        row.addWidget(self._val_lbl)

        # Reset button
        self._default = default
        btn = QPushButton("↺")
        btn.setFixedWidth(24)
        btn.setToolTip("Reset to default")
        btn.clicked.connect(self._reset)
        row.addWidget(btn)

    def value(self) -> float:
        return self._lo + self._slider.value() / 200.0 * self._range

    def set_value(self, v: float):
        self._slider.setValue(int((v - self._lo) / self._range * 200))

    def _emit(self):
        v = self.value()
        self._val_lbl.setText(f"{v:.2f}")
        self.changed.emit(self._key, v)

    def _reset(self):
        self.set_value(self._default)


class ColorCorrectionWidget(QWidget):
    """Per-frame color/exposure corrections."""

    corrections_changed = Signal(dict)  # full dict for current frame

    def __init__(self, parent=None):
        super().__init__(parent)
        self._corrections: dict = {}
        self._path: str = ""
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(4)

        # Preview
        prev_row = QHBoxLayout()
        self._prev_lbl = QLabel("No image loaded")
        self._prev_lbl.setFixedHeight(160)
        self._prev_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._prev_lbl.setStyleSheet("background:#111; color:#555;")
        self._prev_lbl.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        prev_row.addWidget(self._prev_lbl, 1)
        root.addLayout(prev_row)

        # Sliders
        self._sliders: Dict[str, _CCSlider] = {}
        _defs = [
            ("Brightness", "brightness", -100.0, 100.0, 0.0),
            ("Contrast", "contrast", 0.1, 3.0, 1.0),
            ("Saturation", "saturation", 0.0, 3.0, 1.0),
            ("Gamma", "gamma", 0.2, 5.0, 1.0),
            ("Temperature", "temperature", -50.0, 50.0, 0.0),
        ]
        for name, key, lo, hi, default in _defs:
            s = _CCSlider(name, key, lo, hi, default)
            s.changed.connect(self._on_changed)
            self._sliders[key] = s
            root.addWidget(s)

        btn_row = QHBoxLayout()
        btn_reset = QPushButton("Reset All")
        btn_reset.clicked.connect(self._reset_all)
        apply_shadow_effect(btn_reset, radius=4, y_offset=2)
        btn_row.addWidget(btn_reset)

        btn_match = QPushButton("Match Adjacent →")
        btn_match.setToolTip(
            "Auto-match this frame's histogram to the next frame "
            "(requires both frames to be loaded)."
        )
        btn_match.clicked.connect(self._match_adjacent)
        apply_shadow_effect(btn_match, radius=4, y_offset=2)
        btn_row.addWidget(btn_match)
        btn_row.addStretch()
        root.addLayout(btn_row)
        root.addStretch()

        # Debounce for preview refresh
        self._debounce = QTimer()
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(120)
        self._debounce.timeout.connect(self._refresh_preview)

    def load_frame(self, path: str, existing_cc: dict | None = None):
        self._path = path
        self._corrections = dict(existing_cc or {})
        for key, slider in self._sliders.items():
            slider.set_value(self._corrections.get(key, slider._default))
        self._refresh_preview()

    def get_corrections(self) -> dict:
        return dict(self._corrections)

    def set_adjacent_path(self, path: str):
        self._adj_path = path

    def _on_changed(self, key: str, value: float):
        self._corrections[key] = value
        self._debounce.start()
        self.corrections_changed.emit(dict(self._corrections))

    def _reset_all(self):
        for slider in self._sliders.values():
            slider._reset()
        self._corrections.clear()
        self._refresh_preview()
        self.corrections_changed.emit({})

    def _match_adjacent(self):
        adj = getattr(self, "_adj_path", "")
        if not self._path or not adj:
            return
        ref = cv2.imread(adj)
        src = cv2.imread(self._path)
        if ref is None or src is None:
            return

        # Simple histogram matching on L channel in Lab
        ref_l = cv2.cvtColor(ref, cv2.COLOR_BGR2Lab)[:, :, 0].astype(np.float32)
        src_l = cv2.cvtColor(src, cv2.COLOR_BGR2Lab)[:, :, 0].astype(np.float32)

        mean_diff = float(ref_l.mean() - src_l.mean())
        ratio = float(ref_l.std()) / max(float(src_l.std()), 0.1)

        # Map to sliders
        # brightness offset → brightness slider
        self._sliders["brightness"].set_value(mean_diff)
        # std ratio → contrast slider (clamped)
        ratio = max(0.1, min(3.0, ratio))
        self._sliders["contrast"].set_value(ratio)

    def _refresh_preview(self):
        if not self._path:
            return
        bgr = cv2.imread(self._path)
        if bgr is None:
            return
        # Scale for preview
        h, w = bgr.shape[:2]
        scale = min(1.0, 400 / max(w, h, 1))
        if scale < 1.0:
            bgr = cv2.resize(bgr, (int(w * scale), int(h * scale)))
        bgr = _apply_color_correction(bgr, self._corrections)
        qi = _bgr_to_qimage(bgr)
        pm = QPixmap.fromImage(qi)
        self._prev_lbl.setPixmap(
            pm.scaled(
                self._prev_lbl.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )


# ---------------------------------------------------------------------------
# Section 6 — Seam Painter
# ---------------------------------------------------------------------------


class _PaintCanvas(QGraphicsView):
    """Paintable canvas showing the overlap blend.  Three brush modes:
    Force-A (red), Force-B (blue), Neutral (eraser).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._pix_item: Optional[QGraphicsPixmapItem] = None
        self._overlay: Optional[np.ndarray] = None  # RGBA paint layer, H×W×4
        self._overlay_item: Optional[QGraphicsPixmapItem] = None
        self._brush_mode = "A"  # "A" | "B" | "neutral"
        self._brush_size = 20
        self._painting = False
        self._last_pt: Optional[QPointF] = None
        self._img_w = 1
        self._img_h = 1

        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setBackgroundBrush(QBrush(QColor("#111")))
        self.setMinimumSize(300, 250)

    # ── Public API ───────────────────────────────────────────────────

    def load_blend(self, blend_bgr: np.ndarray):
        """Load the blended composite as background."""
        self._img_h, self._img_w = blend_bgr.shape[:2]
        self._overlay = np.zeros((self._img_h, self._img_w, 4), dtype=np.uint8)
        scene = self._scene
        if self._pix_item:
            scene.removeItem(self._pix_item)
        qi = _bgr_to_qimage(blend_bgr)
        pm = QPixmap.fromImage(qi)
        self._pix_item = QGraphicsPixmapItem(pm)
        scene.addItem(self._pix_item)
        scene.setSceneRect(0, 0, self._img_w, self._img_h)
        # Overlay item
        if self._overlay_item:
            scene.removeItem(self._overlay_item)
        self._overlay_item = QGraphicsPixmapItem()
        self._overlay_item.setZValue(5)
        scene.addItem(self._overlay_item)
        self._update_overlay_pixmap()
        self.fitInView(self._pix_item, Qt.AspectRatioMode.KeepAspectRatio)
        QTimer.singleShot(0, self._fit_image)

    def get_mask_a(self) -> np.ndarray:
        """Returns binary mask where user painted Force-A (red)."""
        if self._overlay is None:
            return np.zeros((self._img_h, self._img_w), dtype=np.uint8)
        return (self._overlay[:, :, 0] > 50).astype(np.uint8) * 255

    def get_mask_b(self) -> np.ndarray:
        if self._overlay is None:
            return np.zeros((self._img_h, self._img_w), dtype=np.uint8)
        return (self._overlay[:, :, 2] > 50).astype(np.uint8) * 255

    def clear_paint(self):
        if self._overlay is not None:
            self._overlay[:] = 0
            self._update_overlay_pixmap()

    def set_brush(self, mode: str, size: int):
        self._brush_mode = mode
        self._brush_size = size

    # ── Paint ────────────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._overlay is not None:
            self._painting = True
            self._last_pt = self.mapToScene(event.position().toPoint())
            self._paint_at(self._last_pt)
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._painting:
            pt = self.mapToScene(event.position().toPoint())
            self._paint_at(pt)
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._painting = False
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)

    def _paint_at(self, scene_pt: QPointF):
        cx = int(scene_pt.x())
        cy = int(scene_pt.y())
        r = self._brush_size
        x0 = max(0, cx - r)
        y0 = max(0, cy - r)
        x1 = min(self._img_w, cx + r)
        y1 = min(self._img_h, cy + r)
        if self._brush_mode == "A":
            self._overlay[y0:y1, x0:x1, 0] = 220  # red
            self._overlay[y0:y1, x0:x1, 2] = 0
            self._overlay[y0:y1, x0:x1, 3] = 120
        elif self._brush_mode == "B":
            self._overlay[y0:y1, x0:x1, 2] = 220  # blue
            self._overlay[y0:y1, x0:x1, 0] = 0
            self._overlay[y0:y1, x0:x1, 3] = 120
        else:
            self._overlay[y0:y1, x0:x1] = 0
        self._update_overlay_pixmap()

    def _update_overlay_pixmap(self):
        if self._overlay is None or self._overlay_item is None:
            return
        rgba = self._overlay
        qi = QImage(
            rgba.data,
            self._img_w,
            self._img_h,
            self._img_w * 4,
            QImage.Format.Format_RGBA8888,
        ).copy()
        self._overlay_item.setPixmap(QPixmap.fromImage(qi))

    def _fit_image(self):
        if self._pix_item is not None:
            self.fitInView(self._pix_item, Qt.AspectRatioMode.KeepAspectRatio)

    def showEvent(self, event):
        super().showEvent(event)
        self._fit_image()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit_image()


class SeamPainterWidget(QWidget):
    """
    Shows the blended overlap after alignment.  User paints hard
    constraints; "Compute Seam" finds the min-cost path respecting them.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._warped_a: Optional[np.ndarray] = None
        self._warped_b: Optional[np.ndarray] = None
        self._seam_mask: Optional[np.ndarray] = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(4)

        # Toolbar
        tb = QHBoxLayout()
        tb.addWidget(QLabel("Brush:"))

        self._btn_a = QPushButton("Force A (red)")
        self._btn_a.setCheckable(True)
        self._btn_a.setChecked(True)
        self._btn_a.setStyleSheet("background:#c62828; color:white; font-weight:bold;")
        self._btn_a.clicked.connect(lambda: self._set_brush("A"))
        tb.addWidget(self._btn_a)

        self._btn_b = QPushButton("Force B (blue)")
        self._btn_b.setCheckable(True)
        self._btn_b.setStyleSheet("background:#1565C0; color:white; font-weight:bold;")
        self._btn_b.clicked.connect(lambda: self._set_brush("B"))
        tb.addWidget(self._btn_b)

        self._btn_erase = QPushButton("Erase")
        self._btn_erase.setCheckable(True)
        self._btn_erase.clicked.connect(lambda: self._set_brush("neutral"))
        tb.addWidget(self._btn_erase)

        tb.addWidget(QLabel("Size:"))
        self._size_spin = QSpinBox()
        self._size_spin.setRange(2, 80)
        self._size_spin.setValue(20)
        self._size_spin.valueChanged.connect(self._update_brush)
        tb.addWidget(self._size_spin)

        tb.addStretch()

        btn_blend = QPushButton("Preview Blend")
        btn_blend.clicked.connect(self._preview_blend)
        apply_shadow_effect(btn_blend, radius=4, y_offset=2)
        tb.addWidget(btn_blend)

        btn_seam = QPushButton("🔧 Compute Seam")
        btn_seam.setStyleSheet(
            "background:#1976D2;color:white;font-weight:bold;padding:4px 8px;"
        )
        btn_seam.clicked.connect(self._compute_seam)
        apply_shadow_effect(btn_seam, radius=4, y_offset=2)
        tb.addWidget(btn_seam)

        btn_clear = QPushButton("Clear Paint")
        btn_clear.clicked.connect(self._clear)
        tb.addWidget(btn_clear)

        root.addLayout(tb)

        self._canvas = _PaintCanvas()
        root.addWidget(self._canvas, 1)

        self._status = QLabel(
            "Load two aligned frames and paint hard seam constraints."
        )
        self._status.setStyleSheet("color:#aaa; font-size:10px;")
        root.addWidget(self._status)

    def load_aligned_pair(self, warped_a: np.ndarray, warped_b: np.ndarray):
        self._warped_a = warped_a
        self._warped_b = warped_b
        blend = cv2.addWeighted(warped_a, 0.5, warped_b, 0.5, 0)
        self._canvas.load_blend(blend)
        self._status.setText(
            "Paint Force-A (red) / Force-B (blue) regions, then Compute Seam."
        )

    def get_seam_mask(self) -> Optional[np.ndarray]:
        return self._seam_mask

    def _set_brush(self, mode: str):
        for btn, m in [
            (self._btn_a, "A"),
            (self._btn_b, "B"),
            (self._btn_erase, "neutral"),
        ]:
            btn.setChecked(m == mode)
        self._canvas.set_brush(mode, self._size_spin.value())

    def _update_brush(self):
        for btn, m in [
            (self._btn_a, "A"),
            (self._btn_b, "B"),
            (self._btn_erase, "neutral"),
        ]:
            if btn.isChecked():
                self._canvas.set_brush(m, self._size_spin.value())
                return

    def _clear(self):
        self._canvas.clear_paint()

    def _preview_blend(self):
        if self._warped_a is None or self._warped_b is None:
            return
        blend = cv2.addWeighted(self._warped_a, 0.5, self._warped_b, 0.5, 0)
        self._canvas.load_blend(blend)

    def _compute_seam(self):
        if self._warped_a is None or self._warped_b is None:
            self._status.setText("No warped frames loaded.")
            return

        mask_a = self._canvas.get_mask_a()  # 255 = force use A here
        mask_b = self._canvas.get_mask_b()  # 255 = force use B here

        # Energy = per-pixel absolute difference
        diff = (
            cv2.absdiff(self._warped_a, self._warped_b).astype(np.float32).mean(axis=2)
        )
        H, W = diff.shape

        # Enforce constraints: 0 cost to keep A where painted A, ∞ cost otherwise
        energy = diff.copy()
        energy[mask_a > 0] = 0.0  # free to stay in A region
        energy[mask_b > 0] = 1e9  # avoid entering B-forced region from A side

        # DP shortest-path seam (horizontal seam separating top/bottom for vertical pan)
        # or pick direction automatically based on aspect ratio of the diff
        horizontal = W > H  # horizontal seam for vertical pans

        if not horizontal:
            energy = energy.T  # transpose → always run horizontal seam logic

        eh, ew = energy.shape
        M = energy.copy()
        for i in range(1, eh):
            for j in range(ew):
                nbrs = [M[i - 1, j]]
                if j > 0:
                    nbrs.append(M[i - 1, j - 1])
                if j < ew - 1:
                    nbrs.append(M[i - 1, j + 1])
                M[i, j] += min(nbrs)

        # Traceback
        path = np.zeros(eh, np.int32)
        j = int(np.argmin(M[eh - 1]))
        path[eh - 1] = j
        for i in range(eh - 2, -1, -1):
            nbrs = [j]
            if j > 0:
                nbrs.append(j - 1)
            if j < ew - 1:
                nbrs.append(j + 1)
            j = nbrs[int(np.argmin([M[i, c] for c in nbrs]))]
            path[i] = j

        # Build seam mask
        seam = np.ones((eh, ew), dtype=np.uint8) * 255  # 255 = use A
        for i in range(eh):
            seam[i, path[i] :] = 0  # 0 = use B

        if not horizontal:
            seam = seam.T

        self._seam_mask = seam

        # Show result: composite using seam
        result = np.where(seam[:, :, np.newaxis] > 0, self._warped_a, self._warped_b)
        self._canvas.load_blend(result.astype(np.uint8))
        self._status.setText(
            "Seam computed and applied to preview.  "
            "The seam mask will be used during Render."
        )


# ---------------------------------------------------------------------------
# Section 7 — Content-Aware Mesh Warp
# ---------------------------------------------------------------------------


class _MeshPin(QGraphicsEllipseItem):
    R = 6

    def __init__(self, canvas: "_MeshCanvas", gi: int, gj: int):
        super().__init__(-self.R, -self.R, 2 * self.R, 2 * self.R)
        self._canvas = canvas
        self._gi = gi
        self._gj = gj
        self.setBrush(QBrush(QColor("#FF9800")))
        self.setPen(QPen(QColor("white"), 1.5))
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setZValue(20)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self._canvas._on_pin_moved(self._gi, self._gj)
        return super().itemChange(change, value)


class _MeshCanvas(QGraphicsView):
    """Deformable-grid canvas.  Drag grid intersections to warp the image."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._pix_item: Optional[QGraphicsPixmapItem] = None
        self._pins: Dict[Tuple[int, int], _MeshPin] = {}
        self._grid_lines: List[QGraphicsLineItem] = []
        self._img_w = 1
        self._img_h = 1
        self._rows = 5
        self._cols = 8
        self._orig_positions: Dict[Tuple[int, int], Tuple[float, float]] = {}
        self._displaced: Optional[np.ndarray] = None

        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setBackgroundBrush(QBrush(QColor("#111")))
        self.setMinimumSize(300, 250)

    def load_image(self, bgr: np.ndarray, rows: int = 5, cols: int = 8):
        self._img_h, self._img_w = bgr.shape[:2]
        self._rows, self._cols = rows, cols
        qi = _bgr_to_qimage(bgr)
        pm = QPixmap.fromImage(qi)
        scene = self._scene
        for line in self._grid_lines:
            scene.removeItem(line)
        self._grid_lines.clear()
        for pin in self._pins.values():
            scene.removeItem(pin)
        self._pins.clear()
        self._orig_positions.clear()

        if self._pix_item:
            scene.removeItem(self._pix_item)
        self._pix_item = QGraphicsPixmapItem(pm)
        scene.addItem(self._pix_item)
        scene.setSceneRect(0, 0, self._img_w, self._img_h)

        # Create pins at grid intersections
        dx = self._img_w / cols
        dy = self._img_h / rows
        for gi in range(rows + 1):
            for gj in range(cols + 1):
                x = gj * dx
                y = gi * dy
                pin = _MeshPin(self, gi, gj)
                pin.setPos(x, y)
                scene.addItem(pin)
                self._pins[(gi, gj)] = pin
                self._orig_positions[(gi, gj)] = (x, y)

        self._draw_grid_lines()
        self.fitInView(self._pix_item, Qt.AspectRatioMode.KeepAspectRatio)
        QTimer.singleShot(0, self._fit_image)

    def reset_pins(self):
        for (gi, gj), pin in self._pins.items():
            ox, oy = self._orig_positions[(gi, gj)]
            pin.setPos(ox, oy)
        self._draw_grid_lines()
        self._displaced = None

    def _on_pin_moved(self, gi, gj):
        self._draw_grid_lines()

    def _draw_grid_lines(self):
        scene = self._scene
        for line in self._grid_lines:
            scene.removeItem(line)
        self._grid_lines.clear()
        pen = QPen(QColor("#FF980088"), 1)
        for gi in range(self._rows + 1):
            for gj in range(self._cols):
                p1 = self._pins[(gi, gj)].pos()
                p2 = self._pins[(gi, gj + 1)].pos()
                item = QGraphicsLineItem(p1.x(), p1.y(), p2.x(), p2.y())
                item.setPen(pen)
                item.setZValue(5)
                scene.addItem(item)
                self._grid_lines.append(item)
        for gi in range(self._rows):
            for gj in range(self._cols + 1):
                p1 = self._pins[(gi, gj)].pos()
                p2 = self._pins[(gi + 1, gj)].pos()
                item = QGraphicsLineItem(p1.x(), p1.y(), p2.x(), p2.y())
                item.setPen(pen)
                item.setZValue(5)
                scene.addItem(item)
                self._grid_lines.append(item)

    def compute_warp(self) -> np.ndarray:
        """Return warped image via thin-plate spline from pin displacements."""
        # Collect displaced pins
        src_pts = []
        dst_pts = []
        for (gi, gj), pin in self._pins.items():
            ox, oy = self._orig_positions[(gi, gj)]
            nx, ny = pin.pos().x(), pin.pos().y()
            if abs(nx - ox) > 0.5 or abs(ny - oy) > 0.5:
                src_pts.append([ox, oy])
                dst_pts.append([nx, ny])

        if not src_pts:
            return None  # no displacement

        src = np.float32(src_pts)
        dst = np.float32(dst_pts)

        # Build dense remap via TPS approximation using scattered interpolation
        try:
            from scipy.interpolate import RBFInterpolator

            xs = np.arange(self._img_w, dtype=np.float32)
            ys = np.arange(self._img_h, dtype=np.float32)
            gx, gy = np.meshgrid(xs, ys)
            grid_pts = np.column_stack([gx.ravel(), gy.ravel()])

            interp_x = RBFInterpolator(
                src, dst[:, 0] - src[:, 0], kernel="thin_plate_spline"
            )
            interp_y = RBFInterpolator(
                src, dst[:, 1] - src[:, 1], kernel="thin_plate_spline"
            )

            dx_field = interp_x(grid_pts).reshape(self._img_h, self._img_w)
            dy_field = interp_y(grid_pts).reshape(self._img_h, self._img_w)

            map_x = (gx + dx_field).astype(np.float32)
            map_y = (gy + dy_field).astype(np.float32)
            self._displaced = (map_x, map_y)
            return map_x, map_y

        except ImportError:
            # Fallback: bilinear interpolation via cv2 sparse TPS
            tps = cv2.createThinPlateSplineShapeTransformer()
            tps.estimateTransformation(
                dst.reshape(1, -1, 2),
                src.reshape(1, -1, 2),
                [cv2.DMatch(i, i, 0) for i in range(len(src))],
            )
            map_xy = np.zeros((self._img_h, self._img_w, 2), dtype=np.float32)
            xs = np.arange(self._img_w, dtype=np.float32)
            ys = np.arange(self._img_h, dtype=np.float32)
            gx, gy = np.meshgrid(xs, ys)
            pts_in = (
                np.column_stack([gx.ravel(), gy.ravel()])
                .reshape(1, -1, 2)
                .astype(np.float32)
            )
            _, pts_out = tps.applyTransformation(pts_in)
            pts_out = pts_out.reshape(self._img_h, self._img_w, 2)
            return pts_out[:, :, 0], pts_out[:, :, 1]

    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)

    def _fit_image(self):
        if self._pix_item is not None:
            self.fitInView(self._pix_item, Qt.AspectRatioMode.KeepAspectRatio)

    def showEvent(self, event):
        super().showEvent(event)
        self._fit_image()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._fit_image()


class MeshWarpWidget(QWidget):
    """Pin-based mesh warp panel."""

    warp_applied = Signal(np.ndarray)  # warped BGR image

    def __init__(self, parent=None):
        super().__init__(parent)
        self._bgr: Optional[np.ndarray] = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)

        tb = QHBoxLayout()
        tb.addWidget(QLabel("Grid:"))

        self._rows_spin = QSpinBox()
        self._rows_spin.setRange(2, 20)
        self._rows_spin.setValue(5)
        self._rows_spin.setPrefix("rows: ")
        tb.addWidget(self._rows_spin)

        self._cols_spin = QSpinBox()
        self._cols_spin.setRange(2, 30)
        self._cols_spin.setValue(8)
        self._cols_spin.setPrefix("cols: ")
        tb.addWidget(self._cols_spin)

        btn_reload = QPushButton("Rebuild Grid")
        btn_reload.clicked.connect(self._rebuild_grid)
        apply_shadow_effect(btn_reload, radius=4, y_offset=2)
        tb.addWidget(btn_reload)

        btn_reset = QPushButton("Reset Pins")
        btn_reset.clicked.connect(lambda: self._canvas.reset_pins())
        apply_shadow_effect(btn_reset, radius=4, y_offset=2)
        tb.addWidget(btn_reset)

        tb.addStretch()

        btn_apply = QPushButton("⚡ Apply Warp")
        btn_apply.setStyleSheet(
            "background:#1976D2;color:white;font-weight:bold;padding:4px 8px;"
        )
        btn_apply.clicked.connect(self._apply_warp)
        apply_shadow_effect(btn_apply, radius=4, y_offset=2)
        tb.addWidget(btn_apply)

        root.addLayout(tb)

        self._canvas = _MeshCanvas()
        root.addWidget(self._canvas, 1)

        self._status = QLabel("Load an image, drag grid pins to warp, then Apply Warp.")
        self._status.setStyleSheet("color:#aaa; font-size:10px;")
        root.addWidget(self._status)

    def load_image(self, bgr: np.ndarray):
        self._bgr = bgr
        self._canvas.load_image(bgr, self._rows_spin.value(), self._cols_spin.value())
        self._status.setText("Drag orange pins to warp.  Apply Warp when done.")

    def _rebuild_grid(self):
        if self._bgr is not None:
            self._canvas.load_image(
                self._bgr, self._rows_spin.value(), self._cols_spin.value()
            )

    def _apply_warp(self):
        if self._bgr is None:
            return
        result = self._canvas.compute_warp()
        if result is None:
            self._status.setText("No displacement — drag pins first.")
            return
        map_x, map_y = result
        warped = cv2.remap(
            self._bgr, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT
        )
        self._bgr = warped
        self._canvas.load_image(
            warped, self._rows_spin.value(), self._cols_spin.value()
        )
        self.warp_applied.emit(warped)
        self._status.setText("Warp applied.  You can continue refining or export.")


# ---------------------------------------------------------------------------
# Section 8 — Render Panel
# ---------------------------------------------------------------------------


class RenderPanel(QWidget):
    """Final composite with chosen blending mode."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sequence: List[str] = []
        self._homographies: Dict[Tuple[int, int], np.ndarray] = {}
        self._seam_masks: Dict[Tuple[int, int], np.ndarray] = {}
        self._corrections: Dict[str, dict] = {}
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)

        form = QFormLayout()
        self._blend_mode = QComboBox()
        self._blend_mode.addItems(
            ["Seam mask", "Feather (50% overlap)", "Laplacian (5-band)"]
        )
        form.addRow("Blend mode:", self._blend_mode)

        self._use_cc = QCheckBox("Apply color corrections")
        self._use_cc.setChecked(True)
        form.addRow("", self._use_cc)

        self._use_seam = QCheckBox("Use painted seam masks")
        self._use_seam.setChecked(True)
        form.addRow("", self._use_seam)

        root.addLayout(form)

        btn_row = QHBoxLayout()
        self._btn_render = QPushButton("⚡ Render Panorama")
        self._btn_render.setStyleSheet(
            "background:#388E3C; color:white; font-weight:bold; padding:6px 16px;"
        )
        self._btn_render.clicked.connect(self._render)
        apply_shadow_effect(self._btn_render, radius=6, y_offset=2)
        btn_row.addWidget(self._btn_render)

        btn_save = QPushButton("Save…")
        btn_save.clicked.connect(self._save)
        apply_shadow_effect(btn_save, radius=4, y_offset=2)
        btn_row.addWidget(btn_save)
        btn_row.addStretch()
        root.addLayout(btn_row)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.hide()
        root.addWidget(self._progress)

        self._preview_lbl = QLabel()
        self._preview_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_lbl.setStyleSheet("background:#111;")
        self._preview_lbl.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        root.addWidget(self._preview_lbl, 1)

        self._status = QLabel("Set sequence and homographies, then Render.")
        self._status.setStyleSheet("color:#aaa; font-size:10px;")
        root.addWidget(self._status)

        self._result_bgr: Optional[np.ndarray] = None

    def set_pipeline(
        self,
        sequence: List[str],
        homographies: Dict[Tuple[int, int], np.ndarray],
        seam_masks: Dict[Tuple[int, int], np.ndarray],
        corrections: Dict[str, dict],
    ):
        self._sequence = sequence
        self._homographies = homographies
        self._seam_masks = seam_masks
        self._corrections = corrections
        self._status.setText(
            f"Sequence: {len(sequence)} frames, "
            f"{len(homographies)} homographies.  Ready to render."
        )

    def _render(self):
        if len(self._sequence) < 2:
            QMessageBox.warning(self, "Render", "Need ≥2 frames in sequence.")
            return
        self._btn_render.setEnabled(False)
        self._progress.show()
        self._progress.setValue(0)

        try:
            result = self._do_render()
            if result is not None:
                self._result_bgr = result
                qi = _bgr_to_qimage(result)
                pm = QPixmap.fromImage(qi)
                self._preview_lbl.setPixmap(
                    pm.scaled(
                        self._preview_lbl.size(),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
                self._status.setText(
                    f"Render complete: {result.shape[1]}×{result.shape[0]} px."
                )
        except Exception as e:
            QMessageBox.critical(self, "Render Error", str(e))
        finally:
            self._btn_render.setEnabled(True)
            self._progress.hide()

    def _do_render(self) -> Optional[np.ndarray]:
        seq = self._sequence
        N = len(seq)

        # Load frames (with optional CC)
        frames = []
        for i, p in enumerate(seq):
            bgr = cv2.imread(p)
            if bgr is None:
                raise RuntimeError(f"Could not read '{p}'.")
            if self._use_cc.isChecked():
                cc = self._corrections.get(p, {})
                if cc:
                    bgr = _apply_color_correction(bgr, cc)
            frames.append(bgr)
            self._progress.setValue(int((i + 1) / N * 30))
            QApplication.processEvents()

        # Compute cumulative transforms (sequential chain)
        H, W = frames[0].shape[:2]
        affines = [np.eye(2, 3, dtype=np.float32)]
        for i in range(1, N):
            key = (i - 1, i)
            Hpair = self._homographies.get(key)
            if Hpair is None:
                # Identity fallback (stacked)
                affines.append(affines[-1].copy())
                continue
            # Compose: t_i = H_pair @ t_{i-1}  (simplified: translate by homography centroid)
            # For display purposes use the affine translation from H
            tx = float(Hpair[0, 2])
            ty = float(Hpair[1, 2])
            M = np.eye(2, 3, dtype=np.float32)
            M[0, 2] = affines[-1][0, 2] + tx
            M[1, 2] = affines[-1][1, 2] + ty
            affines.append(M)
            self._progress.setValue(30 + int(i / N * 10))
            QApplication.processEvents()

        # Canvas bounds
        all_pts = []
        for i, (frm, M) in enumerate(zip(frames, affines)):
            fh, fw = frm.shape[:2]
            corners = np.float32([[0, 0], [fw, 0], [fw, fh], [0, fh]])
            warped_c = corners + M[:, 2]
            all_pts.append(warped_c)
        all_pts = np.vstack(all_pts)
        min_xy = all_pts.min(axis=0)
        max_xy = all_pts.max(axis=0)
        T = -min_xy
        cw = int(np.ceil(max_xy[0] - min_xy[0]))
        ch = int(np.ceil(max_xy[1] - min_xy[1]))
        cw, ch = min(cw, 32768), min(ch, 32768)

        canvas = np.zeros((ch, cw, 3), dtype=np.float64)
        weight = np.zeros((ch, cw), dtype=np.float64)

        blend_mode = self._blend_mode.currentText()

        for i, (frm, M) in enumerate(zip(frames, affines)):
            Mt = M.copy()
            Mt[0, 2] += T[0]
            Mt[1, 2] += T[1]
            warped = cv2.warpAffine(frm, Mt, (cw, ch), flags=cv2.INTER_LINEAR)
            valid = (warped.max(axis=2) > 0).astype(np.float64)

            if blend_mode == "Seam mask" and i > 0:
                key = (i - 1, i)
                smask = self._seam_masks.get(key)
                if smask is not None:
                    # Warp the seam mask too
                    sm_w = cv2.warpAffine(smask, Mt, (cw, ch), flags=cv2.INTER_NEAREST)
                    alpha = (sm_w > 0).astype(np.float64)
                    canvas += warped.astype(np.float64) * alpha[:, :, np.newaxis]
                    weight += alpha
                    self._progress.setValue(40 + int(i / N * 55))
                    QApplication.processEvents()
                    continue

            # Feather / laplacian — simple additive for now
            canvas += warped.astype(np.float64) * valid[:, :, np.newaxis]
            weight += valid
            self._progress.setValue(40 + int(i / N * 55))
            QApplication.processEvents()

        weight = np.maximum(weight, 1.0)
        result = np.clip(canvas / weight[:, :, np.newaxis], 0, 255).astype(np.uint8)

        # Crop black border
        gray = result.mean(axis=2)
        rows = np.any(gray > 0, axis=1)
        cols = np.any(gray > 0, axis=0)
        if rows.any() and cols.any():
            r0, r1 = np.argmax(rows), len(rows) - np.argmax(rows[::-1])
            c0, c1 = np.argmax(cols), len(cols) - np.argmax(cols[::-1])
            result = result[r0:r1, c0:c1]

        self._progress.setValue(100)
        return result

    def _save(self):
        if self._result_bgr is None:
            QMessageBox.information(self, "Save", "Render first.")
            return
        p, _ = QFileDialog.getSaveFileName(
            self,
            "Save Panorama",
            "",
            "PNG (*.png);;JPEG (*.jpg *.jpeg);;WebP (*.webp)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if p:
            cv2.imwrite(p, self._result_bgr)


# ---------------------------------------------------------------------------
# Section 9 — Main HybridStitchPanel
# ---------------------------------------------------------------------------


class _FrameListItem(QListWidgetItem):
    def __init__(self, path: str):
        super().__init__(os.path.basename(path))
        self.setData(Qt.ItemDataRole.UserRole, path)
        self.setToolTip(path)
        pm = _load_thumb(path, _THUMB_W, _THUMB_H)
        from PySide6.QtGui import QIcon

        self.setIcon(QIcon(pm))
        self.setSizeHint(QSize(_THUMB_W + 4, _THUMB_H + 8))


class HybridStitchPanel(QWidget):
    """
    Human-in-the-loop stitching panel.

    Left sidebar  : frame sequence list with thumbnail icons.
    Right area    : tabbed tool panels (Control Points, Color Correct,
                    Seam Painter, Mesh Warp, Render).
    """

    # Emitted when user accepts a complete sequence + pipeline for final use
    sequence_accepted = Signal(list)  # List[str] paths in order

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sequence: List[str] = []
        self._homographies: Dict[Tuple[int, int], np.ndarray] = {}
        self._seam_masks: Dict[Tuple[int, int], np.ndarray] = {}
        self._corrections: Dict[str, dict] = {}
        self._current_pair: Tuple[int, int] = (0, 1)
        self._build_ui()

    # ── UI construction ──────────────────────────────────────────────

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(6)

        # ── Left sidebar: sequence list ───────────────────────────────
        sidebar = QWidget()
        sidebar.setFixedWidth(270)
        sl = QVBoxLayout(sidebar)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.setSpacing(4)

        seq_group = QGroupBox("Sequence")
        seq_group.setStyleSheet(_DARK_GROUP)
        seq_l = QVBoxLayout(seq_group)

        self._seq_list = QListWidget()
        self._seq_list.setMinimumHeight(160)
        self._seq_list.setIconSize(QSize(_THUMB_W, _THUMB_H))
        self._seq_list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self._seq_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self._seq_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self._seq_list.setSpacing(2)
        self._seq_list.model().rowsMoved.connect(self._on_seq_reordered)
        self._seq_list.currentRowChanged.connect(self._on_seq_selection_changed)
        self._seq_list.setStyleSheet(
            "QListWidget { background:#1e1f22; } "
            "QListWidget::item:selected { background:#1976D2; }"
        )
        seq_l.addWidget(self._seq_list)

        for label, slot in [
            ("Add Frames…", self._add_frames),
            ("Remove Selected", self._remove_frame),
            ("Move Up ↑", self._move_up),
            ("Move Down ↓", self._move_down),
            ("Clear All", self._clear_sequence),
        ]:
            btn = QPushButton(label)
            btn.setFixedHeight(26)
            btn.clicked.connect(slot)
            seq_l.addWidget(btn)

        sl.addWidget(seq_group)

        # Pair selector
        pair_group = QGroupBox("Working Pair")
        pair_group.setStyleSheet(_DARK_GROUP)
        pair_l = QFormLayout(pair_group)
        self._pair_a_combo = QComboBox()
        self._pair_b_combo = QComboBox()
        self._pair_a_combo.currentIndexChanged.connect(self._on_pair_changed)
        self._pair_b_combo.currentIndexChanged.connect(self._on_pair_changed)
        pair_l.addRow("Frame A:", self._pair_a_combo)
        pair_l.addRow("Frame B:", self._pair_b_combo)

        btn_load_pair = QPushButton("Load Pair →")
        btn_load_pair.setStyleSheet(
            "background:#1565C0; color:white; font-weight:bold; padding:4px;"
        )
        btn_load_pair.clicked.connect(self._load_current_pair)
        apply_shadow_effect(btn_load_pair, radius=4, y_offset=2)
        pair_l.addRow("", btn_load_pair)

        btn_accept_h = QPushButton("✔ Accept H")
        btn_accept_h.setToolTip("Accept the current homography and seam for this pair.")
        btn_accept_h.setStyleSheet(
            "background:#2E7D32; color:white; font-weight:bold; padding:4px;"
        )
        btn_accept_h.clicked.connect(self._accept_pair)
        apply_shadow_effect(btn_accept_h, radius=4, y_offset=2)
        pair_l.addRow("", btn_accept_h)

        sl.addWidget(pair_group)

        btn_use = QPushButton("✔ Use as Stitch List")
        btn_use.setStyleSheet(
            "background:#388E3C; color:white; font-weight:bold; padding:5px;"
        )
        btn_use.clicked.connect(self._emit_sequence)
        apply_shadow_effect(btn_use, radius=6, y_offset=2)
        sl.addWidget(btn_use)

        sl.addStretch()
        root.addWidget(sidebar)

        # ── Right: tool tabs ──────────────────────────────────────────
        self._tools = QTabWidget()
        self._tools.setStyleSheet(
            "QTabWidget::pane { background:#2c2f33; } "
            "QTabBar::tab { background:#3a3d42; color:#ccc; padding:5px 12px; } "
            "QTabBar::tab:selected { background:#1976D2; color:white; }"
        )

        self._cp_editor = ControlPointEditor()
        self._cp_editor.homography_solved.connect(self._on_h_solved)
        self._tools.addTab(self._cp_editor, "Control Points")

        self._cc_widget = ColorCorrectionWidget()
        self._cc_widget.corrections_changed.connect(self._on_cc_changed)
        self._tools.addTab(self._cc_widget, "Color Correct")

        self._seam_widget = SeamPainterWidget()
        self._tools.addTab(self._seam_widget, "Seam Painter")

        self._mesh_widget = MeshWarpWidget()
        self._mesh_widget.warp_applied.connect(self._on_warp_applied)
        self._tools.addTab(self._mesh_widget, "Mesh Warp")

        self._render_panel = RenderPanel()
        self._tools.addTab(self._render_panel, "Render")

        # Status bar across all tools
        self._tools.currentChanged.connect(self._on_tab_changed)
        root.addWidget(self._tools, 1)

    # ── Sequence management ──────────────────────────────────────────

    def load_paths(self, paths: List[str]):
        """Load an existing path list into the sequence."""
        self._sequence = list(paths)
        self._refresh_list()

    def _add_frames(self):
        start = os.path.dirname(self._sequence[-1]) if self._sequence else ""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Add Frames",
            start,
            "Images (*.png *.jpg *.jpeg *.webp *.bmp *.tiff)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        for p in files:
            if p and p not in self._sequence:
                self._sequence.append(p)
        self._refresh_list()

    def _remove_frame(self):
        row = self._seq_list.currentRow()
        if 0 <= row < len(self._sequence):
            self._sequence.pop(row)
            self._seq_list.takeItem(row)
            self._refresh_combos()

    def _move_up(self):
        row = self._seq_list.currentRow()
        if row > 0:
            self._sequence[row], self._sequence[row - 1] = (
                self._sequence[row - 1],
                self._sequence[row],
            )
            self._refresh_list()
            self._seq_list.setCurrentRow(row - 1)

    def _move_down(self):
        row = self._seq_list.currentRow()
        if row < len(self._sequence) - 1:
            self._sequence[row], self._sequence[row + 1] = (
                self._sequence[row + 1],
                self._sequence[row],
            )
            self._refresh_list()
            self._seq_list.setCurrentRow(row + 1)

    def _clear_sequence(self):
        self._sequence.clear()
        self._seq_list.clear()
        self._pair_a_combo.clear()
        self._pair_b_combo.clear()

    def _refresh_list(self):
        self._seq_list.clear()
        for p in self._sequence:
            self._seq_list.addItem(_FrameListItem(p))
        self._refresh_combos()

    def _refresh_combos(self):
        names = [os.path.basename(p) for p in self._sequence]
        self._pair_a_combo.blockSignals(True)
        self._pair_b_combo.blockSignals(True)
        ca, cb = self._pair_a_combo.currentIndex(), self._pair_b_combo.currentIndex()
        self._pair_a_combo.clear()
        self._pair_b_combo.clear()
        self._pair_a_combo.addItems(names)
        self._pair_b_combo.addItems(names)
        n = len(names)
        if n >= 2:
            ia = max(0, min(ca, n - 1))
            ib = max(1, min(cb, n - 1))
            self._pair_a_combo.setCurrentIndex(ia)
            self._pair_b_combo.setCurrentIndex(ib)
            self._current_pair = (ia, ib)
        self._pair_a_combo.blockSignals(False)
        self._pair_b_combo.blockSignals(False)

    def _on_seq_reordered(self, *_args):
        self._sequence = [
            self._seq_list.item(r).data(Qt.ItemDataRole.UserRole)
            for r in range(self._seq_list.count())
        ]
        self._refresh_combos()

    def _on_seq_selection_changed(self, row: int):
        if 0 <= row < len(self._sequence):
            self._pair_a_combo.setCurrentIndex(row)
            self._pair_b_combo.setCurrentIndex(min(row + 1, len(self._sequence) - 1))

    def _on_pair_changed(self, _):
        ia = self._pair_a_combo.currentIndex()
        ib = self._pair_b_combo.currentIndex()
        self._current_pair = (ia, ib)

    def _load_current_pair(self):
        # Always read fresh from combos — cached _current_pair can be stale
        ia = self._pair_a_combo.currentIndex()
        ib = self._pair_b_combo.currentIndex()
        self._current_pair = (ia, ib)
        if ia < 0 or ib < 0 or ia >= len(self._sequence) or ib >= len(self._sequence):
            QMessageBox.warning(self, "Hybrid Stitch", "Select valid frames A and B.")
            return
        if ia == ib:
            QMessageBox.warning(
                self, "Hybrid Stitch", "Frame A and B must be different."
            )
            return
        pa, pb = self._sequence[ia], self._sequence[ib]
        cc_a = self._corrections.get(pa, {})
        cc_b = self._corrections.get(pb, {})
        self._cp_editor.load_pair(pa, pb, cc_a, cc_b)
        self._cc_widget.load_frame(pa, cc_a)
        self._cc_widget.set_adjacent_path(pb)
        # If a warp exists, populate seam painter
        key = (ia, ib)
        if key in self._homographies:
            self._refresh_seam_painter(pa, pb, cc_a, cc_b, self._homographies[key])

    def _accept_pair(self):
        H = self._cp_editor.get_homography()
        if H is None:
            QMessageBox.warning(
                self,
                "Hybrid Stitch",
                "No homography solved yet — use Control Points tab.",
            )
            return
        ia, ib = self._current_pair
        key = (ia, ib)
        self._homographies[key] = H
        # Also grab seam mask if painter has one
        seam = self._seam_widget.get_seam_mask()
        if seam is not None:
            self._seam_masks[key] = seam
        QMessageBox.information(
            self,
            "Pair Accepted",
            f"H for pair ({ia}→{ib}) saved.  "
            f"{len(self._homographies)} pair(s) in pipeline.",
        )
        self._update_render_panel()

    def _refresh_seam_painter(
        self, pa: str, pb: str, cc_a: dict, cc_b: dict, H: np.ndarray
    ):
        bgr_a = cv2.imread(pa)
        bgr_b = cv2.imread(pb)
        if bgr_a is None or bgr_b is None:
            return
        if cc_a:
            bgr_a = _apply_color_correction(bgr_a, cc_a)
        if cc_b:
            bgr_b = _apply_color_correction(bgr_b, cc_b)
        h, w = bgr_a.shape[:2]
        bgr_b_w = cv2.warpPerspective(bgr_b, H, (w, h))
        self._seam_widget.load_aligned_pair(bgr_a, bgr_b_w)

    def _on_h_solved(self, H: np.ndarray, err: float):
        ia, ib = self._current_pair
        if ia < len(self._sequence) and ib < len(self._sequence):
            pa, pb = self._sequence[ia], self._sequence[ib]
            cc_a = self._corrections.get(pa, {})
            cc_b = self._corrections.get(pb, {})
            self._refresh_seam_painter(pa, pb, cc_a, cc_b, H)

    def _on_cc_changed(self, cc: dict):
        ia = self._pair_a_combo.currentIndex()
        if 0 <= ia < len(self._sequence):
            self._corrections[self._sequence[ia]] = cc

    def _on_warp_applied(self, bgr: np.ndarray):
        ia = self._pair_a_combo.currentIndex()
        # The warp was applied to frame A; update the display in the CP editor
        pass

    def _on_tab_changed(self, idx: int):
        tab = self._tools.tabText(idx)
        if tab == "Control Points":
            QTimer.singleShot(50, self._cp_editor.fit_views)
        elif tab == "Mesh Warp":
            ia = self._pair_a_combo.currentIndex()
            if 0 <= ia < len(self._sequence):
                bgr = cv2.imread(self._sequence[ia])
                if bgr is not None:
                    cc = self._corrections.get(self._sequence[ia], {})
                    if cc:
                        bgr = _apply_color_correction(bgr, cc)
                    self._mesh_widget.load_image(bgr)
        elif tab == "Render":
            self._update_render_panel()

    def _update_render_panel(self):
        self._render_panel.set_pipeline(
            self._sequence,
            self._homographies,
            self._seam_masks,
            self._corrections,
        )

    def _emit_sequence(self):
        if not self._sequence:
            QMessageBox.information(self, "Hybrid Stitch", "Sequence is empty.")
            return
        self.sequence_accepted.emit(list(self._sequence))

    def _on_tab_changed(self, idx: int):  # noqa: F811
        tab_name = self._tools.tabText(idx)
        if tab_name == "Mesh Warp":
            ia = self._pair_a_combo.currentIndex()
            if 0 <= ia < len(self._sequence):
                bgr = cv2.imread(self._sequence[ia])
                if bgr is not None:
                    cc = self._corrections.get(self._sequence[ia], {})
                    if cc:
                        bgr = _apply_color_correction(bgr, cc)
                    self._mesh_widget.load_image(bgr)
        elif tab_name == "Render":
            self._update_render_panel()
