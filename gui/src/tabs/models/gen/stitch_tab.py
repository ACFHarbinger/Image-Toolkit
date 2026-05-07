"""
gui/src/tabs/models/gen/stitch_tab.py
======================================
EditTab — integrated image editing suite for anime frame stitching and
wallpaper creation.

Sub-tabs
--------
  Stitch  Interactive panorama stitching built on AnimeStitchPipeline.
          LoFTR keypoint matching, draggable affine overrides, BiRefNet
          foreground masking.

  Adjust  Per-image tone/color/geometric correction with live preview.
          Brightness · Contrast · Gamma · Saturation · Hue · Sharpen ·
          Blur · Rotate · Flip · Aspect-ratio crop · Send to Stitch.

  Canvas  Manual layout composer for wallpaper creation.
          Horizontal / Vertical / Grid, wallpaper size presets, background
          colour, per-image scale mode, adjustable gap.
"""

from __future__ import annotations
from backend.src.core.anime_stitch_pipeline import AnimeStitchPipeline

import os
import re
import tempfile
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
from PySide6.QtCore import (
    QObject,
    QPointF,
    QRectF,
    QRunnable,
    QSize,
    QThread,
    QThreadPool,
    QTimer,
    Qt,
    Signal,
    Slot,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QIcon,
    QImage,
    QImageReader,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QDragEnterEvent,
    QDragMoveEvent,
    QDropEvent,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsLineItem,
    QGraphicsPathItem,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsTextItem,
    QGraphicsView,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ....helpers.models.stitch_worker import (
    AdjustWorker,
    CanvasWorker,
    GraphStitchWorker,
    MatchWorker,
    MaskPreviewWorker,
    StitchWorker,
)
from ....styles.style import apply_shadow_effect
from .hybrid_stitch_panel import HybridStitchPanel

# ---------------------------------------------------------------------------
# Stitch-panel helpers
# ---------------------------------------------------------------------------

_CONF_HIGH = QColor(80, 220, 80, 180)
_CONF_MED  = QColor(220, 200, 40, 160)
_CONF_LOW  = QColor(220, 60, 60, 140)
_ANCHOR_RADIUS = 5
_MAX_DISPLAYED_MATCHES = 150


def _conf_color(c: float) -> QColor:
    if c >= 0.7:
        return _CONF_HIGH
    if c >= 0.5:
        return _CONF_MED
    return _CONF_LOW


def _bgr_to_qpixmap(bgr: np.ndarray, max_dim: int = 600) -> QPixmap:
    h, w = bgr.shape[:2]
    if max(h, w) > max_dim:
        scale = max_dim / max(h, w)
        bgr = cv2.resize(bgr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    h2, w2 = rgb.shape[:2]
    qi = QImage(rgb.data, w2, h2, 3 * w2, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(qi.copy())


def _mask_to_qpixmap(bgr: np.ndarray, mask: np.ndarray, max_dim: int = 600) -> QPixmap:
    overlay = bgr.copy()
    fg = mask < 128
    overlay[fg] = (overlay[fg] * 0.3 + np.array([180, 60, 60]) * 0.7).clip(0, 255).astype(np.uint8)
    return _bgr_to_qpixmap(overlay, max_dim)


def _qimage_to_qpixmap(qi: QImage, max_dim: int = 0) -> QPixmap:
    px = QPixmap.fromImage(qi)
    if max_dim > 0 and max(px.width(), px.height()) > max_dim:
        px = px.scaled(max_dim, max_dim, Qt.AspectRatioMode.KeepAspectRatio,
                       Qt.TransformationMode.SmoothTransformation)
    return px


# ---------------------------------------------------------------------------
# Thumbnail file picker
# ---------------------------------------------------------------------------

class _ThumbHub(QObject):
    loaded = Signal(str, int, object)  # path, generation, QImage


class _ThumbTask(QRunnable):
    def __init__(self, path: str, size: int, generation: int, hub: "_ThumbHub"):
        super().__init__()
        self._path = path
        self._size = size
        self._gen = generation
        self._hub = hub
        self.setAutoDelete(True)

    def run(self):
        img = QImage(self._path)
        if not img.isNull():
            img = img.scaled(
                self._size, self._size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        self._hub.loaded.emit(self._path, self._gen, img)


class _ThumbnailFilePicker(QDialog):
    _EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tif"}

    def __init__(self, parent=None, start_dir: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Add Source Frames")
        self.resize(960, 640)
        self._current_dir = start_dir or os.path.expanduser("~")
        self._selected_paths: List[str] = []
        self._item_map: Dict[str, QListWidgetItem] = {}
        self._generation = 0
        self._pool = QThreadPool.globalInstance()
        self._hub = _ThumbHub()
        self._hub.loaded.connect(self._on_thumb_loaded)
        self._thumb_size = 128
        self._folder_icon = _ThumbnailFilePicker._make_folder_icon(64)
        self._build_ui()
        self._navigate(self._current_dir)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Navigation bar
        nav = QHBoxLayout()
        btn_up = QPushButton("↑ Up")
        btn_up.setFixedWidth(60)
        btn_up.clicked.connect(self._go_up)
        self._addr_bar = QLineEdit()
        self._addr_bar.returnPressed.connect(
            lambda: self._navigate(self._addr_bar.text())
        )
        nav.addWidget(btn_up)
        nav.addWidget(self._addr_bar)
        layout.addLayout(nav)

        # Sidebar + thumbnail grid
        splitter = QSplitter(Qt.Orientation.Horizontal)

        self._sidebar = QListWidget()
        self._sidebar.setMaximumWidth(150)
        self._sidebar.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self._sidebar.setFrameShape(QListWidget.Shape.NoFrame)
        self._sidebar.setStyleSheet(
            "QListWidget { background:#1e1e1e; color:#ccc; }"
            "QListWidget::item { padding:5px 8px; color:#ccc; }"
            "QListWidget::item:selected { background:#1e5080; color:#fff; }"
            "QListWidget::item:hover { background:#2a3a4a; }"
        )
        self._populate_sidebar()
        self._sidebar.itemClicked.connect(
            lambda item: self._navigate(item.data(Qt.ItemDataRole.UserRole))
        )
        splitter.addWidget(self._sidebar)

        self._grid = QListWidget()
        self._grid.setViewMode(QListWidget.ViewMode.IconMode)
        self._grid.setIconSize(QSize(self._thumb_size, self._thumb_size))
        self._grid.setGridSize(QSize(self._thumb_size + 30, self._thumb_size + 40))
        self._grid.setResizeMode(QListWidget.ResizeMode.Adjust)
        self._grid.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self._grid.setMovement(QListWidget.Movement.Static)
        self._grid.setWrapping(True)
        self._grid.setWordWrap(True)
        self._grid.setSpacing(8)
        self._grid.setFrameShape(QListWidget.Shape.NoFrame)
        self._grid.setStyleSheet(
            "QListWidget { background:#1e1e1e; color:#ccc; }"
            "QListWidget::item { color:#ccc; border-radius:4px; padding:2px; }"
            "QListWidget::item:selected { background:#1e5080; color:#fff; }"
            "QListWidget::item:hover { background:#2a3a4a; }"
        )
        self._grid.itemDoubleClicked.connect(self._on_double_click)
        self._grid.itemSelectionChanged.connect(self._update_status)
        splitter.addWidget(self._grid)
        splitter.setSizes([150, 800])
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter)

        # Status + icon-size slider + buttons
        bottom = QHBoxLayout()
        self._status_label = QLabel("No files selected")

        size_lbl = QLabel("Icon size:")
        self._size_slider = QSlider(Qt.Orientation.Horizontal)
        self._size_slider.setRange(64, 256)
        self._size_slider.setValue(self._thumb_size)
        self._size_slider.setFixedWidth(120)
        self._size_slider.valueChanged.connect(self._on_size_changed)

        btn_open = QPushButton("Open")
        btn_open.setDefault(True)
        btn_open.clicked.connect(self._accept)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)

        bottom.addWidget(self._status_label)
        bottom.addStretch()
        bottom.addWidget(size_lbl)
        bottom.addWidget(self._size_slider)
        bottom.addWidget(btn_open)
        bottom.addWidget(btn_cancel)
        layout.addLayout(bottom)

    def _populate_sidebar(self):
        home = os.path.expanduser("~")
        bookmarks = [
            ("Home", home),
            ("Desktop", os.path.join(home, "Desktop")),
            ("Pictures", os.path.join(home, "Pictures")),
            ("Downloads", os.path.join(home, "Downloads")),
            ("Documents", os.path.join(home, "Documents")),
        ]
        for label, path in bookmarks:
            if os.path.isdir(path):
                item = QListWidgetItem(label)
                item.setData(Qt.ItemDataRole.UserRole, path)
                self._sidebar.addItem(item)

    def _navigate(self, path: str):
        path = os.path.normpath(path)
        if not os.path.isdir(path):
            return
        self._generation += 1
        gen = self._generation
        self._grid.clear()
        self._item_map.clear()
        self._current_dir = path
        self._addr_bar.setText(path)

        try:
            entries = sorted(
                os.scandir(path),
                key=lambda e: (not e.is_dir(), e.name.lower()),
            )
        except PermissionError:
            return

        for entry in entries:
            if entry.is_dir() and not entry.name.startswith("."):
                item = QListWidgetItem(self._folder_icon, entry.name)
                item.setData(Qt.ItemDataRole.UserRole, entry.path)
                item.setData(Qt.ItemDataRole.UserRole + 1, "dir")
                self._grid.addItem(item)
            elif os.path.splitext(entry.name)[1].lower() in self._EXTS:
                item = QListWidgetItem(entry.name)
                item.setData(Qt.ItemDataRole.UserRole, entry.path)
                item.setData(Qt.ItemDataRole.UserRole + 1, "file")
                self._grid.addItem(item)
                self._item_map[entry.path] = item
                self._pool.start(_ThumbTask(entry.path, self._thumb_size, gen, self._hub))

    @Slot(str, int, object)
    def _on_thumb_loaded(self, path: str, generation: int, img: QImage):
        if generation != self._generation:
            return
        item = self._item_map.get(path)
        if item and not img.isNull():
            item.setIcon(QIcon(QPixmap.fromImage(img)))

    def _on_double_click(self, item: QListWidgetItem):
        if item.data(Qt.ItemDataRole.UserRole + 1) == "dir":
            self._navigate(item.data(Qt.ItemDataRole.UserRole))

    def _go_up(self):
        parent = os.path.dirname(self._current_dir)
        if parent != self._current_dir:
            self._navigate(parent)

    def _update_status(self):
        n = sum(
            1 for it in self._grid.selectedItems()
            if it.data(Qt.ItemDataRole.UserRole + 1) == "file"
        )
        self._status_label.setText(
            f"{n} file{'s' if n != 1 else ''} selected" if n else "No files selected"
        )

    def _on_size_changed(self, value: int):
        self._thumb_size = value
        self._grid.setIconSize(QSize(value, value))
        self._grid.setGridSize(QSize(value + 28, value + 36))
        self._navigate(self._current_dir)

    def _accept(self):
        self._selected_paths = [
            it.data(Qt.ItemDataRole.UserRole)
            for it in self._grid.selectedItems()
            if it.data(Qt.ItemDataRole.UserRole + 1) == "file"
        ]
        if self._selected_paths:
            self.accept()

    def selected_paths(self) -> List[str]:
        return self._selected_paths

    @staticmethod
    def _make_folder_icon(size: int = 64) -> QIcon:
        pm = QPixmap(size, size)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        amber = QColor(240, 185, 60)
        dark_amber = QColor(200, 145, 20)
        p.setPen(QPen(dark_amber, 1))
        p.setBrush(QBrush(amber))
        tab_h = size // 8
        body_top = size // 4
        p.drawRoundedRect(2, body_top, size // 3, tab_h, 3, 3)
        p.drawRoundedRect(2, body_top + tab_h - 2, size - 4, size - body_top - tab_h - 2, 5, 5)
        p.end()
        return QIcon(pm)


# ---------------------------------------------------------------------------
# _AnchorHandle — draggable keypoint marker
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Node graph editor (Graph sub-tab)
# ---------------------------------------------------------------------------

_PORT_R      = 6
_NODE_W      = 220
_NODE_HDR_H  = 26
_NODE_BODY_H = 52
_THUMB_H     = 110    # height of the thumbnail area in _SourceNode
_EDGE_COL    = QColor(80, 200, 255, 200)


class _Port(QGraphicsEllipseItem):
    """Input (left) or output (right) connection port on a graph node."""

    def __init__(self, node, is_input: bool, index: int = 0):
        r = _PORT_R
        super().__init__(-r, -r, r * 2, r * 2)
        self.node = node
        self.is_input = is_input
        self.index = index
        self.edges: List["_GraphEdge"] = []
        self.setZValue(15)
        self.setAcceptHoverEvents(True)
        color = QColor(100, 180, 100) if is_input else QColor(80, 160, 230)
        self.setBrush(QBrush(color))
        pen = QPen(Qt.GlobalColor.white)
        pen.setWidth(1)
        self.setPen(pen)

    def scene_center(self):
        return self.mapToScene(QPointF(0, 0))

    def hoverEnterEvent(self, event):
        self.setScale(1.35)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.setScale(1.0)
        super().hoverLeaveEvent(event)

    def update_edges(self):
        for e in self.edges:
            e.update_path()


class _GraphEdge(QGraphicsPathItem):
    """Cubic-Bezier edge from an output port to an input port."""

    def __init__(self, src: _Port, dst: Optional[_Port] = None):
        super().__init__()
        self.src = src
        self.dst = dst
        pen = QPen(_EDGE_COL, 2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        self.setPen(pen)
        self.setZValue(5)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.update_path()

    def update_path(self, end_pos=None):
        p1 = self.src.scene_center()
        p2 = end_pos if end_pos is not None else (
            self.dst.scene_center() if self.dst else p1
        )
        dx = max(abs(p2.x() - p1.x()) * 0.5, 60)
        path = QPainterPath(p1)
        path.cubicTo(p1 + QPointF(dx, 0), p2 - QPointF(dx, 0), p2)
        self.setPath(path)

    def remove_self(self):
        if self in self.src.edges:
            self.src.edges.remove(self)
        if self.dst and self in self.dst.edges:
            self.dst.edges.remove(self)
        if self.scene():
            self.scene().removeItem(self)


class _BaseNode(QGraphicsRectItem):
    """Draggable rounded-rect node with title bar and ports."""

    def __init__(self, title: str, hdr_color: QColor, x: float = 0, y: float = 0):
        h = _NODE_HDR_H + _NODE_BODY_H
        super().__init__(0, 0, _NODE_W, h)
        self.setPos(x, y)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsScenePositionChanges)
        self.setZValue(10)
        self._title = title
        self._hdr_color = hdr_color
        self._input_ports: List[_Port] = []
        self._output_port: Optional[_Port] = None
        self.setPen(QPen(QColor(70, 70, 75), 1))
        self.setBrush(QBrush(QColor(42, 42, 48)))

    # ── port helpers ─────────────────────────────────────────────────────

    def _place_input_ports(self):
        n = len(self._input_ports)
        h = self.rect().height()
        for i, p in enumerate(self._input_ports):
            p.setPos(0, _NODE_HDR_H + (i + 1) * (h - _NODE_HDR_H) / (n + 1))

    def add_input_port(self) -> _Port:
        p = _Port(self, is_input=True, index=len(self._input_ports))
        p.setParentItem(self)
        self._input_ports.append(p)
        self._place_input_ports()
        return p

    def set_output_port(self) -> _Port:
        p = _Port(self, is_input=False)
        p.setParentItem(self)
        p.setPos(_NODE_W, self.rect().height() / 2)
        self._output_port = p
        return p

    @property
    def output_port(self):
        return self._output_port

    @property
    def input_ports(self):
        return self._input_ports

    # ── drawing ──────────────────────────────────────────────────────────

    def paint(self, painter: QPainter, option, widget=None):
        r = self.rect()
        # body
        painter.setBrush(QBrush(QColor(42, 42, 48)))
        sel_pen = QPen(QColor(0, 188, 212), 2) if self.isSelected() else QPen(QColor(70, 70, 75), 1)
        painter.setPen(sel_pen)
        painter.drawRoundedRect(r, 7, 7)
        # header fill clipped to top rounded corners
        painter.save()
        painter.setClipRect(QRectF(0, 0, _NODE_W, _NODE_HDR_H))
        painter.setBrush(QBrush(self._hdr_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(r, 7, 7)
        painter.restore()
        # title
        painter.setPen(Qt.GlobalColor.white)
        painter.setFont(QFont("sans-serif", 8, QFont.Weight.Bold))
        painter.drawText(
            QRectF(10, 0, _NODE_W - 20, _NODE_HDR_H),
            Qt.AlignmentFlag.AlignVCenter, self._title,
        )
        # body text
        painter.setFont(QFont("sans-serif", 7))
        painter.setPen(QColor(190, 190, 190))
        painter.drawText(
            QRectF(10, _NODE_HDR_H + 4, _NODE_W - 20, self.rect().height() - _NODE_HDR_H - 8),
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
            | Qt.TextFlag.TextWordWrap,
            self._body_text(),
        )

    def _body_text(self) -> str:
        return ""

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemScenePositionHasChanged:
            for p in self._input_ports:
                p.update_edges()
            if self._output_port:
                self._output_port.update_edges()
        return super().itemChange(change, value)


class _SourceNode(_BaseNode):
    """Image-source node — no inputs, one output. Shows an inline thumbnail."""

    _HDR = QColor(30, 90, 140)

    def __init__(self, path: str, x: float = 0, y: float = 0):
        # Taller rect to accommodate thumbnail
        super().__init__(os.path.basename(path), self._HDR, x, y)
        self.path = path
        self.setRect(0, 0, _NODE_W, _NODE_HDR_H + _THUMB_H)
        self._thumb: Optional[QPixmap] = self._load_thumb(path)
        self.set_output_port()  # repositioned after setRect

    @staticmethod
    def _load_thumb(path: str) -> Optional[QPixmap]:
        """Load a downscaled thumbnail efficiently via QImageReader."""
        reader = QImageReader(path)
        if not reader.canRead():
            return None
        orig = reader.size()
        if orig.isValid() and orig.width() > 0:
            tw = _NODE_W - 4
            th = _THUMB_H - 4
            scale = min(tw / orig.width(), th / orig.height())
            reader.setScaledSize(
                QSize(max(1, int(orig.width() * scale)),
                      max(1, int(orig.height() * scale)))
            )
        qi = reader.read()
        return QPixmap.fromImage(qi) if not qi.isNull() else None

    def paint(self, painter: QPainter, option, widget=None):
        # Draw base (header + border)
        super().paint(painter, option, widget)
        # Draw thumbnail centred in body area
        if self._thumb:
            px = self._thumb
            x = int((_NODE_W - px.width()) / 2)
            y = _NODE_HDR_H + int((_THUMB_H - px.height()) / 2)
            painter.drawPixmap(x, y, px)
        else:
            # Fallback: dim placeholder
            painter.setPen(QColor(100, 100, 100))
            painter.setFont(QFont("sans-serif", 8))
            painter.drawText(
                QRectF(0, _NODE_HDR_H, _NODE_W, _THUMB_H),
                Qt.AlignmentFlag.AlignCenter,
                "(no preview)",
            )

    def _body_text(self) -> str:
        return ""   # thumbnail replaces text


class _StitchOpNode(_BaseNode):
    """Stitch-operation node — N inputs, one output."""

    _HDR = QColor(90, 50, 130)

    def __init__(self, name: str, output_path: str = "", x: float = 0, y: float = 0):
        super().__init__(f"⊞ {name}", self._HDR, x, y)
        self.step_name = name
        self.output_path = output_path
        self.add_input_port()
        self.add_input_port()
        self.set_output_port()

    def grow_input(self):
        self.add_input_port()
        new_h = _NODE_HDR_H + _NODE_BODY_H + (len(self._input_ports) - 2) * 22
        self.prepareGeometryChange()
        self.setRect(0, 0, _NODE_W, new_h)
        self._place_input_ports()
        if self._output_port:
            self._output_port.setPos(_NODE_W, new_h / 2)
        self.update()

    def _body_text(self) -> str:
        n_conn = sum(1 for p in self._input_ports if p.edges)
        return f"Inputs connected: {n_conn}/{len(self._input_ports)}"


class _NodeScene(QGraphicsScene):
    """Manages source nodes, stitch-op nodes, and their connections."""

    plan_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._drag_edge: Optional[_GraphEdge] = None
        self._drag_src:  Optional[_Port]      = None

    # ── node factory ─────────────────────────────────────────────────────

    def add_source(self, path: str, pos: Optional[QPointF] = None) -> _SourceNode:
        if pos is None:
            x, y = self._next_pos(col=0)
        else:
            x, y = pos.x(), pos.y()
        node = _SourceNode(path, x, y)
        self.addItem(node)
        self.plan_changed.emit()
        return node

    def add_stitch_op(self, name: str = "", output: str = "") -> _StitchOpNode:
        x, y = self._next_pos(col=1)
        n = sum(1 for i in self.items() if isinstance(i, _StitchOpNode))
        node = _StitchOpNode(name or f"Op {n + 1}", output, x, y)
        self.addItem(node)
        self.plan_changed.emit()
        return node

    def remove_selected(self):
        for item in list(self.selectedItems()):
            if isinstance(item, _GraphEdge):
                item.remove_self()
            elif isinstance(item, _BaseNode):
                for p in item.input_ports + ([item.output_port] if item.output_port else []):
                    for e in list(p.edges):
                        e.remove_self()
                self.removeItem(item)
        self.plan_changed.emit()

    def clear_graph(self):
        self.clear()
        self._drag_edge = None
        self._drag_src  = None
        self.plan_changed.emit()

    def _next_pos(self, col: int = 0) -> Tuple[float, float]:
        nodes = [i for i in self.items() if isinstance(i, _BaseNode)]
        col_nodes = [n for n in nodes if (n.scenePos().x() > 260) == (col > 0)]
        y = max((n.scenePos().y() for n in col_nodes), default=30) + _NODE_HDR_H + _NODE_BODY_H + 20
        return (30.0 if col == 0 else 300.0, y if col_nodes else 30.0)

    # ── port-drag connection ──────────────────────────────────────────────

    def _port_at(self, pos) -> Optional[_Port]:
        for item in self.items(pos):
            if isinstance(item, _Port):
                return item
        return None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            port = self._port_at(event.scenePos())
            if port:
                if not port.is_input:
                    # Start new connection
                    self._drag_src  = port
                    self._drag_edge = _GraphEdge(port)
                    self.addItem(self._drag_edge)
                    return
                elif port.is_input and port.edges:
                    # Detach existing connection
                    edge = port.edges.pop()
                    self._drag_src = edge.src
                    self._drag_edge = edge
                    edge.dst = None
                    edge.update_path(event.scenePos())
                    self.plan_changed.emit()
                    return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_edge:
            self._drag_edge.update_path(event.scenePos())
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._drag_edge and self._drag_src:
            dst = self._port_at(event.scenePos())
            if (dst and dst.is_input
                    and dst.node is not self._drag_src.node
                    and not dst.edges):
                self._drag_edge.dst = dst
                self._drag_src.edges.append(self._drag_edge)
                dst.edges.append(self._drag_edge)
                self._drag_edge.update_path()
                self.plan_changed.emit()
            else:
                # Remove from source port list if it was already registered
                if self._drag_edge in self._drag_src.edges:
                    self._drag_src.edges.remove(self._drag_edge)
                self.removeItem(self._drag_edge)
                self.plan_changed.emit()
            self._drag_edge = None
            self._drag_src  = None
            return
        super().mouseReleaseEvent(event)

    # ── plan extraction ───────────────────────────────────────────────────

    def get_plan(self) -> List[Dict]:
        ops: List[_StitchOpNode] = [
            i for i in self.items() if isinstance(i, _StitchOpNode)
        ]
        if not ops:
            return []

        id_map: Dict[int, str] = {id(op): f"op_{k}" for k, op in enumerate(ops)}

        def _inputs_for(op: _StitchOpNode) -> List[str]:
            res = []
            for port in op.input_ports:
                for edge in port.edges:
                    src = edge.src.node
                    if isinstance(src, _SourceNode):
                        res.append(src.path)
                    elif isinstance(src, _StitchOpNode):
                        res.append(id_map[id(src)])
            return res

        # Kahn topological sort
        in_deg: Dict[int, int] = {id(op): 0 for op in ops}
        deps:   Dict[int, List[_StitchOpNode]] = {id(op): [] for op in ops}
        for op in ops:
            for inp in _inputs_for(op):
                for dep in ops:
                    if id_map[id(dep)] == inp:
                        in_deg[id(op)] += 1
                        deps[id(dep)].append(op)

        queue   = [op for op in ops if in_deg[id(op)] == 0]
        ordered: List[_StitchOpNode] = []
        while queue:
            cur = queue.pop(0)
            ordered.append(cur)
            for dep in deps[id(cur)]:
                in_deg[id(dep)] -= 1
                if in_deg[id(dep)] == 0:
                    queue.append(dep)

        return [
            {
                "id":     id_map[id(op)],
                "name":   op.step_name,
                "inputs": _inputs_for(op),
                "output": op.output_path,
            }
            for op in ordered
        ]


class _NodeView(QGraphicsView):
    """Zoomable / pannable view for the node graph canvas."""

    def __init__(self, scene: _NodeScene):
        super().__init__(scene)
        self.setDragMode(QGraphicsView.DragMode.NoDrag) # Managed in events
        self.setAcceptDrops(True)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("background:#1a1a1e; border:none;")

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if not urls: return
        scene_pos = self.mapToScene(event.position().toPoint())
        added = False
        for i, url in enumerate(urls):
            fpath = url.toLocalFile()
            if not fpath: continue
            ext = os.path.splitext(fpath)[1].lower()
            if ext in [".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"]:
                # Offset multiple images slightly so they don't stack perfectly
                drop_pos = scene_pos + QPointF(i*20, i*20)
                self.scene().add_source(fpath, pos=drop_pos)
                added = True
        if added:
            event.acceptProposedAction()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            item = self.itemAt(event.position().toPoint())
            if not item:
                self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            else:
                self.setDragMode(QGraphicsView.DragMode.NoDrag)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)

    def wheelEvent(self, event: QWheelEvent):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            f = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
            self.scale(f, f)
        else:
            super().wheelEvent(event)


# ---------------------------------------------------------------------------
# _AnchorHandle — draggable keypoint marker
# ---------------------------------------------------------------------------


class _AnchorHandle(QGraphicsEllipseItem):
    def __init__(self, cx: float, cy: float, color: QColor, moved_cb,
                 radius: int = _ANCHOR_RADIUS):
        r = radius
        super().__init__(-r, -r, r * 2, r * 2)
        self._moved_cb = moved_cb
        self.setPos(cx, cy)
        self.setBrush(QBrush(color))
        pen = QPen(Qt.GlobalColor.white)
        pen.setWidth(1)
        self.setPen(pen)
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsScenePositionChanges
            | QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations
        )
        self.setZValue(10)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemScenePositionHasChanged:
            self._moved_cb(self, value)
        return super().itemChange(change, value)


# ---------------------------------------------------------------------------
# _MatchScene
# ---------------------------------------------------------------------------


class _MatchScene(QGraphicsScene):
    affine_updated = Signal(object)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._pix_a: Optional[QGraphicsPixmapItem] = None
        self._pix_b: Optional[QGraphicsPixmapItem] = None
        self._offset_x: float = 0.0
        self._scale_a: float = 1.0
        self._scale_b: float = 1.0
        self._orig_h_a = self._orig_w_a = self._orig_h_b = self._orig_w_b = 0
        self._match_lines: list = []
        self._anchors_a: List[_AnchorHandle] = []
        self._anchors_b: List[_AnchorHandle] = []
        self._affine_overlay: Optional[QGraphicsRectItem] = None
        self._hint_label: Optional[QGraphicsTextItem] = None

        self._debounce = QTimer()
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(80)
        self._debounce.timeout.connect(self._recompute_affine)

    def load_pair(self, img_a, img_b, orig_h_a, orig_w_a, orig_h_b, orig_w_b):
        self.clear()
        self._match_lines = []
        self._anchors_a = []
        self._anchors_b = []
        self._affine_overlay = None

        pix_a = _bgr_to_qpixmap(img_a)
        pix_b = _bgr_to_qpixmap(img_b)
        self._pix_a = self.addPixmap(pix_a)
        self._pix_a.setPos(0, 0)

        gap = 12
        self._offset_x = float(pix_a.width() + gap)
        self._pix_b = self.addPixmap(pix_b)
        self._pix_b.setPos(self._offset_x, 0)

        self._scale_a = pix_a.width() / orig_w_a if orig_w_a else 1.0
        self._scale_b = pix_b.width() / orig_w_b if orig_w_b else 1.0
        self._orig_h_a, self._orig_w_a = orig_h_a, orig_w_a
        self._orig_h_b, self._orig_w_b = orig_h_b, orig_w_b

        self.setSceneRect(
            QRectF(0, 0, self._offset_x + pix_b.width(),
                   max(pix_a.height(), pix_b.height()))
        )
        sep_pen = QPen(QColor(120, 120, 120, 200))
        sep_pen.setWidth(2)
        sep = self.addLine(self._offset_x - gap / 2, 0,
                           self._offset_x - gap / 2,
                           max(pix_a.height(), pix_b.height()), sep_pen)
        sep.setZValue(1)

        lbl = self.addText("Click 'Compute Matches' to show correspondences.")
        lbl.setDefaultTextColor(QColor(180, 180, 180))
        lbl.setFont(QFont("monospace", 10))
        lbl.setPos(10, max(pix_a.height(), pix_b.height()) / 2 - 10)
        lbl.setZValue(5)
        self._hint_label = lbl

    def show_matches(self, pts1, pts2, conf):
        if self._hint_label is not None:
            self.removeItem(self._hint_label)
            self._hint_label = None

        for item in self._match_lines + self._anchors_a + self._anchors_b:
            self.removeItem(item)
        self._match_lines = []
        self._anchors_a = []
        self._anchors_b = []

        if len(pts1) > _MAX_DISPLAYED_MATCHES:
            idx = np.argsort(conf)[::-1][:_MAX_DISPLAYED_MATCHES]
            pts1, pts2, conf = pts1[idx], pts2[idx], conf[idx]

        for p1, p2, c in zip(pts1, pts2, conf):
            color = _conf_color(float(c))
            sx_a = float(p1[0]) * self._scale_a
            sy_a = float(p1[1]) * self._scale_a
            sx_b = float(p2[0]) * self._scale_b + self._offset_x
            sy_b = float(p2[1]) * self._scale_b

            line_pen = QPen(color)
            line_pen.setWidthF(1.2)
            line = self.addLine(sx_a, sy_a, sx_b, sy_b, line_pen)
            line.setZValue(3)
            self._match_lines.append(line)

            h_a = _AnchorHandle(sx_a, sy_a, color, self._on_anchor_moved)
            h_b = _AnchorHandle(sx_b, sy_b, color, self._on_anchor_moved)
            self.addItem(h_a)
            self.addItem(h_b)
            self._anchors_a.append(h_a)
            self._anchors_b.append(h_b)

    def show_mask(self, img_a, mask):
        if self._pix_a is None:
            return
        self._pix_a.setPixmap(_mask_to_qpixmap(img_a, mask))

    def _on_anchor_moved(self, handle: _AnchorHandle, _pos):
        idx_a = self._anchors_a.index(handle) if handle in self._anchors_a else -1
        idx_b = self._anchors_b.index(handle) if handle in self._anchors_b else -1
        idx = idx_a if idx_a >= 0 else idx_b
        if 0 <= idx < len(self._match_lines):
            line_item: QGraphicsLineItem = self._match_lines[idx]
            ha = self._anchors_a[idx]
            hb = self._anchors_b[idx]
            line_item.setLine(
                ha.scenePos().x(), ha.scenePos().y(),
                hb.scenePos().x(), hb.scenePos().y(),
            )
        self._debounce.start()

    def _recompute_affine(self):
        if len(self._anchors_a) < 3:
            self.affine_updated.emit(None)
            return
        pts_a = np.array(
            [[h.scenePos().x() / self._scale_a, h.scenePos().y() / self._scale_a]
             for h in self._anchors_a], dtype=np.float32)
        pts_b = np.array(
            [((h.scenePos().x() - self._offset_x) / self._scale_b,
              h.scenePos().y() / self._scale_b)
             for h in self._anchors_b], dtype=np.float32)
        M, _ = cv2.estimateAffinePartial2D(pts_a, pts_b, method=cv2.RANSAC,
                                           ransacReprojThreshold=4.0)
        self.affine_updated.emit(M)

    def get_affine_from_anchors(self) -> Optional[np.ndarray]:
        if len(self._anchors_a) < 3:
            return None
        pts_a = np.array(
            [[h.scenePos().x() / self._scale_a, h.scenePos().y() / self._scale_a]
             for h in self._anchors_a], dtype=np.float32)
        pts_b = np.array(
            [((h.scenePos().x() - self._offset_x) / self._scale_b,
              h.scenePos().y() / self._scale_b)
             for h in self._anchors_b], dtype=np.float32)
        M, _ = cv2.estimateAffinePartial2D(pts_a, pts_b, method=cv2.RANSAC,
                                           ransacReprojThreshold=4.0)
        return M


# ---------------------------------------------------------------------------
# _MatchView
# ---------------------------------------------------------------------------


class _MatchView(QGraphicsView):
    def __init__(self, scene: _MatchScene):
        super().__init__(scene)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        self.setMinimumSize(480, 300)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def wheelEvent(self, event: QWheelEvent):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
            self.scale(factor, factor)
        else:
            super().wheelEvent(event)

    def fit(self):
        self.fitInView(self.scene().sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)


# ---------------------------------------------------------------------------
# EditTab
# ---------------------------------------------------------------------------

# Wallpaper output size presets
_SIZE_PRESETS = [
    ("Custom",                   None),
    ("Desktop  1920 × 1080",     (1920, 1080)),
    ("Desktop  2560 × 1440",     (2560, 1440)),
    ("Desktop  3840 × 2160  4K", (3840, 2160)),
    ("Desktop  5120 × 2880  5K", (5120, 2880)),
    ("Desktop  2560 × 1080  UW", (2560, 1080)),
    ("Desktop  3440 × 1440  UW", (3440, 1440)),
    ("Phone    1080 × 1920",     (1080, 1920)),
    ("Phone    1440 × 2560",     (1440, 2560)),
    ("Phone    1284 × 2778  iPhone 14", (1284, 2778)),
    ("Phone    1440 × 3200",     (1440, 3200)),
    ("Square   1080 × 1080",     (1080, 1080)),
    ("Square   2048 × 2048",     (2048, 2048)),
]

_CROP_PRESETS = [
    ("No crop",             None),
    ("16 : 9   Desktop",    (16, 9)),
    ("21 : 9   Ultrawide",  (21, 9)),
    ("9 : 16   Portrait",   (9, 16)),
    ("4 : 3   Classic",     (4, 3)),
    ("3 : 2",               (3, 2)),
    ("1 : 1   Square",      (1, 1)),
]


# ---------------------------------------------------------------------------
# Statistics worker — runs off the main thread
# ---------------------------------------------------------------------------

class _StatsSignals(QObject):
    individual_done = Signal(list)   # List[dict] — one dict per image
    pairwise_done   = Signal(list)   # List[dict] — one dict per pair
    progress        = Signal(int)    # 0-100
    error           = Signal(str)


class StatsWorker(QRunnable):
    """
    Computes per-image and pairwise statistics for a list of image paths.

    Per-image metrics
    -----------------
    resolution, aspect_ratio, brightness, contrast, sharpness, saturation,
    dominant_hue, noise_estimate, file_size_kb

    Pairwise metrics (consecutive pairs + all pairs if ≤ 12 images)
    ---------------------------------------------------------------
    hist_correlation, ssim, orb_inliers, mean_diff
    """

    def __init__(self, paths: List[str], knn_window: int = 20):
        super().__init__()
        self.setAutoDelete(True)
        self._paths = list(paths)
        self._knn_window = max(1, knn_window)
        self.signals = _StatsSignals()
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            self._compute()
        except Exception as exc:
            self.signals.error.emit(str(exc))

    # ------------------------------------------------------------------
    def _compute(self):
        paths = self._paths
        n = len(paths)
        if n == 0:
            self.signals.individual_done.emit([])
            self.signals.pairwise_done.emit([])
            return

        individual: List[dict] = []
        knn = self._knn_window
        # For large sets: consecutive pairs + K-window extended pairs
        # For small sets (≤ 12): all pairs (already covers everything)
        if n <= 12:
            _n_pw_est = n * (n - 1) // 2
        else:
            _n_pw_est = (n - 1) + (n - 1) * min(knn - 1, n - 2)
        total_steps = n + max(_n_pw_est, 1)
        done = 0

        # ── Per-image ──────────────────────────────────────────────────
        bgr_cache: Dict[str, np.ndarray] = {}

        for path in paths:
            if self._cancelled:
                return
            row = self._image_stats(path)
            individual.append(row)
            bgr = cv2.imread(path)
            if bgr is not None:
                # Cache a small version for pairwise (saves memory)
                h, w = bgr.shape[:2]
                scale = min(1.0, 512 / max(h, w, 1))
                if scale < 1.0:
                    bgr = cv2.resize(bgr, (int(w * scale), int(h * scale)),
                                     interpolation=cv2.INTER_AREA)
            bgr_cache[path] = bgr
            done += 1
            self.signals.progress.emit(int(done / total_steps * 100))

        self.signals.individual_done.emit(individual)

        # ── Pairwise ───────────────────────────────────────────────────
        # For ≤ 12 images: all pairs (covers every combination).
        # For larger sets: consecutive pairs PLUS an extended K-window so
        # that periodically-repeating poses (common in anime cycles) are
        # captured.  Each row carries a "consecutive" flag so the
        # recommendations section can distinguish direct neighbours from
        # extended-window candidates.
        if n <= 12:
            pairs = [(i, j, True) for i in range(n) for j in range(i + 1, n)]
        else:
            seen: set = set()
            pairs = []
            for i in range(n - 1):
                if (i, i + 1) not in seen:
                    pairs.append((i, i + 1, True))
                    seen.add((i, i + 1))
            for i in range(n):
                for step in range(2, knn + 1):
                    j = i + step
                    if j < n and (i, j) not in seen:
                        pairs.append((i, j, False))
                        seen.add((i, j))

        pairwise: List[dict] = []
        total_steps_pw = max(len(pairs), 1)
        done_pw = 0

        orb = cv2.ORB_create(nfeatures=500)

        for i, j, is_consec in pairs:
            if self._cancelled:
                return
            pa, pb = paths[i], paths[j]
            a = bgr_cache.get(pa)
            b = bgr_cache.get(pb)
            row = self._pair_stats(pa, pb, a, b, i, j, orb)
            row["consecutive"] = is_consec
            pairwise.append(row)
            done_pw += 1
            # Map pairwise progress onto second half
            pct = int((n + done_pw / total_steps_pw * (n - 1)) / total_steps * 100)
            self.signals.progress.emit(min(pct, 99))

        self.signals.pairwise_done.emit(pairwise)
        self.signals.progress.emit(100)

    # ------------------------------------------------------------------
    @staticmethod
    def _image_stats(path: str) -> dict:
        import os as _os
        row: dict = {"path": path, "name": _os.path.basename(path)}

        try:
            file_size_kb = round(_os.path.getsize(path) / 1024, 1)
        except OSError:
            file_size_kb = 0.0
        row["file_size_kb"] = file_size_kb

        bgr = cv2.imread(path)
        if bgr is None:
            row.update({"width": 0, "height": 0, "aspect_ratio": "—",
                        "brightness": 0.0, "contrast": 0.0, "sharpness": 0.0,
                        "saturation": 0.0, "dominant_hue": 0, "noise": 0.0})
            return row

        h, w = bgr.shape[:2]
        row["width"]  = w
        row["height"] = h
        from math import gcd
        g = gcd(w, h)
        row["aspect_ratio"] = f"{w // g}:{h // g}"

        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
        row["brightness"] = round(float(gray.mean()), 2)
        row["contrast"]   = round(float(gray.std()), 2)

        lap = cv2.Laplacian(gray, cv2.CV_32F)
        row["sharpness"] = round(float(lap.var()), 2)

        # Noise estimate: median absolute deviation of Laplacian
        lap_abs = np.abs(lap - np.median(lap))
        row["noise"] = round(float(np.median(lap_abs)), 2)

        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
        row["saturation"] = round(float(hsv[:, :, 1].mean()), 2)

        # Dominant hue: peak of hue histogram (ignore low-saturation pixels)
        sat_mask = (hsv[:, :, 1] > 30).astype(np.uint8)
        if sat_mask.sum() > 100:
            hue_hist = cv2.calcHist([hsv], [0], sat_mask, [180], [0, 180])
            row["dominant_hue"] = int(np.argmax(hue_hist))
        else:
            row["dominant_hue"] = -1  # achromatic

        return row

    # ------------------------------------------------------------------
    @staticmethod
    def _pair_stats(pa: str, pb: str, a, b, i: int, j: int, orb) -> dict:
        row = {"idx_a": i, "idx_b": j,
               "path_a": pa, "path_b": pb,
               "name_a": os.path.basename(pa),
               "name_b": os.path.basename(pb),
               "hist_corr": 0.0, "ssim": 0.0, "orb_inliers": 0,
               "mean_diff": 0.0}

        if a is None or b is None:
            return row

        # Resize to same shape for pixel-level metrics
        h = min(a.shape[0], b.shape[0])
        w = min(a.shape[1], b.shape[1])
        ar = cv2.resize(a, (w, h), interpolation=cv2.INTER_AREA)
        br = cv2.resize(b, (w, h), interpolation=cv2.INTER_AREA)

        # Histogram correlation (per channel, averaged)
        corrs = []
        for c in range(3):
            ha = cv2.calcHist([ar], [c], None, [64], [0, 256])
            hb = cv2.calcHist([br], [c], None, [64], [0, 256])
            corrs.append(float(cv2.compareHist(ha, hb, cv2.HISTCMP_CORREL)))
        row["hist_corr"] = round(float(np.mean(corrs)), 4)

        # SSIM (grayscale, simplified)
        ga = cv2.cvtColor(ar, cv2.COLOR_BGR2GRAY).astype(np.float32)
        gb = cv2.cvtColor(br, cv2.COLOR_BGR2GRAY).astype(np.float32)
        C1, C2 = 6.5025, 58.5225
        mu_a = cv2.GaussianBlur(ga, (11, 11), 1.5)
        mu_b = cv2.GaussianBlur(gb, (11, 11), 1.5)
        mu_a2, mu_b2, mu_ab = mu_a ** 2, mu_b ** 2, mu_a * mu_b
        sig_a2 = cv2.GaussianBlur(ga * ga, (11, 11), 1.5) - mu_a2
        sig_b2 = cv2.GaussianBlur(gb * gb, (11, 11), 1.5) - mu_b2
        sig_ab = cv2.GaussianBlur(ga * gb, (11, 11), 1.5) - mu_ab
        ssim_map = ((2 * mu_ab + C1) * (2 * sig_ab + C2)) / \
                   ((mu_a2 + mu_b2 + C1) * (sig_a2 + sig_b2 + C2))
        row["ssim"] = round(float(ssim_map.mean()), 4)

        # Mean pixel difference
        row["mean_diff"] = round(float(np.abs(ar.astype(np.float32) - br.astype(np.float32)).mean()), 2)

        # ORB feature matching inliers
        try:
            kp_a, des_a = orb.detectAndCompute(cv2.cvtColor(ar, cv2.COLOR_BGR2GRAY), None)
            kp_b, des_b = orb.detectAndCompute(cv2.cvtColor(br, cv2.COLOR_BGR2GRAY), None)
            if des_a is not None and des_b is not None and len(kp_a) >= 4 and len(kp_b) >= 4:
                bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
                matches = bf.knnMatch(des_a, des_b, k=2)
                good = [m for m, n in matches if m.distance < 0.75 * n.distance]
                if len(good) >= 4:
                    src_pts = np.float32([kp_a[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
                    dst_pts = np.float32([kp_b[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
                    _, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
                    row["orb_inliers"] = int(mask.sum()) if mask is not None else len(good)
                else:
                    row["orb_inliers"] = len(good)
        except Exception:
            pass

        return row


# ---------------------------------------------------------------------------
# Animation cluster worker — runs off the main thread
# ---------------------------------------------------------------------------

_ANIM_CLUSTER_COLORS = [
    ("#4CAF50", "#1b3a1f"),
    ("#FF9800", "#3a2000"),
    ("#2196F3", "#001a3a"),
    ("#f44336", "#3a1010"),
    ("#9C27B0", "#2a003a"),
    ("#00BCD4", "#003a3a"),
    ("#FFEB3B", "#3a3600"),
    ("#FF5722", "#3a1a00"),
]


class _AnimClusterSignals(QObject):
    finished = Signal(list)   # List[dict]: path, cluster, cluster_name, is_animated
    progress = Signal(int)    # 0-100
    error    = Signal(str)


class AnimClusterWorker(QRunnable):
    """
    Groups a list of image paths into animation phases using per-pixel temporal
    FFT analysis (replicating AnimeStitchPipeline._cluster_animation_phases).

    Each result dict:
        path         : str   — absolute image path
        cluster      : int   — 0-based phase index  (-1 = unassigned)
        cluster_name : str   — human-readable label
        is_animated  : bool  — True if temporal animation was detected
        ac_ratio     : float — mean AC/(DC+AC) ratio across the frame set
    """

    def __init__(
        self,
        paths: List[str],
        ac_threshold: float = 0.25,
        min_anim_pixels: int = 500,
    ):
        super().__init__()
        self.setAutoDelete(True)
        self._paths            = list(paths)
        self._ac_threshold     = ac_threshold
        self._min_anim_pixels  = min_anim_pixels
        self.signals           = _AnimClusterSignals()
        self._cancelled        = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            try:
                from sklearn.cluster import KMeans  # noqa: F401
            except ImportError:
                self.signals.error.emit(
                    "scikit-learn is not installed.\n\n"
                    "Run:  pip install scikit-learn\n\n"
                    "Restart the application after installing."
                )
                return
            self._compute()
        except Exception as exc:
            self.signals.error.emit(str(exc))

    def _compute(self):
        from sklearn.cluster import KMeans

        paths = self._paths
        N = len(paths)
        if N == 0:
            self.signals.finished.emit([])
            return

        # ── Load frames, normalise to first frame's size ─────────────────
        frames: List[np.ndarray] = []
        H = W = 0
        for i, p in enumerate(paths):
            if self._cancelled:
                return
            img = cv2.imread(p)
            if img is None:
                img = np.zeros((100, 100, 3), np.uint8)
            if i == 0:
                H, W = img.shape[:2]
            elif img.shape[:2] != (H, W):
                img = cv2.resize(img, (W, H), interpolation=cv2.INTER_AREA)
            frames.append(img)
            self.signals.progress.emit(int((i + 1) / N * 35))

        if N < 4:
            rows = [
                {"path": p, "cluster": 0,
                 "cluster_name": "Static (need ≥ 4 frames)",
                 "is_animated": False, "ac_ratio": 0.0}
                for p in paths
            ]
            self.signals.finished.emit(rows)
            return

        # ── Downsample and build small greyscale stack ────────────────────
        target_w = 320
        scale = target_w / max(W, 1)
        th = max(1, int(H * scale))
        tw = target_w

        small_stack: List[np.ndarray] = []
        for i, frame in enumerate(frames):
            if self._cancelled:
                return
            M_small = np.array([[scale, 0.0, 0.0], [0.0, scale, 0.0]], np.float32)
            warped = cv2.warpAffine(frame, M_small, (tw, th), flags=cv2.INTER_AREA)
            gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
            small_stack.append(gray)
            self.signals.progress.emit(35 + int((i + 1) / N * 25))

        stack_arr = np.stack(small_stack, axis=0)  # (N, th, tw)

        # ── Temporal FFT: detect animated pixels ─────────────────────────
        F = np.fft.rfft(stack_arr, axis=0)
        power = np.abs(F) ** 2
        dc_power = power[0]
        ac_power = power[1:].sum(axis=0)
        ratio    = ac_power / (dc_power + ac_power + 1e-8)
        mean_ratio = float(ratio.mean())

        anim_mask = (ratio > self._ac_threshold).astype(np.uint8) * 255
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        anim_mask = cv2.morphologyEx(anim_mask, cv2.MORPH_OPEN,  kernel)
        anim_mask = cv2.morphologyEx(anim_mask, cv2.MORPH_CLOSE, kernel)

        n_anim_px = int(anim_mask.sum()) // 255
        if n_anim_px < self._min_anim_pixels:
            rows = [
                {"path": p, "cluster": 0,
                 "cluster_name": "Static (no animation detected)",
                 "is_animated": False, "ac_ratio": mean_ratio}
                for p in paths
            ]
            self.signals.finished.emit(rows)
            return

        # ── Cluster frames by Canny edge signature on anim pixels ─────────
        anim_ys, anim_xs = np.where(anim_mask > 0)
        sigs: List[np.ndarray] = []
        for gray in small_stack:
            edges = cv2.Canny((gray * 255).astype(np.uint8), 50, 150)
            sigs.append(edges[anim_ys, anim_xs].astype(np.float32))
        sig_matrix = np.stack(sigs, axis=0)  # (N, K)

        n_clusters = max(2, min(8, N // 2))
        km = KMeans(n_clusters=n_clusters, n_init=5, random_state=0)
        labels = km.fit_predict(sig_matrix)

        self.signals.progress.emit(95)

        rows = []
        for i, p in enumerate(paths):
            c = int(labels[i])
            rows.append({
                "path":         p,
                "cluster":      c,
                "cluster_name": f"Phase {c + 1}",
                "is_animated":  True,
                "ac_ratio":     mean_ratio,
            })
        rows.sort(key=lambda r: (r["cluster"], os.path.basename(r["path"])))

        self.signals.progress.emit(100)
        self.signals.finished.emit(rows)


# ---------------------------------------------------------------------------
# Sequence-builder worker
# ---------------------------------------------------------------------------


class _SeqBuilderSignals(QObject):
    progress   = Signal(int)          # 0-100
    result     = Signal(list)         # List[dict]: ordered chain items
    error      = Signal(str)


class SequenceBuilderWorker(QRunnable):
    """
    Given an anchor image and a pool of candidates, builds the longest
    sequential stitching chain greedily.

    Scoring — stitchability, not similarity
    ----------------------------------------
    Two frames are good for stitching when they share overlapping content AND
    the camera has panned enough to reveal new content.  The old approach
    (SSIM + hist_corr + ORB inliers) measured raw similarity, so near-identical
    consecutive frames scored highest — the opposite of what is needed.

    This version scores each candidate by:
      1. ORB feature matching + RANSAC homography against the current tail.
      2. Extracting the translation (dx, dy) from the homography.
      3. Rejecting near-duplicates  : |translation| < min_pan  (same view)
      4. Rejecting non-overlapping  : |translation| > max_pan  (no shared content)
      5. Fitness = inlier_ratio × displacement_quality(ratio)
         where displacement_quality peaks at ~30% of frame diagonal and falls
         off toward 0 at the min/max boundaries.

    Sharpness filter
    ----------------
    Each candidate is compared against the anchor's Laplacian variance.
    Candidates whose sharpness is below `blur_threshold × anchor_sharpness`
    are excluded before the chain search begins.
    """

    def __init__(
        self,
        anchor: str,
        candidates: List[str],
        min_score: float = 0.25,
        blur_threshold: float = 0.5,
        min_pan_ratio: float = 0.03,
        max_pan_ratio: float = 0.85,
    ):
        super().__init__()
        self.setAutoDelete(True)
        self._anchor         = anchor
        self._candidates     = [p for p in candidates if p != anchor]
        self._min_score      = min_score
        self._blur_threshold = blur_threshold   # sharpness relative to anchor
        self._min_pan        = min_pan_ratio    # min translation as fraction of diagonal
        self._max_pan        = max_pan_ratio    # max translation as fraction of diagonal
        self.signals         = _SeqBuilderSignals()
        self._cancelled      = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            self._build()
        except Exception as exc:
            self.signals.error.emit(str(exc))

    # ------------------------------------------------------------------
    def _build(self):
        all_paths = [self._anchor] + self._candidates
        n = len(all_paths)
        if n < 2:
            self.signals.result.emit([{"path": self._anchor,
                                        "name": os.path.basename(self._anchor),
                                        "score_to_prev": None}])
            return

        orb = cv2.ORB_create(nfeatures=800)
        bf  = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)

        # ── Cache thumbnails + precompute features + sharpness ────────
        cache:     Dict[str, Optional[np.ndarray]] = {}
        feats:     Dict[str, tuple]                = {}  # (kp, des)
        sharpness: Dict[str, float]                = {}

        for idx, p in enumerate(all_paths):
            if self._cancelled:
                return
            bgr = cv2.imread(p)
            if bgr is not None:
                h, w = bgr.shape[:2]
                scale = min(1.0, 512 / max(h, w, 1))
                if scale < 1.0:
                    bgr = cv2.resize(bgr, (int(w * scale), int(h * scale)),
                                     interpolation=cv2.INTER_AREA)
                gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
                lap  = cv2.Laplacian(gray.astype(np.float32), cv2.CV_32F)
                sharpness[p] = float(lap.var())
                kp, des = orb.detectAndCompute(gray, None)
                feats[p] = (kp, des)
            else:
                sharpness[p] = 0.0
                feats[p] = ([], None)
            cache[p] = bgr
            self.signals.progress.emit(int((idx + 1) / n * 45))

        anchor_sharp = max(sharpness.get(self._anchor, 1.0), 1.0)
        sharp_thresh = anchor_sharp * self._blur_threshold

        # ── Pre-filter: remove blurry candidates ─────────────────────
        valid_candidates = [
            p for p in self._candidates
            if sharpness.get(p, 0.0) >= sharp_thresh
        ]
        n_rejected = len(self._candidates) - len(valid_candidates)
        if n_rejected:
            print(f"[SeqBuilder] Rejected {n_rejected} blurry candidates "
                  f"(sharpness < {sharp_thresh:.1f}).")

        # ── Stitch-fitness scorer ─────────────────────────────────────
        fitness_cache: Dict[tuple, tuple] = {}  # key → (score, dx, dy)

        def stitch_fitness(ref_p: str, cand_p: str) -> tuple:
            """Returns (score, dx, dy).  score=0 means not usable."""
            key = (min(ref_p, cand_p), max(ref_p, cand_p))
            if key in fitness_cache:
                return fitness_cache[key]

            kp_r, des_r = feats.get(ref_p,  ([], None))
            kp_c, des_c = feats.get(cand_p, ([], None))
            zero = (0.0, 0.0, 0.0)
            if des_r is None or des_c is None:
                fitness_cache[key] = zero
                return zero
            if len(kp_r) < 6 or len(kp_c) < 6:
                fitness_cache[key] = zero
                return zero

            try:
                matches = bf.knnMatch(des_r, des_c, k=2)
            except Exception:
                fitness_cache[key] = zero
                return zero

            good = [m for m, n2 in matches
                    if len((m, n2)) == 2 and m.distance < 0.75 * n2.distance]
            if len(good) < 8:
                fitness_cache[key] = zero
                return zero

            src_pts = np.float32([kp_r[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
            dst_pts = np.float32([kp_c[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
            M, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
            if M is None or mask is None:
                fitness_cache[key] = zero
                return zero

            inliers = int(mask.sum())
            if inliers < 8:
                fitness_cache[key] = zero
                return zero

            dx, dy = float(M[0, 2]), float(M[1, 2])

            ref_img = cache.get(ref_p)
            if ref_img is None:
                fitness_cache[key] = zero
                return zero
            fh, fw = ref_img.shape[:2]
            diag = float(np.sqrt(fw ** 2 + fh ** 2))
            dist  = float(np.sqrt(dx ** 2 + dy ** 2))
            ratio = dist / diag

            # Reject near-duplicates and non-overlapping frames
            if ratio < self._min_pan or ratio > self._max_pan:
                fitness_cache[key] = zero
                return zero

            # Displacement quality: triangular, peaks at 30% of diagonal
            peak = 0.30
            if ratio <= peak:
                disp_q = ratio / peak
            else:
                disp_q = (self._max_pan - ratio) / (self._max_pan - peak)
            disp_q = max(0.0, disp_q)

            inlier_ratio = inliers / max(len(good), 1)
            score = round(inlier_ratio * disp_q, 4)

            result = (score, dx, dy)
            fitness_cache[key] = result
            return result

        # ── Greedy chain extension ────────────────────────────────────
        chain:  List[str] = [self._anchor]
        used:   set        = {self._anchor}

        def best_next(ref: str) -> tuple:
            best_p, best_s, best_dx, best_dy = None, -1.0, 0.0, 0.0
            for p in valid_candidates:
                if p in used:
                    continue
                s, dx, dy = stitch_fitness(ref, p)
                if s > best_s:
                    best_s, best_p, best_dx, best_dy = s, p, dx, dy
            return best_p, best_s, best_dx, best_dy

        total = len(valid_candidates)
        done  = 0

        # Extend forward
        while True:
            if self._cancelled:
                return
            nxt, s, _dx, _dy = best_next(chain[-1])
            if nxt is None or s < self._min_score:
                break
            chain.append(nxt)
            used.add(nxt)
            done += 1
            self.signals.progress.emit(45 + int(done / max(total, 1) * 27))

        # Extend backward
        while True:
            if self._cancelled:
                return
            prv, s, _dx, _dy = best_next(chain[0])
            if prv is None or s < self._min_score:
                break
            chain.insert(0, prv)
            used.add(prv)
            done += 1
            self.signals.progress.emit(72 + int(done / max(total, 1) * 27))

        # ── Build result with per-pair fitness scores ────────────────
        result: List[dict] = []
        for idx, p in enumerate(chain):
            if idx == 0:
                s_prev = None
            else:
                s_prev = stitch_fitness(chain[idx - 1], p)[0]
            result.append({"path": p, "name": os.path.basename(p),
                           "score_to_prev": s_prev})

        self.signals.progress.emit(100)
        self.signals.result.emit(result)


# ---------------------------------------------------------------------------


class EditTab(QWidget):
    """
    Full image editing suite focused on anime wallpaper creation.

    Stitch  — intelligent multi-frame panorama stitching with LoFTR matching.
    Adjust  — per-image corrections (tone, color, geometry) before stitching.
    Canvas  — drag-and-drop style layout composer with wallpaper presets.
    """

    def __init__(self):
        super().__init__()

        # ── Stitch state ─────────────────────────────────────────────────
        self._frame_paths: List[str] = []
        self._manual_affines: Dict[Tuple[int, int], np.ndarray] = {}
        self._current_pair: Tuple[int, int] = (0, 1)

        self._stitch_thread: Optional[QThread] = None
        self._stitch_worker: Optional[StitchWorker] = None
        self._match_thread: Optional[QThread] = None
        self._match_worker: Optional[MatchWorker] = None
        self._mask_thread: Optional[QThread] = None
        self._mask_worker: Optional[MaskPreviewWorker] = None

        # ── Adjust state ──────────────────────────────────────────────────
        self._adj_img_path: Optional[str] = None
        self._adj_flip_h: bool = False
        self._adj_flip_v: bool = False
        self._adj_thread: Optional[QThread] = None
        self._adj_worker: Optional[AdjustWorker] = None

        self._adj_debounce = QTimer()
        self._adj_debounce.setSingleShot(True)
        self._adj_debounce.setInterval(220)
        self._adj_debounce.timeout.connect(self._adj_run_preview)

        # ── Canvas state ──────────────────────────────────────────────────
        self._cv_paths: List[str] = []
        self._cv_bg_color: Tuple[int, int, int] = (0, 0, 0)
        self._cv_thread: Optional[QThread] = None
        self._cv_worker: Optional[CanvasWorker] = None

        # ── Graph state ───────────────────────────────────────────────────
        self._graph_thread: Optional[QThread] = None
        self._graph_worker: Optional[GraphStitchWorker] = None
        self._last_selected_op: Optional[_StitchOpNode] = None

        # ── Stats state ───────────────────────────────────────────────────
        self._stats_worker: Optional[StatsWorker] = None
        self._stats_dir_path: str = ""

        # ── Sequence-builder state ────────────────────────────────────────
        self._seq_worker: Optional[SequenceBuilderWorker] = None
        self._seq_anchor_path: str = ""
        self._seq_dir_path: str = ""
        self._seq_chain: List[dict] = []   # current built chain

        # ── Frame-list thumbnail loader ───────────────────────────────────
        self._frame_thumb_hub = _ThumbHub()
        self._frame_thumb_hub.loaded.connect(self._on_frame_thumb_loaded)
        self._frame_item_map: Dict[str, QListWidgetItem] = {}

        # ── Canvas thumbnail loader ───────────────────────────────────────
        self._cv_thumb_hub = _ThumbHub()
        self._cv_thumb_hub.loaded.connect(self._on_cv_thumb_loaded)
        self._cv_item_map: Dict[str, QListWidgetItem] = {}

        # ── Sequence Builder table thumbnail loader ───────────────────────
        self._seq_thumb_hub = _ThumbHub()
        self._seq_thumb_hub.loaded.connect(self._on_seq_table_thumb_loaded)
        self._seq_table_item_map: Dict[str, QTableWidgetItem] = {}

        # ── Statistics thumbnail loaders ──────────────────────────────────
        self._stats_ind_thumb_hub = _ThumbHub()
        self._stats_ind_thumb_hub.loaded.connect(self._on_stats_ind_thumb_loaded)
        self._stats_ind_item_map: Dict[str, QTableWidgetItem] = {}

        self._stats_pw_thumb_hub_a = _ThumbHub()
        self._stats_pw_thumb_hub_a.loaded.connect(self._on_stats_pw_thumb_loaded_a)
        self._stats_pw_item_map_a: Dict[str, QTableWidgetItem] = {}

        self._stats_pw_thumb_hub_b = _ThumbHub()
        self._stats_pw_thumb_hub_b.loaded.connect(self._on_stats_pw_thumb_loaded_b)
        self._stats_pw_item_map_b: Dict[str, QTableWidgetItem] = {}

        # ── Anim Clusters state ───────────────────────────────────────────
        self._anim_cluster_worker: Optional[AnimClusterWorker] = None
        self._anim_cluster_paths: List[str] = []
        self._anim_cluster_dir_path: str = ""
        self._anim_thumb_hub = _ThumbHub()
        self._anim_thumb_hub.loaded.connect(self._on_anim_thumb_loaded)
        self._anim_item_map: Dict[str, QTableWidgetItem] = {}

        self._init_ui()

    # ======================================================================
    # Top-level UI
    # ======================================================================

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._tab_widget = QTabWidget()
        self._tab_widget.addTab(self._build_stitch_panel(),    "Stitch")
        self._tab_widget.addTab(self._build_graph_panel(),    "Graph")
        self._tab_widget.addTab(self._build_adjust_panel(),   "Adjust")
        self._tab_widget.addTab(self._build_canvas_panel(),   "Canvas")
        self._tab_widget.addTab(self._build_stats_panel(),    "Statistics")
        self._tab_widget.addTab(self._build_seq_panel(),      "Sequence Builder")
        self._tab_widget.addTab(self._build_hybrid_panel(),      "Hybrid Stitch")
        self._tab_widget.addTab(self._build_anim_clusters_panel(), "Anim Clusters")

        root.addWidget(self._tab_widget)

    # ======================================================================
    # ── Frame-list thumbnail helpers ──────────────────────────────────────
    # ======================================================================

    def _make_frame_item(self, path: str) -> QListWidgetItem:
        """Create a QListWidgetItem for the stitch frame list and enqueue thumb load."""
        item = QListWidgetItem(os.path.basename(path))
        item.setData(Qt.ItemDataRole.UserRole, path)
        item.setToolTip(path)
        self._frame_item_map[path] = item
        QThreadPool.globalInstance().start(
            _ThumbTask(path, 48, 0, self._frame_thumb_hub)
        )
        return item

    @Slot(str, int, object)
    def _on_frame_thumb_loaded(self, path: str, _generation: int, img: QImage):
        item = self._frame_item_map.get(path)
        if item and not img.isNull():
            item.setIcon(QIcon(QPixmap.fromImage(img)))

    def _make_cv_item(self, path: str, label: str = "") -> QListWidgetItem:
        """Create a QListWidgetItem for the canvas list with async thumbnail."""
        item = QListWidgetItem(label or os.path.basename(path))
        item.setData(Qt.ItemDataRole.UserRole, path)
        item.setToolTip(path)
        self._cv_item_map[path] = item
        QThreadPool.globalInstance().start(
            _ThumbTask(path, 48, 0, self._cv_thumb_hub)
        )
        return item

    @Slot(str, int, object)
    def _on_cv_thumb_loaded(self, path: str, _generation: int, img: QImage):
        item = self._cv_item_map.get(path)
        if item and not img.isNull():
            item.setIcon(QIcon(QPixmap.fromImage(img)))

    @Slot(str, int, object)
    def _on_seq_table_thumb_loaded(self, path: str, _generation: int, img: QImage):
        item = self._seq_table_item_map.get(path)
        if item and not img.isNull():
            item.setIcon(QIcon(QPixmap.fromImage(img)))

    @Slot(str, int, object)
    def _on_stats_ind_thumb_loaded(self, path: str, _generation: int, img: QImage):
        item = self._stats_ind_item_map.get(path)
        if item and not img.isNull():
            item.setIcon(QIcon(QPixmap.fromImage(img)))

    @Slot(str, int, object)
    def _on_stats_pw_thumb_loaded_a(self, path: str, _generation: int, img: QImage):
        item = self._stats_pw_item_map_a.get(path)
        if item and not img.isNull():
            item.setIcon(QIcon(QPixmap.fromImage(img)))

    @Slot(str, int, object)
    def _on_stats_pw_thumb_loaded_b(self, path: str, _generation: int, img: QImage):
        item = self._stats_pw_item_map_b.get(path)
        if item and not img.isNull():
            item.setIcon(QIcon(QPixmap.fromImage(img)))

    # ======================================================================
    # ── SUB-TAB 1: Stitch ─────────────────────────────────────────────────
    # ======================================================================

    def _build_stitch_panel(self) -> QWidget:
        panel = QWidget()
        root = QVBoxLayout(panel)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(4)

        # ── Main splitter (left │ centre │ right) ─────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # ── LEFT: frame list ──────────────────────────────────────────
        left = QWidget()
        left.setMinimumWidth(190)
        left.setMaximumWidth(240)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 4, 0)

        frames_group = QGroupBox("Source Frames")
        frames_group_layout = QVBoxLayout(frames_group)

        self._frame_list = QListWidget()
        self._frame_list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self._frame_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self._frame_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self._frame_list.setIconSize(QSize(48, 48))
        self._frame_list.setToolTip(
            "Drag rows to reorder.\n"
            "Order = stitching sequence (first = leftmost / topmost)."
        )
        self._frame_list.model().rowsMoved.connect(self._on_rows_reordered)
        self._frame_list.currentRowChanged.connect(self._on_frame_selection_changed)
        frames_group_layout.addWidget(self._frame_list)

        self._btn_add    = QPushButton("Add…")
        self._btn_add.setToolTip("Add one or more image files to the stitch queue.")
        self._btn_remove = QPushButton("Remove")
        self._btn_remove.setToolTip("Remove the selected frame.")
        self._btn_up     = QPushButton("↑  Move Up")
        self._btn_down   = QPushButton("↓  Move Down")
        btn_grid = QGridLayout()
        btn_grid.setSpacing(4)
        for b in (self._btn_add, self._btn_remove, self._btn_up, self._btn_down):
            apply_shadow_effect(b, radius=4, y_offset=2)
        btn_grid.addWidget(self._btn_add,    0, 0)
        btn_grid.addWidget(self._btn_remove, 0, 1)
        btn_grid.addWidget(self._btn_up,     1, 0)
        btn_grid.addWidget(self._btn_down,   1, 1)
        
        self._btn_auto_order = QPushButton("⚡ Auto-Order")
        self._btn_auto_order.setToolTip("Find the longest coherent sequence starting from the selected image.")
        self._btn_auto_order.clicked.connect(self._auto_order_sequence)
        apply_shadow_effect(self._btn_auto_order, radius=4, y_offset=2)
        btn_grid.addWidget(self._btn_auto_order, 2, 0, 1, 2)
        frames_group_layout.addLayout(btn_grid)

        self._btn_add.clicked.connect(self._add_frames)
        self._btn_remove.clicked.connect(self._remove_selected_frame)
        self._btn_up.clicked.connect(self._move_frame_up)
        self._btn_down.clicked.connect(self._move_frame_down)

        left_layout.addWidget(frames_group)

        # Pair selector
        pair_group = QGroupBox("Preview Pair")
        pair_layout = QFormLayout(pair_group)

        self._pair_combo = QComboBox()
        self._pair_combo.setToolTip("Select the frame pair to display LoFTR matches for.")
        self._pair_combo.currentIndexChanged.connect(self._on_pair_changed)
        pair_layout.addRow("Pair:", self._pair_combo)

        self._match_count_label = QLabel("—")
        self._match_count_label.setStyleSheet("color: #aaa; font-size: 10px;")
        pair_layout.addRow("Matches:", self._match_count_label)

        self._conf_thresh_spin = QDoubleSpinBox()
        self._conf_thresh_spin.setRange(0.1, 0.99)
        self._conf_thresh_spin.setValue(0.4)
        self._conf_thresh_spin.setDecimals(2)
        self._conf_thresh_spin.setSingleStep(0.05)
        self._conf_thresh_spin.setToolTip("Minimum LoFTR confidence for a displayed match.")
        pair_layout.addRow("Conf. threshold:", self._conf_thresh_spin)

        left_layout.addWidget(pair_group)
        left_layout.addStretch()
        splitter.addWidget(left)

        # ── CENTRE: match preview ─────────────────────────────────────
        centre = QWidget()
        centre_layout = QVBoxLayout(centre)
        centre_layout.setContentsMargins(4, 0, 4, 0)

        self._scene = _MatchScene(self)
        self._scene.affine_updated.connect(self._on_affine_updated)
        self._match_view = _MatchView(self._scene)

        view_toolbar = QHBoxLayout()
        self._btn_compute = QPushButton("Compute Matches")
        self._btn_compute.setToolTip("Run LoFTR on the selected pair.")
        self._btn_compute.setStyleSheet(
            "background:#1976D2; color:white; font-weight:bold; padding:5px 12px;"
        )
        apply_shadow_effect(self._btn_compute, radius=6, y_offset=2)

        self._btn_show_mask = QPushButton("Show Mask")
        self._btn_show_mask.setToolTip("Overlay BiRefNet foreground mask on the left frame.")
        apply_shadow_effect(self._btn_show_mask, radius=6, y_offset=2)

        self._btn_reset_anchors = QPushButton("Reset Anchors")
        self._btn_reset_anchors.setToolTip("Discard dragged-anchor overrides for this pair.")
        apply_shadow_effect(self._btn_reset_anchors, radius=6, y_offset=2)

        self._btn_fit = QPushButton("⊡ Fit")
        self._btn_fit.setMinimumWidth(80)
        self._btn_fit.setToolTip("Fit the view to the scene.")
        apply_shadow_effect(self._btn_fit, radius=4, y_offset=2)

        view_toolbar.addWidget(self._btn_compute)
        view_toolbar.addWidget(self._btn_show_mask)
        view_toolbar.addWidget(self._btn_reset_anchors)
        view_toolbar.addStretch()
        view_toolbar.addWidget(self._btn_fit)

        self._btn_compute.clicked.connect(self._compute_matches)
        self._btn_show_mask.clicked.connect(self._show_mask)
        self._btn_reset_anchors.clicked.connect(self._reset_anchors)
        self._btn_fit.clicked.connect(self._match_view.fit)

        centre_layout.addLayout(view_toolbar)
        centre_layout.addWidget(self._match_view)

        self._affine_label = QLabel("No manual alignment override active.")
        self._affine_label.setStyleSheet("color: #888; font-size: 10px; padding: 2px;")
        centre_layout.addWidget(self._affine_label)

        splitter.addWidget(centre)

        # ── RIGHT: pipeline config ────────────────────────────────────
        right = QWidget()
        right.setMinimumWidth(230)
        right.setMaximumWidth(290)
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setWidget(right)
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(4, 0, 0, 0)

        pipeline_group = QGroupBox("Pipeline Stages")
        pipeline_form = QFormLayout(pipeline_group)

        self._cb_basic = QCheckBox("BaSiC photometric correction")
        self._cb_basic.setChecked(True)
        self._cb_basic.setToolTip("Remove broadcast dimming and vignettes before matching.")
        pipeline_form.addRow(self._cb_basic)

        self._cb_birefnet = QCheckBox("BiRefNet foreground masking")
        self._cb_birefnet.setChecked(True)
        self._cb_birefnet.setToolTip(
            "Detect and exclude anime character regions from LoFTR matching.\n"
            "Strongly recommended — characters move between frames."
        )
        pipeline_form.addRow(self._cb_birefnet)

        self._cb_loftr = QCheckBox("LoFTR dense matching")
        self._cb_loftr.setChecked(True)
        self._cb_loftr.setToolTip(
            "Use LoFTR for subpixel-accurate correspondences.\n"
            "Falls back to template matching if unchecked or unavailable."
        )
        pipeline_form.addRow(self._cb_loftr)

        self._cb_ecc = QCheckBox("ECC sub-pixel refinement")
        self._cb_ecc.setChecked(True)
        self._cb_ecc.setToolTip("Apply ECC after bundle adjustment for sub-pixel accuracy.")
        pipeline_form.addRow(self._cb_ecc)

        self._cb_composite_fg = QCheckBox("Composite foreground")
        self._cb_composite_fg.setChecked(True)
        self._cb_composite_fg.setToolTip(
            "Paste the character from the best single frame back onto the\n"
            "median background after stitching."
        )
        pipeline_form.addRow(self._cb_composite_fg)

        right_layout.addWidget(pipeline_group)

        render_group = QGroupBox("Renderer & Quality")
        render_form = QFormLayout(render_group)

        self._renderer_combo = QComboBox()
        self._renderer_combo.addItem("Temporal Median (recommended)", "median")
        self._renderer_combo.addItem("First-Valid Pixel", "first")
        self._renderer_combo.addItem("Sequential Laplacian Blend", "blend")
        self._renderer_combo.setToolTip(
            "median: Overmix-style suppression of MPEG noise and moving foreground.\n"
            "first: Fastest — takes first valid frame per pixel.\n"
            "blend: Sequential Laplacian blend (SCANS-style)."
        )
        render_form.addRow("Renderer:", self._renderer_combo)

        self._bands_spin = QSpinBox()
        self._bands_spin.setRange(1, 8)
        self._bands_spin.setValue(5)
        self._bands_spin.setToolTip("Laplacian pyramid depth for multi-band seam blending.")
        render_form.addRow("Pyramid bands:", self._bands_spin)

        right_layout.addWidget(render_group)

        ckpt_group = QGroupBox("StitchNet Checkpoint (Optional)")
        ckpt_layout = QVBoxLayout(ckpt_group)
        self._ckpt_path = QLineEdit()
        self._ckpt_path.setPlaceholderText("Path to AnimeStitchNet .pth…")
        self._ckpt_path.setToolTip(
            "Trained AnimeStitchNet checkpoint to supplement LoFTR.\n"
            "Leave blank to use LoFTR only."
        )
        btn_ckpt = QPushButton("Browse Checkpoint…")
        btn_ckpt.clicked.connect(self._browse_checkpoint)
        apply_shadow_effect(btn_ckpt, radius=4, y_offset=2)
        ckpt_layout.addWidget(self._ckpt_path)
        ckpt_layout.addWidget(btn_ckpt)
        right_layout.addWidget(ckpt_group)

        output_group = QGroupBox("Output")
        output_layout = QVBoxLayout(output_group)
        self._output_path = QLineEdit()
        self._output_path.setPlaceholderText("panorama.png")
        self._output_path.setToolTip("Destination path for the stitched panorama.")
        btn_output = QPushButton("Browse Output…")
        btn_output.clicked.connect(self._browse_output)
        apply_shadow_effect(btn_output, radius=4, y_offset=2)
        output_layout.addWidget(self._output_path)
        output_layout.addWidget(btn_output)
        right_layout.addWidget(output_group)

        right_layout.addStretch()
        splitter.addWidget(right_scroll)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([180, 1200, 220])

        root.addWidget(splitter, stretch=1)

        # ── BOTTOM: progress + log ────────────────────────────────────
        bottom = QWidget()
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.setContentsMargins(0, 4, 0, 0)
        bottom_layout.setSpacing(4)

        self._stage_label = QLabel("Ready.")
        self._stage_label.setStyleSheet("color: #aaa; font-size: 10px;")
        bottom_layout.addWidget(self._stage_label)

        self._progress = QProgressBar()
        self._progress.setRange(0, StitchWorker.TOTAL_STAGES)
        self._progress.setValue(0)
        self._progress.setTextVisible(True)
        self._progress.setFormat("%v / %m stages")
        bottom_layout.addWidget(self._progress)

        action_row = QHBoxLayout()
        self._btn_stitch = QPushButton("▶  Stitch Panorama")
        self._btn_stitch.setStyleSheet(
            "background:#4CAF50; color:white; font-weight:bold; padding:8px 18px;"
        )
        apply_shadow_effect(self._btn_stitch, radius=8, y_offset=3)
        self._btn_cancel = QPushButton("■  Cancel")
        self._btn_cancel.setStyleSheet(
            "background:#f44336; color:white; font-weight:bold; padding:8px 18px;"
        )
        self._btn_cancel.setEnabled(False)
        self.stitch_worker = None
        self.stitch_thread = None
        apply_shadow_effect(self._btn_cancel, radius=8, y_offset=3)

        self._btn_stitch.clicked.connect(self._start_stitch)
        self._btn_cancel.clicked.connect(self._cancel_stitch)
        action_row.addWidget(self._btn_stitch)
        action_row.addWidget(self._btn_cancel)
        action_row.addStretch()
        bottom_layout.addLayout(action_row)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setFixedHeight(110)
        self._log.setStyleSheet("font-family: monospace; font-size: 10px;")
        bottom_layout.addWidget(self._log)

        root.addWidget(bottom)

        return panel

    # ======================================================================
    # ── SUB-TAB 1b: Graph ─────────────────────────────────────────────────
    # ======================================================================

    def _build_graph_panel(self) -> QWidget:
        """
        Graph-based stitch planner.

        Left sidebar  — toolbar buttons + selected-node property editor.
        Centre        — node graph canvas (_NodeView / _NodeScene).
        Bottom        — shared pipeline config + progress + run/cancel.

        Workflow
        --------
        1. Click "Add Image" to drop _SourceNode items onto the canvas.
        2. Click "Add Stitch Op" to create a _StitchOpNode.
        3. Drag from an output port (right side, blue) to an input port
           (left side, green) to connect nodes.
        4. Select a _StitchOpNode and set its output path in the sidebar.
        5. Hit "Run Graph" — operations execute in topological order.
        """
        panel = QWidget()
        vbox_lay = QVBoxLayout(panel)
        vbox_lay.setContentsMargins(0, 0, 0, 0)
        v_split = QSplitter(Qt.Orientation.Vertical)
        vbox_lay.addWidget(v_split)

        # ── scene ────────────────────────────────────────────────────────
        self._node_scene = _NodeScene(self)
        self._node_scene.plan_changed.connect(self._graph_refresh_plan)
        self._node_view  = _NodeView(self._node_scene)

        # ── main splitter ────────────────────────────────────────────────
        split = QSplitter(Qt.Orientation.Horizontal)

        # ── LEFT: toolbar + properties ───────────────────────────────────
        left_w  = QWidget()
        left_w.setFixedWidth(190)
        left_lay = QVBoxLayout(left_w)
        left_lay.setContentsMargins(4, 4, 4, 4)
        left_lay.setSpacing(6)

        # Toolbar buttons
        btn_add_img = QPushButton("+ Add Image(s)")
        btn_add_img.setToolTip("Add image source nodes.")
        btn_add_img.clicked.connect(self._graph_add_sources)
        apply_shadow_effect(btn_add_img, radius=4, y_offset=2)

        btn_add_op = QPushButton("+ Add Stitch Op")
        btn_add_op.setToolTip("Add a stitch operation node.")
        btn_add_op.clicked.connect(self._graph_add_op)
        apply_shadow_effect(btn_add_op, radius=4, y_offset=2)

        btn_grow = QPushButton("+ Input Port")
        btn_grow.setToolTip("Add an extra input port to the selected stitch-op node.")
        btn_grow.clicked.connect(self._graph_grow_input)
        apply_shadow_effect(btn_grow, radius=4, y_offset=2)

        btn_del = QPushButton("Delete Selected")
        btn_del.setToolTip("Remove selected nodes / edges (Del).")
        btn_del.clicked.connect(self._node_scene.remove_selected)
        apply_shadow_effect(btn_del, radius=4, y_offset=2)

        btn_clear = QPushButton("Clear All")
        btn_clear.clicked.connect(self._node_scene.clear_graph)
        apply_shadow_effect(btn_clear, radius=4, y_offset=2)

        for b in (btn_add_img, btn_add_op, btn_grow, btn_del, btn_clear):
            left_lay.addWidget(b)

        left_lay.addSpacing(8)

        # Selected-node properties
        props_group = QGroupBox("Selected Op Properties")
        props_form  = QVBoxLayout(props_group)
        props_form.setSpacing(4)

        props_form.addWidget(QLabel("Step name:"))
        self._graph_name_edit = QLineEdit()
        self._graph_name_edit.setPlaceholderText("e.g. Pair A")
        self._graph_name_edit.textChanged.connect(self._graph_apply_props)
        props_form.addWidget(self._graph_name_edit)

        btn_grow_inline = QPushButton("+ Input Port")
        btn_grow_inline.clicked.connect(self._graph_grow_input)
        props_form.addWidget(btn_grow_inline)

        left_lay.addWidget(props_group)

        # Plan summary
        plan_group = QGroupBox("Execution Plan")
        plan_lay   = QVBoxLayout(plan_group)
        self._graph_plan_label = QLabel("(no ops)")
        self._graph_plan_label.setWordWrap(True)
        self._graph_plan_label.setStyleSheet("color:#999; font-size:10px;")
        plan_lay.addWidget(self._graph_plan_label)
        left_lay.addWidget(plan_group)

        left_lay.addStretch()
        split.addWidget(left_w)

        # ── CENTRE: node canvas ───────────────────────────────────────────
        split.addWidget(self._node_view)
        split.setStretchFactor(1, 1)
        v_split.addWidget(split)

        # ── BOTTOM: pipeline options + progress + run ─────────────────────
        bottom_group = QGroupBox("Pipeline & Execution")
        bottom_lay   = QVBoxLayout(bottom_group)
        bottom_lay.setSpacing(4)

        # Reuse same pipeline toggles as Stitch tab (separate widget instances)
        pipe_row = QHBoxLayout()
        self._gph_chk_basic    = QCheckBox("BaSiC")
        self._gph_chk_birefnet = QCheckBox("BiRefNet")
        self._gph_chk_loftr    = QCheckBox("LoFTR")
        self._gph_chk_ecc      = QCheckBox("ECC")
        self._gph_chk_fg       = QCheckBox("Composite FG")
        for chk, default in (
            (self._gph_chk_basic,    True),
            (self._gph_chk_birefnet, True),
            (self._gph_chk_loftr,    True),
            (self._gph_chk_ecc,      True),
            (self._gph_chk_fg,       True),
        ):
            chk.setChecked(default)
            pipe_row.addWidget(chk)
        pipe_row.addStretch()

        # Combined Renderer and Output Row
        config_row = QHBoxLayout()
        config_row.addWidget(QLabel("Renderer:"))
        self._gph_renderer = QComboBox()
        self._gph_renderer.addItems(["median", "first", "blend"])
        config_row.addWidget(self._gph_renderer)
        
        config_row.addSpacing(20)
        
        config_row.addWidget(QLabel("Output dir:"))
        self._gph_out_dir_edit = QLineEdit()
        self._gph_out_dir_edit.setText("images")
        self._gph_out_dir_edit.setToolTip("Directory where stitch outputs are saved.")
        config_row.addWidget(self._gph_out_dir_edit)
        btn_out_dir = QPushButton("…")
        btn_out_dir.setFixedWidth(28)
        btn_out_dir.clicked.connect(self._graph_browse_output_dir)
        config_row.addWidget(btn_out_dir)
        config_row.addStretch()



        self._gph_progress  = QProgressBar()
        self._gph_progress.setRange(0, 100)
        self._gph_progress.setValue(0)
        self._gph_stage_lbl = QLabel("Idle")
        self._gph_stage_lbl.setStyleSheet("color:#aaa; font-size:10px;")

        btn_row = QHBoxLayout()
        self._gph_btn_run    = QPushButton("▶ Run Graph")
        self._gph_btn_run.setStyleSheet(
            "QPushButton{background:#2e7d32;color:white;font-weight:bold;padding:6px;}"
            "QPushButton:hover{background:#388e3c;}"
        )
        self._gph_btn_run.clicked.connect(self._graph_run)
        apply_shadow_effect(self._gph_btn_run, radius=6, y_offset=3)

        self._gph_btn_cancel = QPushButton("Cancel")
        self._gph_btn_cancel.setEnabled(False)
        self._gph_btn_cancel.clicked.connect(self._graph_cancel)
        apply_shadow_effect(self._gph_btn_cancel, radius=4, y_offset=2)

        btn_row.addWidget(self._gph_btn_run)
        btn_row.addWidget(self._gph_btn_cancel)
        btn_row.addStretch()

        self._gph_log = QTextEdit()
        self._gph_log.setReadOnly(True)
        self._gph_log.setFixedHeight(75)
        self._gph_log.setFont(QFont("Monospace", 8))

        bottom_lay.addLayout(pipe_row)
        bottom_lay.addLayout(config_row)
        bottom_lay.addLayout(btn_row)
        bottom_lay.addWidget(self._gph_stage_lbl)
        bottom_lay.addWidget(self._gph_progress)
        bottom_lay.addWidget(self._gph_log)

        v_split.addWidget(bottom_group)
        v_split.setStretchFactor(0, 1)
        v_split.setStretchFactor(1, 0)
        v_split.setSizes([1000, 300])

        # Connect scene selection changes to property editor
        self._node_scene.selectionChanged.connect(self._graph_on_selection_changed)

        return panel

    # ======================================================================
    # ── SUB-TAB 2: Adjust ─────────────────────────────────────────────────
    # ======================================================================

    def _build_adjust_panel(self) -> QWidget:
        panel = QWidget()
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # ── LEFT: load bar + preview + action buttons ──────────────────
        left = QWidget()
        left.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)

        load_bar = QHBoxLayout()
        self._adj_path_edit = QLineEdit()
        self._adj_path_edit.setPlaceholderText("No image loaded…")
        self._adj_path_edit.setReadOnly(True)
        btn_adj_open = QPushButton("Open…")
        btn_adj_open.setToolTip("Load an image to adjust.")
        btn_adj_open.clicked.connect(self._adj_load_image)
        apply_shadow_effect(btn_adj_open, radius=4, y_offset=2)
        load_bar.addWidget(self._adj_path_edit)
        load_bar.addWidget(btn_adj_open)
        left_layout.addLayout(load_bar)

        # Preview label
        self._adj_preview = QLabel("No image loaded.")
        self._adj_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._adj_preview.setMinimumSize(300, 240)
        self._adj_preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._adj_preview.setStyleSheet(
            "background: #181818; border: 1px solid #3a3a3a; color: #666;"
        )
        left_layout.addWidget(self._adj_preview)

        # Status / dims label
        self._adj_status_label = QLabel("")
        self._adj_status_label.setStyleSheet("color: #777; font-size: 10px;")
        self._adj_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_layout.addWidget(self._adj_status_label)

        # Action row
        act_bar = QHBoxLayout()
        self._btn_adj_save = QPushButton("Save As…")
        self._btn_adj_save.setToolTip("Save the adjusted image at full resolution.")
        self._btn_adj_save.setStyleSheet(
            "background:#1976D2; color:white; font-weight:bold; padding:6px 14px;"
        )
        self._btn_adj_save.setEnabled(False)
        self._btn_adj_save.clicked.connect(self._adj_save)
        apply_shadow_effect(self._btn_adj_save, radius=6, y_offset=2)

        self._btn_adj_to_stitch = QPushButton("→ Add to Stitch")
        self._btn_adj_to_stitch.setToolTip(
            "Apply adjustments and add the result to the Stitch queue."
        )
        self._btn_adj_to_stitch.setStyleSheet(
            "background:#388E3C; color:white; font-weight:bold; padding:6px 14px;"
        )
        self._btn_adj_to_stitch.setEnabled(False)
        self._btn_adj_to_stitch.clicked.connect(self._adj_send_to_stitch)
        apply_shadow_effect(self._btn_adj_to_stitch, radius=6, y_offset=2)

        self._btn_adj_to_canvas = QPushButton("→ Add to Canvas")
        self._btn_adj_to_canvas.setToolTip(
            "Apply adjustments and add the result to the Canvas queue."
        )
        self._btn_adj_to_canvas.setStyleSheet(
            "background:#6A1B9A; color:white; font-weight:bold; padding:6px 14px;"
        )
        self._btn_adj_to_canvas.setEnabled(False)
        self._btn_adj_to_canvas.clicked.connect(self._adj_send_to_canvas)
        apply_shadow_effect(self._btn_adj_to_canvas, radius=6, y_offset=2)

        act_bar.addWidget(self._btn_adj_save)
        act_bar.addWidget(self._btn_adj_to_stitch)
        act_bar.addWidget(self._btn_adj_to_canvas)
        left_layout.addLayout(act_bar)

        layout.addWidget(left, stretch=1)

        # ── RIGHT: adjustment controls (scrollable) ────────────────────
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setFixedWidth(285)
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(4, 4, 4, 4)
        right_layout.setSpacing(6)
        right_scroll.setWidget(right)

        # Geometric group
        geo_group = QGroupBox("Geometric")
        geo_layout = QVBoxLayout(geo_group)
        geo_layout.setSpacing(4)

        rot_bar = QHBoxLayout()
        for label, angle in [("↺ 90°", -90), ("↻ 90°", 90), ("↕ 180°", 180)]:
            btn = QPushButton(label)
            btn.setFixedHeight(28)
            btn.clicked.connect(lambda _, a=angle: self._adj_rotate_by(a))
            apply_shadow_effect(btn, radius=3, y_offset=1)
            rot_bar.addWidget(btn)
        geo_layout.addLayout(rot_bar)

        flip_bar = QHBoxLayout()
        btn_flip_h = QPushButton("⟺ Flip H")
        btn_flip_h.setFixedHeight(28)
        btn_flip_h.setCheckable(True)
        btn_flip_h.setToolTip("Mirror image horizontally.")
        btn_flip_h.clicked.connect(lambda checked: self._adj_set_flip(h=checked))
        apply_shadow_effect(btn_flip_h, radius=3, y_offset=1)
        btn_flip_v = QPushButton("⇕ Flip V")
        btn_flip_v.setFixedHeight(28)
        btn_flip_v.setCheckable(True)
        btn_flip_v.setToolTip("Flip image vertically.")
        btn_flip_v.clicked.connect(lambda checked: self._adj_set_flip(v=checked))
        apply_shadow_effect(btn_flip_v, radius=3, y_offset=1)
        self._btn_flip_h = btn_flip_h
        self._btn_flip_v = btn_flip_v
        flip_bar.addWidget(btn_flip_h)
        flip_bar.addWidget(btn_flip_v)
        geo_layout.addLayout(flip_bar)

        angle_form = QFormLayout()
        angle_form.setSpacing(3)
        self._adj_angle_spin = QDoubleSpinBox()
        self._adj_angle_spin.setRange(-180.0, 180.0)
        self._adj_angle_spin.setValue(0.0)
        self._adj_angle_spin.setSuffix("°")
        self._adj_angle_spin.setSingleStep(0.5)
        self._adj_angle_spin.setDecimals(1)
        self._adj_angle_spin.setToolTip("Fine rotation (positive = clockwise).")
        self._adj_angle_spin.valueChanged.connect(self._adj_schedule_preview)
        angle_form.addRow("Fine rotate:", self._adj_angle_spin)
        geo_layout.addLayout(angle_form)

        right_layout.addWidget(geo_group)

        # Crop group
        crop_group = QGroupBox("Crop to Aspect Ratio")
        crop_form = QFormLayout(crop_group)
        crop_form.setSpacing(3)
        self._adj_crop_combo = QComboBox()
        for label, ratio in _CROP_PRESETS:
            self._adj_crop_combo.addItem(label, ratio)
        self._adj_crop_combo.setToolTip("Center-crop to this aspect ratio before other adjustments.")
        self._adj_crop_combo.currentIndexChanged.connect(self._adj_schedule_preview)
        crop_form.addRow("Preset:", self._adj_crop_combo)
        right_layout.addWidget(crop_group)

        # White Balance group  (fixes yellow/blue tinting between stitched frames)
        wb_group = QGroupBox("White Balance")
        wb_form  = QFormLayout(wb_group)
        wb_form.setSpacing(3)
        self._adj_temperature = self._make_slider(-100, 100, 0, "Temp (warm→cool)", wb_form)
        self._adj_tint        = self._make_slider(-100, 100, 0, "Tint (mag→green)", wb_form)
        btn_auto_wb = QPushButton("Auto WB (Gray World)")
        btn_auto_wb.setFixedHeight(26)
        btn_auto_wb.setToolTip(
            "Apply gray-world white balance: corrects dominant colour casts "
            "(e.g. the yellow tinting that appears when stitching frames with "
            "different colour grading)."
        )
        btn_auto_wb.clicked.connect(self._adj_apply_auto_wb)
        apply_shadow_effect(btn_auto_wb, radius=3, y_offset=1)
        wb_form.addRow("", btn_auto_wb)
        right_layout.addWidget(wb_group)

        # Tone group
        tone_group = QGroupBox("Tone")
        tone_form = QFormLayout(tone_group)
        tone_form.setSpacing(3)
        self._adj_brightness = self._make_slider(-100, 100, 0,   "Brightness", tone_form)
        self._adj_contrast   = self._make_slider(-100, 100, 0,   "Contrast",   tone_form)
        self._adj_gamma      = self._make_slider(10,   500, 100, "Gamma ×100", tone_form)
        self._adj_shadows    = self._make_slider(-100, 100, 0,   "Shadows",    tone_form)
        self._adj_highlights = self._make_slider(-100, 100, 0,   "Highlights", tone_form)
        right_layout.addWidget(tone_group)

        # Color group
        color_group = QGroupBox("Color")
        color_form = QFormLayout(color_group)
        color_form.setSpacing(3)
        self._adj_saturation = self._make_slider(-100, 100, 0, "Saturation", color_form)
        self._adj_vibrance   = self._make_slider(-100, 100, 0, "Vibrance",   color_form)
        self._adj_hue        = self._make_slider(-180, 180, 0, "Hue shift",  color_form)
        right_layout.addWidget(color_group)

        # Detail group
        detail_group = QGroupBox("Detail")
        detail_form = QFormLayout(detail_group)
        detail_form.setSpacing(3)
        self._adj_sharpen = self._make_slider(0,  100, 0, "Sharpen", detail_form)
        self._adj_blur    = self._make_slider(0,   50, 0, "Blur",    detail_form)
        right_layout.addWidget(detail_group)

        # Reset
        btn_adj_reset = QPushButton("Reset All")
        btn_adj_reset.setToolTip("Reset all adjustments to defaults.")
        btn_adj_reset.clicked.connect(self._adj_reset)
        apply_shadow_effect(btn_adj_reset, radius=4, y_offset=2)
        right_layout.addWidget(btn_adj_reset)
        right_layout.addStretch()

        layout.addWidget(right_scroll)

        return panel

    def _make_slider(
        self, min_val: int, max_val: int, default: int, label: str, form: QFormLayout
    ) -> QSlider:
        """Create an int QSlider + current-value label and add them as a form row."""
        row = QWidget()
        hl = QHBoxLayout(row)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(4)
        sl = QSlider(Qt.Orientation.Horizontal)
        sl.setRange(min_val, max_val)
        sl.setValue(default)
        lbl = QLabel(str(default))
        lbl.setFixedWidth(36)
        lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        lbl.setStyleSheet("color: #bbb; font-size: 10px;")
        sl.valueChanged.connect(lambda v, _lbl=lbl: _lbl.setText(str(v)))
        sl.valueChanged.connect(self._adj_schedule_preview)
        hl.addWidget(sl)
        hl.addWidget(lbl)
        form.addRow(label + ":", row)
        return sl

    # ======================================================================
    # ── SUB-TAB 3: Canvas ─────────────────────────────────────────────────
    # ======================================================================

    def _build_canvas_panel(self) -> QWidget:
        panel = QWidget()
        root_layout = QVBoxLayout(panel)
        root_layout.setContentsMargins(6, 6, 6, 6)
        root_layout.setSpacing(6)

        # ── Top bar: output size ───────────────────────────────────────
        size_group = QGroupBox("Output Size")
        size_layout = QHBoxLayout(size_group)
        size_layout.setSpacing(6)

        self._cv_preset_combo = QComboBox()
        for label, _ in _SIZE_PRESETS:
            self._cv_preset_combo.addItem(label)
        self._cv_preset_combo.currentIndexChanged.connect(self._cv_on_preset_changed)
        size_layout.addWidget(QLabel("Preset:"))
        size_layout.addWidget(self._cv_preset_combo, stretch=1)

        size_layout.addWidget(QLabel("W:"))
        self._cv_width_spin = QSpinBox()
        self._cv_width_spin.setRange(64, 16384)
        self._cv_width_spin.setValue(1920)
        self._cv_width_spin.setSuffix(" px")
        self._cv_width_spin.setFixedWidth(100)
        size_layout.addWidget(self._cv_width_spin)

        size_layout.addWidget(QLabel("H:"))
        self._cv_height_spin = QSpinBox()
        self._cv_height_spin.setRange(64, 16384)
        self._cv_height_spin.setValue(1080)
        self._cv_height_spin.setSuffix(" px")
        self._cv_height_spin.setFixedWidth(100)
        size_layout.addWidget(self._cv_height_spin)

        root_layout.addWidget(size_group)

        # ── Main area: image list │ preview ───────────────────────────
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_splitter.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Left: image list + controls
        left = QWidget()
        left.setFixedWidth(260)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 4, 0)

        img_group = QGroupBox("Images")
        img_group_layout = QVBoxLayout(img_group)

        self._cv_list = QListWidget()
        self._cv_list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self._cv_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self._cv_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self._cv_list.setToolTip("Drag to reorder. Images are placed left-to-right / top-to-bottom.")
        self._cv_list.setIconSize(QSize(48, 48))
        self._cv_list.model().rowsMoved.connect(self._cv_sync_paths)
        img_group_layout.addWidget(self._cv_list)

        cv_btn_grid = QGridLayout()
        cv_btn_grid.setSpacing(4)
        btn_cv_add = QPushButton("Add…")
        btn_cv_add.clicked.connect(self._cv_add_images)
        apply_shadow_effect(btn_cv_add, radius=4, y_offset=2)
        btn_cv_remove = QPushButton("Remove")
        btn_cv_remove.clicked.connect(self._cv_remove_selected)
        apply_shadow_effect(btn_cv_remove, radius=4, y_offset=2)
        btn_cv_clear = QPushButton("Clear All")
        btn_cv_clear.clicked.connect(self._cv_clear_all)
        apply_shadow_effect(btn_cv_clear, radius=4, y_offset=2)
        cv_btn_grid.addWidget(btn_cv_add,    0, 0)
        cv_btn_grid.addWidget(btn_cv_remove, 0, 1)
        cv_btn_grid.addWidget(btn_cv_clear,  1, 0, 1, 2)
        img_group_layout.addLayout(cv_btn_grid)
        left_layout.addWidget(img_group)

        # Layout options
        layout_group = QGroupBox("Layout")
        layout_v = QVBoxLayout(layout_group)
        layout_v.setSpacing(4)

        self._cv_layout_bg = QButtonGroup(self)
        self._cv_radio_h = QRadioButton("Horizontal")
        self._cv_radio_v = QRadioButton("Vertical")
        self._cv_radio_g = QRadioButton("Grid")
        self._cv_radio_h.setChecked(True)
        for rb in (self._cv_radio_h, self._cv_radio_v, self._cv_radio_g):
            self._cv_layout_bg.addButton(rb)
            layout_v.addWidget(rb)

        grid_cols_row = QHBoxLayout()
        grid_cols_row.addWidget(QLabel("Columns:"))
        self._cv_cols_spin = QSpinBox()
        self._cv_cols_spin.setRange(1, 20)
        self._cv_cols_spin.setValue(2)
        self._cv_cols_spin.setFixedWidth(70)
        grid_cols_row.addWidget(self._cv_cols_spin)
        grid_cols_row.addStretch()
        layout_v.addLayout(grid_cols_row)

        left_layout.addWidget(layout_group)

        # Style options
        style_group = QGroupBox("Style")
        style_form = QFormLayout(style_group)
        style_form.setSpacing(4)

        gap_row = QHBoxLayout()
        self._cv_gap_spin = QSpinBox()
        self._cv_gap_spin.setRange(0, 200)
        self._cv_gap_spin.setValue(0)
        self._cv_gap_spin.setSuffix(" px")
        self._cv_gap_spin.setFixedWidth(80)
        gap_row.addWidget(self._cv_gap_spin)
        gap_row.addStretch()
        style_form.addRow("Gap:", gap_row)

        self._cv_scale_combo = QComboBox()
        self._cv_scale_combo.addItem("Fit (letterbox)", "fit")
        self._cv_scale_combo.addItem("Fill (center crop)", "fill")
        self._cv_scale_combo.addItem("Stretch", "stretch")
        self._cv_scale_combo.setToolTip(
            "Fit: preserve aspect ratio, add background bars.\n"
            "Fill: fill the cell, crop the excess.\n"
            "Stretch: deform to fill."
        )
        style_form.addRow("Scale:", self._cv_scale_combo)

        bg_row = QHBoxLayout()
        self._cv_bg_btn = QPushButton("  ")
        self._cv_bg_btn.setFixedWidth(40)
        self._cv_bg_btn.setToolTip("Background colour.")
        self._cv_bg_btn.clicked.connect(self._cv_pick_bg_color)
        self._cv_bg_label = QLabel("#000000")
        self._cv_bg_label.setStyleSheet("color: #aaa; font-size: 10px;")
        self._cv_update_bg_button()
        bg_row.addWidget(self._cv_bg_btn)
        bg_row.addWidget(self._cv_bg_label)
        bg_row.addStretch()
        style_form.addRow("Background:", bg_row)

        left_layout.addWidget(style_group)
        left_layout.addStretch()

        main_splitter.addWidget(left)

        # Right: preview
        preview_widget = QWidget()
        preview_layout = QVBoxLayout(preview_widget)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(4)

        self._cv_preview_label = QLabel("Press 'Preview' to render the canvas.")
        self._cv_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._cv_preview_label.setSizePolicy(QSizePolicy.Policy.Expanding,
                                              QSizePolicy.Policy.Expanding)
        self._cv_preview_label.setStyleSheet(
            "background: #181818; border: 1px solid #3a3a3a; color: #666;"
        )
        preview_layout.addWidget(self._cv_preview_label)

        self._cv_status_label = QLabel("")
        self._cv_status_label.setStyleSheet("color: #777; font-size: 10px;")
        self._cv_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_layout.addWidget(self._cv_status_label)

        main_splitter.addWidget(preview_widget)
        main_splitter.setStretchFactor(0, 0)
        main_splitter.setStretchFactor(1, 1)

        root_layout.addWidget(main_splitter, stretch=1)

        # ── Bottom: action bar ─────────────────────────────────────────
        cv_action_bar = QHBoxLayout()
        self._btn_cv_preview = QPushButton("▶  Preview")
        self._btn_cv_preview.setStyleSheet(
            "background:#1976D2; color:white; font-weight:bold; padding:7px 16px;"
        )
        apply_shadow_effect(self._btn_cv_preview, radius=6, y_offset=2)
        self._btn_cv_preview.clicked.connect(self._cv_run_preview)

        self._btn_cv_export = QPushButton("⬇  Export Canvas…")
        self._btn_cv_export.setStyleSheet(
            "background:#4CAF50; color:white; font-weight:bold; padding:7px 16px;"
        )
        apply_shadow_effect(self._btn_cv_export, radius=6, y_offset=2)
        self._btn_cv_export.clicked.connect(self._cv_export)

        self._cv_export_format = QComboBox()
        self._cv_export_format.addItem("PNG",  "png")
        self._cv_export_format.addItem("JPEG", "jpg")
        self._cv_export_format.addItem("WebP", "webp")

        self._cv_progress = QProgressBar()
        self._cv_progress.setRange(0, 0)
        self._cv_progress.setVisible(False)
        self._cv_progress.setFixedWidth(150)
        self._cv_progress.setTextVisible(False)

        cv_action_bar.addWidget(self._btn_cv_preview)
        cv_action_bar.addWidget(self._btn_cv_export)
        cv_action_bar.addWidget(QLabel("Format:"))
        cv_action_bar.addWidget(self._cv_export_format)
        cv_action_bar.addWidget(self._cv_progress)
        cv_action_bar.addStretch()
        root_layout.addLayout(cv_action_bar)

        return panel

    # ======================================================================
    # ── Stitch methods ─────────────────────────────────────────────────────
    # ======================================================================

    def _add_frames(self):
        start_dir = (
            os.path.dirname(self._frame_paths[-1]) if self._frame_paths else ""
        )
        dlg = _ThumbnailFilePicker(self, start_dir=start_dir)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        for p in dlg.selected_paths():
            if p and p not in self._frame_paths:
                self._frame_paths.append(p)
                self._frame_list.addItem(self._make_frame_item(p))
        self._refresh_pair_combo()

    def _remove_selected_frame(self):
        row = self._frame_list.currentRow()
        if row < 0:
            return
        self._frame_list.takeItem(row)
        self._frame_paths.pop(row)
        self._manual_affines = {
            k: v for k, v in self._manual_affines.items()
            if k[0] < len(self._frame_paths) and k[1] < len(self._frame_paths)
        }
        self._refresh_pair_combo()

    def _move_frame_up(self):
        row = self._frame_list.currentRow()
        if row <= 0:
            return
        self._swap_rows(row, row - 1)
        self._frame_list.setCurrentRow(row - 1)

    def _move_frame_down(self):
        row = self._frame_list.currentRow()
        if row < 0 or row >= self._frame_list.count() - 1:
            return
        self._swap_rows(row, row + 1)
        self._frame_list.setCurrentRow(row + 1)

    def _swap_rows(self, a: int, b: int):
        self._frame_paths[a], self._frame_paths[b] = (
            self._frame_paths[b], self._frame_paths[a]
        )
        item_a = self._frame_list.takeItem(a)
        item_b = self._frame_list.takeItem(b - 1)
        self._frame_list.insertItem(b - 1, item_a)
        self._frame_list.insertItem(a, item_b)
        self._manual_affines.clear()
        self._refresh_pair_combo()

    @Slot(object, object, int, int, int, int)
    def _on_rows_reordered(self, *_):
        self._frame_paths = [
            self._frame_list.item(r).data(Qt.ItemDataRole.UserRole)
            for r in range(self._frame_list.count())
        ]
        self._manual_affines.clear()
        self._refresh_pair_combo()

    @Slot(int)
    def _on_frame_selection_changed(self, row: int):
        if row < 0 or len(self._frame_paths) < 2:
            return
        j = min(row + 1, len(self._frame_paths) - 1)
        i = row if j > row else row - 1
        pair_text = f"Frame {i} → {j}"
        idx = self._pair_combo.findText(pair_text)
        if idx >= 0:
            self._pair_combo.setCurrentIndex(idx)

    def _refresh_pair_combo(self):
        self._pair_combo.blockSignals(True)
        self._pair_combo.clear()
        n = len(self._frame_paths)
        for i in range(n - 1):
            self._pair_combo.addItem(f"Frame {i} → {i + 1}", (i, i + 1))
        for i in range(n - 2):
            self._pair_combo.addItem(f"Frame {i} → {i + 2}  (skip)", (i, i + 2))
        self._pair_combo.blockSignals(False)
        if self._pair_combo.count():
            self._pair_combo.setCurrentIndex(0)
            self._on_pair_changed(0)

    @Slot(int)
    def _on_pair_changed(self, idx: int):
        if idx < 0 or idx >= self._pair_combo.count():
            return
        pair = self._pair_combo.itemData(idx)
        if pair is None:
            return
        self._current_pair = tuple(pair)
        i, j = self._current_pair
        if i >= len(self._frame_paths) or j >= len(self._frame_paths):
            return
        img_a = cv2.imread(self._frame_paths[i])
        img_b = cv2.imread(self._frame_paths[j])
        if img_a is None or img_b is None:
            return
        ha, wa = img_a.shape[:2]
        hb, wb = img_b.shape[:2]
        self._scene.load_pair(img_a, img_b, ha, wa, hb, wb)
        QTimer.singleShot(50, self._match_view.fit)

        if self._current_pair in self._manual_affines:
            self._affine_label.setText(
                f"Manual override active for pair {i}→{j}. Drag anchors to adjust."
            )
            self._affine_label.setStyleSheet("color: #80CBC4; font-size: 10px; padding: 2px;")
        else:
            self._affine_label.setText("No manual alignment override active.")
            self._affine_label.setStyleSheet("color: #888; font-size: 10px; padding: 2px;")

        self._match_count_label.setText("—")

    def _compute_matches(self):
        if len(self._frame_paths) < 2:
            QMessageBox.warning(self, "No frames", "Add at least 2 frames first.")
            return
        i, j = self._current_pair
        if i >= len(self._frame_paths) or j >= len(self._frame_paths):
            return
        if self._match_thread and self._match_thread.isRunning():
            return

        self._btn_compute.setEnabled(False)
        self._log_append(f"[LoFTR] Computing matches for pair {i}→{j}…")

        self._match_worker = MatchWorker(
            self._frame_paths[i], self._frame_paths[j],
            conf_thresh=self._conf_thresh_spin.value(),
            use_birefnet=self._cb_birefnet.isChecked(),
        )
        self._match_thread = QThread(self)
        self._match_worker.moveToThread(self._match_thread)
        self._match_thread.started.connect(self._match_worker.run)
        self._match_worker.sig_finished.connect(self._on_matches_ready)
        self._match_worker.sig_error.connect(self._on_match_error)
        self._match_worker.sig_finished.connect(self._match_thread.quit)
        self._match_worker.sig_error.connect(self._match_thread.quit)
        self._match_thread.finished.connect(lambda: self._btn_compute.setEnabled(True))
        self._match_thread.start()

    @Slot(object, object, object)
    def _on_matches_ready(self, pts1, pts2, conf):
        n = len(pts1)
        self._match_count_label.setText(
            f"{n} (conf ≥ {self._conf_thresh_spin.value():.2f})"
        )
        self._log_append(
            f"[LoFTR] {n} matches for pair {self._current_pair[0]}→{self._current_pair[1]}."
        )
        self._scene.show_matches(pts1, pts2, conf)
        QTimer.singleShot(50, self._match_view.fit)

    @Slot(str)
    def _on_match_error(self, msg: str):
        self._log_append(f"[LoFTR] Error: {msg}")

    def _show_mask(self):
        row = self._frame_list.currentRow()
        if row < 0 or row >= len(self._frame_paths):
            QMessageBox.warning(self, "No frame selected", "Select a frame in the list first.")
            return
        if self._mask_thread and self._mask_thread.isRunning():
            return

        self._btn_show_mask.setEnabled(False)
        self._log_append(f"[BiRefNet] Masking frame {row}…")

        self._mask_worker = MaskPreviewWorker(self._frame_paths[row])
        self._mask_thread = QThread(self)
        self._mask_worker.moveToThread(self._mask_thread)
        self._mask_thread.started.connect(self._mask_worker.run)
        self._mask_worker.sig_finished.connect(self._on_mask_ready)
        self._mask_worker.sig_error.connect(self._on_mask_error)
        self._mask_worker.sig_finished.connect(self._mask_thread.quit)
        self._mask_worker.sig_error.connect(self._mask_thread.quit)
        self._mask_thread.finished.connect(lambda: self._btn_show_mask.setEnabled(True))
        self._mask_thread.start()

    @Slot(object)
    def _on_mask_ready(self, mask):
        row = self._frame_list.currentRow()
        if row < 0 or row >= len(self._frame_paths):
            return
        img = cv2.imread(self._frame_paths[row])
        if img is not None:
            self._scene.show_mask(img, mask)
        self._log_append("[BiRefNet] Mask overlay applied to left frame.")

    @Slot(str)
    def _on_mask_error(self, msg: str):
        self._log_append(f"[BiRefNet] Error: {msg}")

    @Slot(object)
    def _on_affine_updated(self, M):
        if M is None:
            return
        self._manual_affines[self._current_pair] = M.astype(np.float32)
        i, j = self._current_pair
        tx, ty = float(M[0, 2]), float(M[1, 2])
        scale = float(np.sqrt(M[0, 0] ** 2 + M[1, 0] ** 2))
        angle_deg = float(np.degrees(np.arctan2(M[1, 0], M[0, 0])))
        self._affine_label.setText(
            f"Manual override {i}→{j}:  tx={tx:.1f}  ty={ty:.1f}  "
            f"scale={scale:.3f}  θ={angle_deg:.2f}°"
        )
        self._affine_label.setStyleSheet("color: #80CBC4; font-size: 10px; padding: 2px;")

    def _reset_anchors(self):
        if self._current_pair in self._manual_affines:
            del self._manual_affines[self._current_pair]
        self._affine_label.setText("Manual override cleared — LoFTR will be used.")
        self._affine_label.setStyleSheet("color: #888; font-size: 10px; padding: 2px;")
        self._compute_matches()

    def _browse_checkpoint(self):
        p, _ = QFileDialog.getOpenFileName(
            self, "Select StitchNet checkpoint", "", "PyTorch (*.pth *.pt)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if p:
            self._ckpt_path.setText(p)

    def _browse_output(self):
        p, _ = QFileDialog.getSaveFileName(
            self, "Save Panorama As", "panorama.png",
            "Images (*.png *.webp *.jpg)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if p:
            self._output_path.setText(p)

    def _start_stitch(self):
        if len(self._frame_paths) < 2:
            QMessageBox.warning(self, "Not enough frames", "Add at least 2 source frames.")
            return

        out = self._output_path.text().strip()
        if not out:
            out, _ = QFileDialog.getSaveFileName(
                self, "Save Panorama As", "panorama.png",
                "Images (*.png *.webp *.jpg)",
                options=QFileDialog.Option.DontUseNativeDialog,
            )
            if not out:
                return
            self._output_path.setText(out)

        self._btn_stitch.setEnabled(False)
        self._btn_cancel.setEnabled(True)
        self._progress.setValue(0)
        self._log.clear()
        self._stage_label.setText("Initialising pipeline…")
        self._log_append(
            f"[Stitch] Starting — {len(self._frame_paths)} frames → '{out}'"
        )
        if self._manual_affines:
            self._log_append(
                f"[Stitch] Manual affine overrides active for "
                f"{len(self._manual_affines)} pair(s)."
            )

        pipeline_config = {
            "use_basic":       self._cb_basic.isChecked(),
            "use_birefnet":    self._cb_birefnet.isChecked(),
            "use_loftr":       self._cb_loftr.isChecked(),
            "use_ecc":         self._cb_ecc.isChecked(),
            "renderer":        self._renderer_combo.currentData(),
            "composite_fg":    self._cb_composite_fg.isChecked(),
            "laplacian_bands": self._bands_spin.value(),
            "stitch_net_ckpt": self._ckpt_path.text().strip(),
        }

        self._stitch_worker = StitchWorker(
            image_paths=list(self._frame_paths),
            output_path=out,
            pipeline_config=pipeline_config,
            manual_affines=dict(self._manual_affines),
        )
        self._stitch_thread = QThread(self)
        self._stitch_worker.moveToThread(self._stitch_thread)
        self._stitch_thread.started.connect(self._stitch_worker.run)
        self._stitch_worker.sig_stage.connect(self._on_stage)
        self._stitch_worker.sig_log.connect(self._log_append)
        self._stitch_worker.sig_finished.connect(self._on_stitch_finished)
        self._stitch_worker.sig_error.connect(self._on_stitch_error)
        self._stitch_worker.sig_finished.connect(self._stitch_thread.quit)
        self._stitch_worker.sig_error.connect(self._stitch_thread.quit)
        self._stitch_thread.finished.connect(self._on_stitch_thread_done)
        self._stitch_thread.start()

    def _cancel_stitch(self):
        if self._stitch_worker:
            self._stitch_worker.cancel()
            self._btn_cancel.setEnabled(False)
        self._stitch_worker = None
        self._stitch_thread = None
        self._log_append("[Stitch] Cancellation requested...")

    @Slot(int, int, str)
    def _on_stage(self, current: int, total: int, label: str):
        self._progress.setValue(current)
        self._stage_label.setText(f"Stage {current}/{total}: {label}")

    @Slot(str)
    def _on_stitch_finished(self, output_path: str):
        self._log_append(f"[Stitch] Complete. Saved to: {output_path}")
        QMessageBox.information(self, "Stitch Complete",
                                f"Panorama saved to:\n{output_path}")

    @Slot(str)
    def _on_stitch_error(self, msg: str):
        self._log_append(f"[Stitch] Error: {msg}")
        if "Cancelled" not in msg:
            QMessageBox.critical(self, "Stitch Error", msg)

    def _on_stitch_thread_done(self):
        self._btn_stitch.setEnabled(True)
        self._btn_cancel.setEnabled(False)
        self._stitch_worker = None
        self._stitch_thread = None
        self._progress.setValue(0)
        self._stage_label.setText("Ready.")

    def _log_append(self, msg: str):
        self._log.append(msg)
        self._log.verticalScrollBar().setValue(
            self._log.verticalScrollBar().maximum()
        )

    # ======================================================================
    # ── Graph methods ──────────────────────────────────────────────────────
    # ======================================================================

    def _graph_add_sources(self):
        dlg = _ThumbnailFilePicker(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        for p in dlg.selected_paths():
            self._node_scene.add_source(p)

    def _graph_add_op(self):
        op = self._node_scene.add_stitch_op()
        # Select the new op so its properties appear immediately
        self._node_scene.clearSelection()
        op.setSelected(True)

    def _graph_grow_input(self):
        # Prefer currently selected op; fall back to last selected so sidebar
        # buttons work even if clicking them briefly moved focus away.
        target: Optional[_StitchOpNode] = None
        for item in self._node_scene.selectedItems():
            if isinstance(item, _StitchOpNode):
                target = item
                break
        if target is None:
            target = self._last_selected_op
        if target is not None:
            target.grow_input()
            self._node_scene.plan_changed.emit()
            self._node_scene.update()

    def _graph_on_selection_changed(self):
        try:
            items = self._node_scene.selectedItems()
        except RuntimeError:
            return

        for item in items:
            if isinstance(item, _StitchOpNode):
                self._last_selected_op = item
                self._graph_name_edit.blockSignals(True)
                self._graph_name_edit.setText(item.step_name)
                self._graph_name_edit.blockSignals(False)
                return

    def _graph_apply_props(self):
        try:
            items = self._node_scene.selectedItems()
        except RuntimeError:
            return
        for item in items:
            if isinstance(item, _StitchOpNode):
                item.step_name = self._graph_name_edit.text()
                item._title    = f"⊞ {item.step_name}"
                item.update()
                self._node_scene.plan_changed.emit()
                break

    def _graph_browse_output_dir(self):
        d = QFileDialog.getExistingDirectory(
            self, "Select Output Directory",
            self._gph_out_dir_edit.text() or "images",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if d:
            self._gph_out_dir_edit.setText(d)

    def _graph_refresh_plan(self):
        try:
            plan = self._node_scene.get_plan()
        except RuntimeError:
            return
        if not plan:
            self._graph_plan_label.setText("(no ops)")
            return
        lines = []
        for step in plan:
            ins = ", ".join(
                os.path.basename(i) if not i.startswith("op_") else i
                for i in step["inputs"]
            )
            out = os.path.basename(step["output"]) or "(not set)"
            lines.append(f"{step['name']}: [{ins}] → {out}")
        self._graph_plan_label.setText("\n".join(lines))

    def _graph_run(self):
        plan = self._node_scene.get_plan()
        if not plan:
            QMessageBox.warning(self, "Graph", "No stitch operations defined.")
            return
        for step in plan:
            if not step["inputs"]:
                QMessageBox.warning(
                    self, "Graph",
                    f"Step '{step['name']}' has no connected inputs."
                )
                return

        # Auto-assign output paths under the chosen output directory.
        out_dir = self._gph_out_dir_edit.text().strip() or "images"
        out_dir = os.path.abspath(out_dir)
        os.makedirs(out_dir, exist_ok=True)
        for i, step in enumerate(plan, start=1):
            if not step["output"]:
                slug = re.sub(r"[^\w]+", "_", step["name"]).strip("_").lower() or f"op{i}"
                step["output"] = os.path.join(out_dir, f"{slug}.png")
                # keep the node's stored path in sync so get_plan() stays consistent
                for item in self._node_scene.items():
                    if isinstance(item, _StitchOpNode) and item.step_name == step["name"]:
                        item.output_path = step["output"]
                        break

        cfg = {
            "use_basic":       self._gph_chk_basic.isChecked(),
            "use_birefnet":    self._gph_chk_birefnet.isChecked(),
            "use_loftr":       self._gph_chk_loftr.isChecked(),
            "use_ecc":         self._gph_chk_ecc.isChecked(),
            "composite_fg":    self._gph_chk_fg.isChecked(),
            "renderer":        self._gph_renderer.currentText(),
            "laplacian_bands": 5,
        }

        self._graph_worker = GraphStitchWorker(plan, cfg)
        self._graph_thread = QThread(self)
        self._graph_worker.moveToThread(self._graph_thread)
        self._graph_thread.started.connect(self._graph_worker.run)
        self._graph_worker.sig_step.connect(self._graph_on_step)
        self._graph_worker.sig_stage.connect(self._graph_on_stage)
        self._graph_worker.sig_log.connect(self._graph_log_append)
        self._graph_worker.sig_finished.connect(self._graph_on_finished)
        self._graph_worker.sig_error.connect(self._graph_on_error)
        self._graph_worker.sig_finished.connect(self._graph_thread.quit)
        self._graph_worker.sig_error.connect(self._graph_thread.quit)
        self._graph_thread.finished.connect(self._graph_on_thread_done)

        self._gph_btn_run.setEnabled(False)
        self._gph_btn_cancel.setEnabled(True)
        self._gph_log.clear()
        self._graph_thread.start()

    def _graph_cancel(self):
        if self._graph_worker:
            self._graph_worker.cancel()

    @Slot(int, int, str)
    def _graph_on_step(self, current: int, total: int, name: str):
        pct = int((current - 1) / total * 100)
        self._gph_progress.setValue(pct)
        self._gph_stage_lbl.setText(f"Step {current}/{total}: {name}")

    @Slot(int, int, str)
    def _graph_on_stage(self, stage: int, total: int, label: str):
        self._gph_stage_lbl.setText(f"  ↳ [{stage}/{total}] {label}")

    @Slot(list)
    def _graph_on_finished(self, paths: list):
        self._gph_progress.setValue(100)
        self._gph_stage_lbl.setText("Done.")
        self._graph_log_append(f"\n✓ Graph complete. Outputs: {paths}")

    @Slot(str)
    def _graph_on_error(self, msg: str):
        self._gph_stage_lbl.setText(f"Error: {msg}")
        self._graph_log_append(f"[ERROR] {msg}")

    def _graph_on_thread_done(self):
        self._gph_btn_run.setEnabled(True)
        self._gph_btn_cancel.setEnabled(False)

    def _graph_log_append(self, msg: str):
        self._gph_log.append(msg)
        sb = self._gph_log.verticalScrollBar()
        sb.setValue(sb.maximum())

    # ======================================================================
    # ── Adjust methods ─────────────────────────────────────────────────────
    # ======================================================================

    def _adj_apply_auto_wb(self):
        """Apply gray-world auto white balance as a one-shot preset."""
        if not self._adj_img_path:
            return
        # Set temperature and tint to 0, enable auto_wb via a temp param run
        # then disable auto_wb and bake the correction into temp/tint sliders.
        # Simpler: just run a one-shot AdjustWorker with auto_wb=True and
        # save the result to a temp file, then reload it as the adjusted image.
        import tempfile
        from gui.src.helpers.models.stitch_worker import _apply_adjustments as _aa
        try:
            from PIL import Image as _PILImage
            img = _PILImage.open(self._adj_img_path)
            result = _aa(img, {"auto_wb": True})
            tmp = tempfile.NamedTemporaryFile(
                suffix=os.path.splitext(self._adj_img_path)[1] or ".png",
                delete=False,
            )
            result.save(tmp.name)
            tmp.close()
            # Reset temperature/tint sliders then trigger preview from tmp
            for sl in (self._adj_temperature, self._adj_tint):
                sl.blockSignals(True)
                sl.setValue(0)
                sl.blockSignals(False)
            self._adj_img_path = tmp.name
            self._adj_schedule_preview()
        except Exception as e:
            self._adj_status_label.setText(f"Auto WB failed: {e}")

    def _adj_load_image(self):
        p, _ = QFileDialog.getOpenFileName(
            self, "Open Image", "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp *.tiff *.tif)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if not p:
            return
        self._adj_img_path = p
        self._adj_path_edit.setText(p)
        self._btn_adj_save.setEnabled(True)
        self._btn_adj_to_stitch.setEnabled(True)
        self._btn_adj_to_canvas.setEnabled(True)
        self._adj_run_preview()

    def _adj_schedule_preview(self, *_):
        if self._adj_img_path:
            self._adj_debounce.start()

    def _adj_collect_params(self) -> dict:
        return {
            "crop_ar":     self._adj_crop_combo.currentData(),
            "rotate":      self._adj_angle_spin.value(),
            "flip_h":      self._adj_flip_h,
            "flip_v":      self._adj_flip_v,
            "temperature": self._adj_temperature.value(),
            "tint":        self._adj_tint.value(),
            "brightness":  self._adj_brightness.value(),
            "contrast":    self._adj_contrast.value(),
            "gamma":       self._adj_gamma.value(),
            "shadows":     self._adj_shadows.value(),
            "highlights":  self._adj_highlights.value(),
            "saturation":  self._adj_saturation.value(),
            "vibrance":    self._adj_vibrance.value(),
            "hue":         self._adj_hue.value(),
            "sharpen":     self._adj_sharpen.value(),
            "blur":        self._adj_blur.value(),
        }

    def _adj_run_preview(self):
        if not self._adj_img_path:
            return
        if self._adj_thread and self._adj_thread.isRunning():
            self._adj_debounce.start()
            return

        self._adj_status_label.setText("Rendering preview…")
        self._adj_worker = AdjustWorker(
            self._adj_img_path, self._adj_collect_params(), max_size=900
        )
        self._adj_thread = QThread(self)
        self._adj_worker.moveToThread(self._adj_thread)
        self._adj_thread.started.connect(self._adj_worker.run)
        self._adj_worker.sig_finished.connect(self._on_adj_preview_ready)
        self._adj_worker.sig_error.connect(self._on_adj_error)
        self._adj_worker.sig_finished.connect(self._adj_thread.quit)
        self._adj_worker.sig_error.connect(self._adj_thread.quit)
        self._adj_thread.start()

    @Slot(object)
    def _on_adj_preview_ready(self, qi: QImage):
        w, h = qi.width(), qi.height()
        px = QPixmap.fromImage(qi)
        # Scale to fit the label while preserving aspect ratio
        lw = self._adj_preview.width()
        lh = self._adj_preview.height()
        px = px.scaled(lw, lh, Qt.AspectRatioMode.KeepAspectRatio,
                       Qt.TransformationMode.SmoothTransformation)
        self._adj_preview.setPixmap(px)
        self._adj_status_label.setText(f"Preview: {w} × {h} px")

    @Slot(str)
    def _on_adj_error(self, msg: str):
        self._adj_status_label.setText(f"Error: {msg}")

    def _adj_rotate_by(self, delta: float):
        current = self._adj_angle_spin.value()
        new_val = (current + delta + 180) % 360 - 180
        self._adj_angle_spin.setValue(new_val)

    def _adj_set_flip(self, h: bool = None, v: bool = None):
        if h is not None:
            self._adj_flip_h = h
        if v is not None:
            self._adj_flip_v = v
        self._adj_schedule_preview()

    def _adj_reset(self):
        for sl, default in [
            (self._adj_temperature, 0),
            (self._adj_tint,        0),
            (self._adj_brightness,  0),
            (self._adj_contrast,    0),
            (self._adj_gamma,       100),
            (self._adj_shadows,     0),
            (self._adj_highlights,  0),
            (self._adj_saturation,  0),
            (self._adj_vibrance,    0),
            (self._adj_hue,         0),
            (self._adj_sharpen,     0),
            (self._adj_blur,        0),
        ]:
            sl.blockSignals(True)
            sl.setValue(default)
            sl.blockSignals(False)

        self._adj_angle_spin.blockSignals(True)
        self._adj_angle_spin.setValue(0.0)
        self._adj_angle_spin.blockSignals(False)

        self._adj_crop_combo.blockSignals(True)
        self._adj_crop_combo.setCurrentIndex(0)
        self._adj_crop_combo.blockSignals(False)

        self._adj_flip_h = False
        self._adj_flip_v = False
        self._btn_flip_h.setChecked(False)
        self._btn_flip_v.setChecked(False)

        self._adj_schedule_preview(None)

    def _adj_save(self):
        if not self._adj_img_path:
            return
        ext = self._adj_img_path.rsplit(".", 1)[-1].lower()
        p, _ = QFileDialog.getSaveFileName(
            self, "Save Adjusted Image", f"adjusted.{ext}",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if not p:
            return
        self._adj_status_label.setText("Saving full-resolution image…")
        worker = AdjustWorker(self._adj_img_path, self._adj_collect_params(), max_size=None)
        thread = QThread(self)
        worker.moveToThread(thread)

        def _on_done(qi: QImage):
            qi.save(p)
            self._adj_status_label.setText(f"Saved: {p}")

        def _on_err(msg: str):
            self._adj_status_label.setText(f"Save error: {msg}")

        thread.started.connect(worker.run)
        worker.sig_finished.connect(_on_done)
        worker.sig_error.connect(_on_err)
        worker.sig_finished.connect(thread.quit)
        worker.sig_error.connect(thread.quit)
        thread.start()

    def _adj_export_to_temp(self) -> Optional[str]:
        """Save the adjusted result to a temp file and return its path."""
        if not self._adj_img_path:
            return None
        tmp = tempfile.NamedTemporaryFile(
            suffix=".png", prefix="adj_", delete=False
        )
        tmp_path = tmp.name
        tmp.close()

        from ....helpers.models.stitch_worker import _apply_adjustments
        try:
            from PIL import Image as _Image
            img = _Image.open(self._adj_img_path)
            result = _apply_adjustments(img, self._adj_collect_params())
            result.save(tmp_path)
            return tmp_path
        except Exception as e:
            self._adj_status_label.setText(f"Export error: {e}")
            return None

    def _adj_send_to_stitch(self):
        tmp_path = self._adj_export_to_temp()
        if not tmp_path:
            return
        if tmp_path not in self._frame_paths:
            self._frame_paths.append(tmp_path)
            item = self._make_frame_item(tmp_path)
            item.setText(f"[adj] {os.path.basename(self._adj_img_path)}")
            self._frame_list.addItem(item)
            self._refresh_pair_combo()
        self._tab_widget.setCurrentIndex(0)

    def _adj_send_to_canvas(self):
        tmp_path = self._adj_export_to_temp()
        if not tmp_path:
            return
        if tmp_path not in self._cv_paths:
            self._cv_paths.append(tmp_path)
            item = self._make_cv_item(tmp_path, f"[adj] {os.path.basename(self._adj_img_path)}")
            self._cv_list.addItem(item)
        self._tab_widget.setCurrentIndex(2)

    # ======================================================================
    # ── Canvas methods ──────────────────────────────────────────────────────
    # ======================================================================

    @Slot(int)
    def _cv_on_preset_changed(self, idx: int):
        _, size = _SIZE_PRESETS[idx]
        if size:
            self._cv_width_spin.blockSignals(True)
            self._cv_height_spin.blockSignals(True)
            self._cv_width_spin.setValue(size[0])
            self._cv_height_spin.setValue(size[1])
            self._cv_width_spin.blockSignals(False)
            self._cv_height_spin.blockSignals(False)

    def _cv_add_images(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Add Images to Canvas", "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp *.tiff *.tif)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        for p in paths:
            if p and p not in self._cv_paths:
                self._cv_paths.append(p)
                self._cv_list.addItem(self._make_cv_item(p))

    def _cv_remove_selected(self):
        for item in reversed(self._cv_list.selectedItems()):
            row = self._cv_list.row(item)
            self._cv_list.takeItem(row)
            if row < len(self._cv_paths):
                self._cv_paths.pop(row)

    def _cv_clear_all(self):
        self._cv_list.clear()
        self._cv_paths.clear()
        self._cv_preview_label.setText("Press 'Preview' to render the canvas.")
        self._cv_status_label.setText("")

    def _cv_sync_paths(self, *_):
        self._cv_paths = [
            self._cv_list.item(r).data(Qt.ItemDataRole.UserRole)
            for r in range(self._cv_list.count())
        ]

    def _cv_pick_bg_color(self):
        initial = QColor(*self._cv_bg_color)
        color = QColorDialog.getColor(
            initial, self, "Background Colour",
            QColorDialog.ColorDialogOption.ShowAlphaChannel,
        )
        if color.isValid():
            self._cv_bg_color = (color.red(), color.green(), color.blue())
            self._cv_update_bg_button()

    def _cv_update_bg_button(self):
        r, g, b = self._cv_bg_color
        self._cv_bg_btn.setStyleSheet(
            f"background-color: rgb({r},{g},{b}); border: 1px solid #555;"
        )
        self._cv_bg_label.setText(f"#{r:02X}{g:02X}{b:02X}")

    def _cv_collect_params(self) -> dict:
        if self._cv_radio_h.isChecked():
            layout = "horizontal"
        elif self._cv_radio_v.isChecked():
            layout = "vertical"
        else:
            layout = "grid"
        return {
            "output_w":   self._cv_width_spin.value(),
            "output_h":   self._cv_height_spin.value(),
            "layout":     layout,
            "grid_cols":  self._cv_cols_spin.value(),
            "gap":        self._cv_gap_spin.value(),
            "bg_color":   self._cv_bg_color,
            "scale_mode": self._cv_scale_combo.currentData(),
        }

    def _cv_run_preview(self):
        if not self._cv_paths:
            QMessageBox.warning(self, "No images", "Add at least one image to the canvas.")
            return
        if self._cv_thread and self._cv_thread.isRunning():
            return

        self._cv_progress.setVisible(True)
        self._cv_status_label.setText("Rendering preview…")
        self._btn_cv_preview.setEnabled(False)
        self._btn_cv_export.setEnabled(False)

        self._cv_worker = CanvasWorker(list(self._cv_paths),
                                       self._cv_collect_params(), preview=True)
        self._cv_thread = QThread(self)
        self._cv_worker.moveToThread(self._cv_thread)
        self._cv_thread.started.connect(self._cv_worker.run)
        self._cv_worker.sig_finished.connect(self._on_cv_preview_ready)
        self._cv_worker.sig_error.connect(self._on_cv_error)
        self._cv_worker.sig_finished.connect(self._cv_thread.quit)
        self._cv_worker.sig_error.connect(self._cv_thread.quit)
        self._cv_thread.finished.connect(self._on_cv_thread_done)
        self._cv_thread.start()

    @Slot(object)
    def _on_cv_preview_ready(self, qi: QImage):
        px = QPixmap.fromImage(qi)
        lw = self._cv_preview_label.width()
        lh = self._cv_preview_label.height()
        px = px.scaled(lw, lh, Qt.AspectRatioMode.KeepAspectRatio,
                       Qt.TransformationMode.SmoothTransformation)
        self._cv_preview_label.setPixmap(px)
        p = self._cv_collect_params()
        self._cv_status_label.setText(
            f"Canvas: {p['output_w']} × {p['output_h']} px  |  "
            f"{len(self._cv_paths)} image(s)"
        )

    @Slot(str)
    def _on_cv_error(self, msg: str):
        self._cv_status_label.setText(f"Error: {msg}")

    def _on_cv_thread_done(self):
        self._cv_progress.setVisible(False)
        self._btn_cv_preview.setEnabled(True)
        self._btn_cv_export.setEnabled(True)

    def _cv_export(self):
        if not self._cv_paths:
            QMessageBox.warning(self, "No images", "Add at least one image to the canvas.")
            return
        fmt = self._cv_export_format.currentData()
        p, _ = QFileDialog.getSaveFileName(
            self, "Export Canvas", f"canvas.{fmt}",
            f"Image (*.{fmt})",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if not p:
            return

        self._cv_progress.setVisible(True)
        self._cv_status_label.setText("Exporting full-resolution canvas…")
        self._btn_cv_preview.setEnabled(False)
        self._btn_cv_export.setEnabled(False)

        worker = CanvasWorker(list(self._cv_paths), self._cv_collect_params(), preview=False)
        thread = QThread(self)
        worker.moveToThread(thread)

        def _on_done(qi: QImage):
            qi.save(p)
            self._cv_status_label.setText(f"Exported: {p}")
            self._cv_progress.setVisible(False)
            self._btn_cv_preview.setEnabled(True)
            self._btn_cv_export.setEnabled(True)
            QMessageBox.information(self, "Export Complete", f"Canvas saved to:\n{p}")

        def _on_err(msg: str):
            self._cv_status_label.setText(f"Export error: {msg}")
            self._cv_progress.setVisible(False)
            self._btn_cv_preview.setEnabled(True)
            self._btn_cv_export.setEnabled(True)

        thread.started.connect(worker.run)
        worker.sig_finished.connect(_on_done)
        worker.sig_error.connect(_on_err)
        worker.sig_finished.connect(thread.quit)
        worker.sig_error.connect(thread.quit)
        thread.start()

    # ======================================================================
    # Settings persistence
    # ======================================================================

    def collect(self) -> dict:
        return {
            # Stitch
            "frame_paths":     list(self._frame_paths),
            "output_path":     self._output_path.text(),
            "use_basic":       self._cb_basic.isChecked(),
            "use_birefnet":    self._cb_birefnet.isChecked(),
            "use_loftr":       self._cb_loftr.isChecked(),
            "use_ecc":         self._cb_ecc.isChecked(),
            "renderer":        self._renderer_combo.currentData(),
            "composite_fg":    self._cb_composite_fg.isChecked(),
            "laplacian_bands": self._bands_spin.value(),
            "stitch_net_ckpt": self._ckpt_path.text(),
            "conf_threshold":  self._conf_thresh_spin.value(),
            # Adjust
            "adj_brightness":  self._adj_brightness.value(),
            "adj_contrast":    self._adj_contrast.value(),
            "adj_gamma":       self._adj_gamma.value(),
            "adj_saturation":  self._adj_saturation.value(),
            "adj_hue":         self._adj_hue.value(),
            "adj_sharpen":     self._adj_sharpen.value(),
            "adj_blur":        self._adj_blur.value(),
            "adj_angle":       self._adj_angle_spin.value(),
            "adj_crop_idx":    self._adj_crop_combo.currentIndex(),
            # Canvas
            "cv_width":        self._cv_width_spin.value(),
            "cv_height":       self._cv_height_spin.value(),
            "cv_layout":       ("horizontal" if self._cv_radio_h.isChecked()
                                else "vertical" if self._cv_radio_v.isChecked()
                                else "grid"),
            "cv_cols":         self._cv_cols_spin.value(),
            "cv_gap":          self._cv_gap_spin.value(),
            "cv_bg_color":     list(self._cv_bg_color),
            "cv_scale_mode":   self._cv_scale_combo.currentData(),
            "cv_paths":        list(self._cv_paths),
        }

    def set_config(self, cfg: dict):
        # Stitch
        if "output_path" in cfg:
            self._output_path.setText(cfg["output_path"])
        if "use_basic" in cfg:
            self._cb_basic.setChecked(cfg["use_basic"])
        if "use_birefnet" in cfg:
            self._cb_birefnet.setChecked(cfg["use_birefnet"])
        if "use_loftr" in cfg:
            self._cb_loftr.setChecked(cfg["use_loftr"])
        if "use_ecc" in cfg:
            self._cb_ecc.setChecked(cfg["use_ecc"])
        if "renderer" in cfg:
            idx = self._renderer_combo.findData(cfg["renderer"])
            if idx >= 0:
                self._renderer_combo.setCurrentIndex(idx)
        if "composite_fg" in cfg:
            self._cb_composite_fg.setChecked(cfg["composite_fg"])
        if "laplacian_bands" in cfg:
            self._bands_spin.setValue(cfg["laplacian_bands"])
        if "stitch_net_ckpt" in cfg:
            self._ckpt_path.setText(cfg["stitch_net_ckpt"])
        if "conf_threshold" in cfg:
            self._conf_thresh_spin.setValue(cfg["conf_threshold"])
        if "frame_paths" in cfg:
            for p in cfg["frame_paths"]:
                if p and os.path.isfile(p) and p not in self._frame_paths:
                    self._frame_paths.append(p)
                    self._frame_list.addItem(self._make_frame_item(p))
            self._refresh_pair_combo()
        # Adjust
        for key, sl in [
            ("adj_brightness", self._adj_brightness),
            ("adj_contrast",   self._adj_contrast),
            ("adj_gamma",      self._adj_gamma),
            ("adj_saturation", self._adj_saturation),
            ("adj_hue",        self._adj_hue),
            ("adj_sharpen",    self._adj_sharpen),
            ("adj_blur",       self._adj_blur),
        ]:
            if key in cfg:
                sl.setValue(cfg[key])
        if "adj_angle" in cfg:
            self._adj_angle_spin.setValue(cfg["adj_angle"])
        if "adj_crop_idx" in cfg:
            self._adj_crop_combo.setCurrentIndex(cfg["adj_crop_idx"])
        # Canvas
        if "cv_width" in cfg:
            self._cv_width_spin.setValue(cfg["cv_width"])
        if "cv_height" in cfg:
            self._cv_height_spin.setValue(cfg["cv_height"])
        if "cv_layout" in cfg:
            layout = cfg["cv_layout"]
            if layout == "horizontal":
                self._cv_radio_h.setChecked(True)
            elif layout == "vertical":
                self._cv_radio_v.setChecked(True)
            else:
                self._cv_radio_g.setChecked(True)
        if "cv_cols" in cfg:
            self._cv_cols_spin.setValue(cfg["cv_cols"])
        if "cv_gap" in cfg:
            self._cv_gap_spin.setValue(cfg["cv_gap"])
        if "cv_bg_color" in cfg:
            self._cv_bg_color = tuple(cfg["cv_bg_color"])
            self._cv_update_bg_button()
        if "cv_scale_mode" in cfg:
            idx = self._cv_scale_combo.findData(cfg["cv_scale_mode"])
            if idx >= 0:
                self._cv_scale_combo.setCurrentIndex(idx)
        if "cv_paths" in cfg:
            for p in cfg["cv_paths"]:
                if p and os.path.isfile(p) and p not in self._cv_paths:
                    self._cv_paths.append(p)
                    self._cv_list.addItem(self._make_cv_item(p))

    def get_default_config(self) -> dict:
        return self.collect()


    def _auto_order_sequence(self):
        """Reorder the stitch queue using the longest-coherent-path algorithm."""
        if not self._frame_paths:
            return

        ref_idx = self._frame_list.currentRow()
        if ref_idx < 0: ref_idx = 0
        ref_path = self._frame_paths[ref_idx]
        
        self.setCursor(Qt.CursorShape.WaitCursor)
        try:
            # We treat the currently loaded frames as the candidate pool
            new_order = AnimeStitchPipeline.find_optimal_sequence(
                ref_path, 
                self._frame_paths,
                min_inliers=25
            )
            
            if not new_order:
                QMessageBox.warning(self, "Order Optimizer", "No coherent matches found for the selected frame.")
                return

            # Update state
            self._frame_paths = new_order
            
            # Refresh list
            self._frame_list.clear()
            for p in self._frame_paths:
                self._frame_list.addItem(os.path.basename(p))
            
            # Select the original reference in the new list
            try:
                new_ref_idx = self._frame_paths.index(ref_path)
                self._frame_list.setCurrentRow(new_ref_idx)
            except ValueError: pass
            
            QMessageBox.information(self, "Order Optimizer", 
                f"Reordered {len(new_order)} coherent frames.\n"
                f"Sequence length optimized for continuity.")
                
        except Exception as e:
            QMessageBox.critical(self, "Order Optimizer Error", str(e))
        finally:
            self.setCursor(Qt.CursorShape.ArrowCursor)


    # ======================================================================
    # ── SUB-TAB 5: Statistics ─────────────────────────────────────────────
    # ======================================================================

    def _build_stats_panel(self) -> QWidget:
        panel = QWidget()
        root = QVBoxLayout(panel)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # ── Source selector ───────────────────────────────────────────
        src_group = QGroupBox("Image Source")
        src_layout = QHBoxLayout(src_group)

        self._stats_use_frames_btn = QPushButton("Use Stitch Frame List")
        self._stats_use_frames_btn.setToolTip(
            "Analyse the images currently loaded in the Stitch tab."
        )
        self._stats_use_frames_btn.clicked.connect(self._stats_load_from_frames)
        src_layout.addWidget(self._stats_use_frames_btn)

        src_layout.addWidget(QLabel("  or  "))

        self._stats_dir_edit = QLineEdit()
        self._stats_dir_edit.setPlaceholderText("Select a directory of images…")
        self._stats_dir_edit.setReadOnly(True)
        src_layout.addWidget(self._stats_dir_edit, 1)

        btn_browse_stats = QPushButton("Browse…")
        btn_browse_stats.clicked.connect(self._stats_browse_dir)
        src_layout.addWidget(btn_browse_stats)

        root.addWidget(src_group)

        # ── Run button + progress ─────────────────────────────────────
        run_row = QHBoxLayout()
        self._stats_run_btn = QPushButton("Compute Statistics")
        self._stats_run_btn.setStyleSheet(
            "background:#1976D2; color:white; font-weight:bold; padding:5px 14px;"
        )
        self._stats_run_btn.clicked.connect(self._stats_run)
        run_row.addWidget(self._stats_run_btn)

        run_row.addWidget(QLabel("K neighbors:"))
        self._stats_knn_spin = QSpinBox()
        self._stats_knn_spin.setRange(1, 100)
        self._stats_knn_spin.setValue(20)
        self._stats_knn_spin.setToolTip(
            "When a consecutive pair scores below the weak threshold, also compare each "
            "frame against the K nearest frames ahead/behind it to find better matches.\n"
            "Higher values catch periodic pose repetitions further apart (e.g. every 20 frames) "
            "but increase compute time."
        )
        run_row.addWidget(self._stats_knn_spin)

        self._stats_progress = QProgressBar()
        self._stats_progress.setRange(0, 100)
        self._stats_progress.setValue(0)
        self._stats_progress.setTextVisible(True)
        self._stats_progress.hide()
        run_row.addWidget(self._stats_progress, 1)

        self._stats_status = QLabel("")
        self._stats_status.setStyleSheet("color:#aaa; font-style:italic;")
        run_row.addWidget(self._stats_status)
        root.addLayout(run_row)

        # ── Per-image table ───────────────────────────────────────────
        ind_group = QGroupBox("Per-Image Metrics")
        ind_layout = QVBoxLayout(ind_group)

        _IND_COLS = [
            ("Image",        "name"),
            ("W",            "width"),
            ("H",            "height"),
            ("Aspect",       "aspect_ratio"),
            ("Brightness",   "brightness"),
            ("Contrast",     "contrast"),
            ("Sharpness",    "sharpness"),
            ("Noise",        "noise"),
            ("Saturation",   "saturation"),
            ("Dom. Hue °",   "dominant_hue"),
            ("Size (KB)",    "file_size_kb"),
        ]
        self._stats_ind_cols = _IND_COLS

        self._stats_ind_table = QTableWidget(0, len(_IND_COLS))
        self._stats_ind_table.setHorizontalHeaderLabels([c[0] for c in _IND_COLS])
        self._stats_ind_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        for col in range(1, len(_IND_COLS)):
            self._stats_ind_table.horizontalHeader().setSectionResizeMode(
                col, QHeaderView.ResizeMode.ResizeToContents
            )
        self._stats_ind_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._stats_ind_table.setAlternatingRowColors(True)
        self._stats_ind_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self._stats_ind_table.verticalHeader().setVisible(False)
        self._stats_ind_table.verticalHeader().setDefaultSectionSize(52)
        self._stats_ind_table.setIconSize(QSize(48, 48))
        self._stats_ind_table.setMinimumHeight(220)
        self._stats_ind_table.setStyleSheet(
            "QTableWidget { background:#2c2f33; alternate-background-color:#36393f; }"
            "QHeaderView::section { background:#1e1f22; color:#ccc; padding:4px; }"
        )
        ind_layout.addWidget(self._stats_ind_table)

        # ── Summary row beneath individual table ──────────────────────
        self._stats_ind_summary = QLabel("")
        self._stats_ind_summary.setStyleSheet("color:#aaa; font-size:10px; padding:2px 0;")
        ind_layout.addWidget(self._stats_ind_summary)

        root.addWidget(ind_group)

        # ── Pairwise table ────────────────────────────────────────────
        pw_group = QGroupBox("Pairwise Correlation Metrics")
        pw_layout = QVBoxLayout(pw_group)

        _PW_COLS = [
            ("Frame A",       "name_a"),
            ("Frame B",       "name_b"),
            ("Hist. Corr.",   "hist_corr"),
            ("SSIM",          "ssim"),
            ("ORB Inliers",   "orb_inliers"),
            ("Mean Diff",     "mean_diff"),
            ("Stitch Score",  "_score"),
        ]
        self._stats_pw_cols = _PW_COLS

        self._stats_pw_table = QTableWidget(0, len(_PW_COLS))
        self._stats_pw_table.setHorizontalHeaderLabels([c[0] for c in _PW_COLS])
        for col in range(2):
            self._stats_pw_table.horizontalHeader().setSectionResizeMode(
                col, QHeaderView.ResizeMode.Stretch
            )
        for col in range(2, len(_PW_COLS)):
            self._stats_pw_table.horizontalHeader().setSectionResizeMode(
                col, QHeaderView.ResizeMode.ResizeToContents
            )
        self._stats_pw_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._stats_pw_table.setAlternatingRowColors(True)
        self._stats_pw_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self._stats_pw_table.verticalHeader().setVisible(False)
        self._stats_pw_table.verticalHeader().setDefaultSectionSize(52)
        self._stats_pw_table.setIconSize(QSize(48, 48))
        self._stats_pw_table.setMinimumHeight(200)
        self._stats_pw_table.setStyleSheet(
            "QTableWidget { background:#2c2f33; alternate-background-color:#36393f; }"
            "QHeaderView::section { background:#1e1f22; color:#ccc; padding:4px; }"
        )
        pw_layout.addWidget(self._stats_pw_table)

        self._stats_pw_legend = QLabel(
            "Stitch Score = 0.4 × ORB inliers (norm.) + 0.4 × SSIM + 0.2 × Hist. Corr.  "
            "Higher is better.  Colour: green ≥ 0.6 · yellow ≥ 0.35 · red < 0.35"
        )
        self._stats_pw_legend.setStyleSheet("color:#888; font-size:10px; padding:2px 0;")
        self._stats_pw_legend.setWordWrap(True)
        pw_layout.addWidget(self._stats_pw_legend)

        root.addWidget(pw_group)

        # ── Recommendations ───────────────────────────────────────────
        rec_group = QGroupBox("Stitching Recommendations")
        rec_layout = QVBoxLayout(rec_group)

        self._stats_rec_edit = QTextEdit()
        self._stats_rec_edit.setReadOnly(True)
        self._stats_rec_edit.setMinimumHeight(240)
        self._stats_rec_edit.setPlaceholderText(
            "Run 'Compute Statistics' to generate scenario-based stitching recommendations."
        )
        self._stats_rec_edit.setStyleSheet(
            "QTextEdit { background:#1e1f22; color:#d4d4d4; "
            "border:1px solid #4f545c; border-radius:4px; "
            "font-family: monospace; font-size: 11px; padding: 6px; }"
        )
        rec_layout.addWidget(self._stats_rec_edit)

        root.addWidget(rec_group)

        return panel

    # ── Stats slots ────────────────────────────────────────────────────────

    @Slot()
    def _stats_load_from_frames(self):
        if not self._frame_paths:
            QMessageBox.information(self, "Statistics",
                                    "No frames loaded in the Stitch tab.")
            return
        self._stats_dir_edit.clear()
        self._stats_dir_path = ""
        self._stats_do_run(list(self._frame_paths))

    @Slot()
    def _stats_browse_dir(self):
        start = self._stats_dir_path or (
            os.path.dirname(self._frame_paths[-1]) if self._frame_paths else ""
        )
        d = QFileDialog.getExistingDirectory(
            self, "Select Image Directory", start,
            QFileDialog.Option.DontUseNativeDialog
        )
        if not d:
            return
        self._stats_dir_path = d
        self._stats_dir_edit.setText(d)

    @Slot()
    def _stats_run(self):
        if self._stats_dir_path:
            exts = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tiff", ".tif"}
            paths = sorted(
                str(p) for p in __import__("pathlib").Path(self._stats_dir_path).iterdir()
                if p.is_file() and p.suffix.lower() in exts
            )
            if not paths:
                QMessageBox.information(self, "Statistics",
                                        "No image files found in the selected directory.")
                return
            self._stats_do_run(paths)
        else:
            self._stats_load_from_frames()

    def _stats_do_run(self, paths: List[str]):
        if not paths:
            return

        # Cancel any running worker
        if self._stats_worker is not None:
            self._stats_worker.cancel()
            self._stats_worker = None

        self._stats_ind_rows: List[dict] = []
        self._stats_ind_table.setRowCount(0)
        self._stats_pw_table.setRowCount(0)
        self._stats_ind_summary.setText("")
        self._stats_rec_edit.clear()
        self._stats_progress.setValue(0)
        self._stats_progress.show()
        self._stats_status.setText(f"Analysing {len(paths)} images…")
        self._stats_run_btn.setEnabled(False)

        worker = StatsWorker(paths, knn_window=self._stats_knn_spin.value())
        self._stats_worker = worker
        worker.signals.progress.connect(self._stats_on_progress)
        worker.signals.individual_done.connect(self._stats_on_individual)
        worker.signals.pairwise_done.connect(self._stats_on_pairwise)
        worker.signals.error.connect(self._stats_on_error)
        QThreadPool.globalInstance().start(worker)

    @Slot(int)
    def _stats_on_progress(self, pct: int):
        self._stats_progress.setValue(pct)

    @Slot(list)
    def _stats_on_individual(self, rows: List[dict]):
        self._stats_ind_rows = rows
        table = self._stats_ind_table
        table.setRowCount(len(rows))
        cols = self._stats_ind_cols

        self._stats_ind_item_map.clear()
        for r, row in enumerate(rows):
            for c, (_, key) in enumerate(cols):
                val = row.get(key, "")
                item = QTableWidgetItem(str(val) if val != -1 else "achromatic")
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    if c > 0 else
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                )
                if c == 0:
                    full_path = row.get("path", "")
                    if full_path:
                        item.setData(Qt.ItemDataRole.UserRole, full_path)
                        self._stats_ind_item_map[full_path] = item
                        QThreadPool.globalInstance().start(
                            _ThumbTask(full_path, 48, 0, self._stats_ind_thumb_hub)
                        )

                # Colour-code sharpness column relatively (bottom 15% red,
                # top 40% green) so flat anime content isn't penalised.
                if key == "sharpness":
                    all_sharp = [float(rr.get("sharpness", 0)) for rr in rows]
                    p15 = float(np.percentile(all_sharp, 15))
                    p60 = float(np.percentile(all_sharp, 60))
                    v = float(val) if val else 0.0
                    if v >= p60:
                        item.setForeground(QColor("#4CAF50"))
                    elif v >= p15:
                        item.setForeground(QColor("#FFC107"))
                    else:
                        item.setForeground(QColor("#f44336"))

                # Colour-code noise column (index 7): lower is better
                if key == "noise":
                    v = float(val) if val else 0.0
                    if v <= 5:
                        item.setForeground(QColor("#4CAF50"))
                    elif v <= 15:
                        item.setForeground(QColor("#FFC107"))
                    else:
                        item.setForeground(QColor("#f44336"))

                table.setItem(r, c, item)

        # Summary line
        if rows:
            avg_sharp = np.mean([r.get("sharpness", 0) for r in rows])
            avg_bright = np.mean([r.get("brightness", 0) for r in rows])
            avg_contrast = np.mean([r.get("contrast", 0) for r in rows])
            resolutions = set(f"{r['width']}×{r['height']}" for r in rows if r.get("width"))
            res_str = ", ".join(sorted(resolutions)) if len(resolutions) <= 3 else f"{len(resolutions)} different"
            self._stats_ind_summary.setText(
                f"Count: {len(rows)}  |  Resolutions: {res_str}  |  "
                f"Avg brightness: {avg_bright:.1f}  |  "
                f"Avg contrast: {avg_contrast:.1f}  |  "
                f"Avg sharpness: {avg_sharp:.1f}"
            )

    @Slot(list)
    def _stats_on_pairwise(self, rows: List[dict]):
        table = self._stats_pw_table
        table.setRowCount(len(rows))
        cols = self._stats_pw_cols

        # Normalise ORB inliers across all rows for score
        max_orb = max((r.get("orb_inliers", 0) for r in rows), default=1) or 1

        self._stats_pw_item_map_a.clear()
        self._stats_pw_item_map_b.clear()
        for r, row in enumerate(rows):
            orb_norm = row.get("orb_inliers", 0) / max_orb
            ssim_val = max(0.0, float(row.get("ssim", 0)))
            hist_val = max(0.0, float(row.get("hist_corr", 0)))
            score = round(0.4 * orb_norm + 0.4 * ssim_val + 0.2 * hist_val, 3)
            row["_score"] = score

            for c, (_, key) in enumerate(cols):
                val = row.get(key, "")
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    if c >= 2 else
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                )
                if c == 0:
                    full_path = row.get("path_a", "")
                    if full_path:
                        item.setData(Qt.ItemDataRole.UserRole, full_path)
                        self._stats_pw_item_map_a[full_path] = item
                        QThreadPool.globalInstance().start(
                            _ThumbTask(full_path, 48, 0, self._stats_pw_thumb_hub_a)
                        )
                elif c == 1:
                    full_path = row.get("path_b", "")
                    if full_path:
                        item.setData(Qt.ItemDataRole.UserRole, full_path)
                        self._stats_pw_item_map_b[full_path] = item
                        QThreadPool.globalInstance().start(
                            _ThumbTask(full_path, 48, 0, self._stats_pw_thumb_hub_b)
                        )

                # Colour-code the Stitch Score column
                if key == "_score":
                    if score >= 0.6:
                        item.setForeground(QColor("#4CAF50"))
                        item.setBackground(QColor("#1b3a1f"))
                    elif score >= 0.35:
                        item.setForeground(QColor("#FFC107"))
                        item.setBackground(QColor("#3a3000"))
                    else:
                        item.setForeground(QColor("#f44336"))
                        item.setBackground(QColor("#3a1010"))

                table.setItem(r, c, item)

        self._stats_progress.hide()
        self._stats_status.setText(
            f"Done. {len(rows)} pair(s) analysed."
        )
        self._stats_run_btn.setEnabled(True)
        self._stats_worker = None

        ind_rows = getattr(self, "_stats_ind_rows", [])
        self._stats_rec_edit.setHtml(
            self._stats_build_recommendations(ind_rows, rows, max_orb)
        )

    # ------------------------------------------------------------------
    @staticmethod
    def _stats_build_recommendations(
        ind: List[dict], pw: List[dict], max_orb: int  # noqa: ARG004
    ) -> str:
        """
        Analyse per-image and pairwise metrics and produce scenario-based
        stitching recommendations as an HTML string for display in QTextEdit.
        """
        n = len(ind)
        if n == 0:
            return "<p style='color:#888'>No data to analyse.</p>"

        # ── Derived aggregates ─────────────────────────────────────────
        sharpnesses   = [float(r.get("sharpness",   0)) for r in ind]
        noises        = [float(r.get("noise",        0)) for r in ind]
        brightnesses  = [float(r.get("brightness",   0)) for r in ind]
        saturations   = [float(r.get("saturation",   0)) for r in ind]
        widths        = [int(r.get("width",   0)) for r in ind]
        heights       = [int(r.get("height",  0)) for r in ind]
        file_sizes_kb = [float(r.get("file_size_kb", 0)) for r in ind]

        avg_sharp     = float(np.mean(sharpnesses))
        std_sharp     = float(np.std(sharpnesses))
        avg_noise     = float(np.mean(noises))
        avg_bright    = float(np.mean(brightnesses))
        bright_range  = float(np.max(brightnesses) - np.min(brightnesses))
        avg_sat       = float(np.mean(saturations))
        max_w         = max(widths)  if widths  else 0
        max_h         = max(heights) if heights else 0
        res_uniform   = len(set(zip(widths, heights))) == 1
        total_mb      = sum(file_sizes_kb) / 1024

        # Pairwise aggregates — use consecutive pairs only for summary metrics
        # so the K-window extended pairs don't skew the quality verdict.
        _consec_pw = [r for r in pw if r.get("consecutive", True)] if pw else []
        _consec_pw = _consec_pw or (pw or [])  # fallback if flag absent
        scores   = [float(r.get("_score",     0)) for r in _consec_pw]
        ssims    = [float(r.get("ssim",       0)) for r in _consec_pw]
        orb_vals = [int(r.get("orb_inliers",  0)) for r in _consec_pw]

        avg_score    = float(np.mean(scores))    if scores    else 0.0
        avg_ssim     = float(np.mean(ssims))     if ssims     else 0.0
        avg_orb      = float(np.mean(orb_vals))  if orb_vals  else 0.0

        consec_pairs  = [r for r in pw if r.get("consecutive", True)]
        consec_scores = [float(r.get("_score", 0)) for r in consec_pairs]
        weak_pairs    = [consec_pairs[i] for i, s in enumerate(consec_scores) if s < 0.35]
        dup_pairs     = [consec_pairs[i] for i, s in enumerate(consec_scores) if s > 0.92]
        n_weak        = len(weak_pairs)
        n_dup         = len(dup_pairs)

        # For each weak consecutive pair, check if any extended-window pair
        # involving either frame scores significantly better.
        extended_pairs = [r for r in pw if not r.get("consecutive", True)]
        better_matches: List[dict] = []  # {weak_a, weak_b, best_a, best_b, score_orig, score_best}
        for wp in weak_pairs:
            orig_score = float(wp.get("_score", 0))
            ia, ib = wp["idx_a"], wp["idx_b"]
            candidates = [
                r for r in extended_pairs
                if r["idx_a"] == ia or r["idx_b"] == ib
                   or r["idx_a"] == ib or r["idx_b"] == ia
            ]
            if not candidates:
                continue
            best_ext = max(candidates, key=lambda r: float(r.get("_score", 0)))
            best_score = float(best_ext.get("_score", 0))
            if best_score > orig_score + 0.10:  # only report meaningful improvement
                better_matches.append({
                    "weak_a": wp["name_a"], "weak_b": wp["name_b"],
                    "best_a": best_ext["name_a"], "best_b": best_ext["name_b"],
                    "score_orig": orig_score, "score_best": best_score,
                    "gap": abs(best_ext["idx_b"] - best_ext["idx_a"]),
                })

        # ── Observations (shared facts) ────────────────────────────────
        obs: List[str] = []

        # ── Sharpness — relative to the batch, not absolute ──────────────
        # Digital anime / cel-shading has low Laplacian variance by design
        # (flat colour fills, no film grain).  We use the batch's own
        # distribution so the verdict is always content-appropriate.
        sharp_cv = std_sharp / avg_sharp if avg_sharp > 0 else 0.0  # coefficient of variation

        if sharp_cv < 0.25:
            # Frames are very uniform in sharpness — describe the batch level
            # relative to typical photographic expectations, but without
            # labelling anime as "blurry" just because its absolute values
            # are low (which is normal for cel-shaded content).
            obs.append(
                f"✔ Sharpness is <b>consistent</b> across all frames "
                f"(avg Laplacian variance {avg_sharp:.0f}, CV {sharp_cv:.2f}).  "
                "This is normal for digital anime / cel-shaded content — "
                "flat colour fills inherently produce low Laplacian values."
            )
        else:
            obs.append(
                f"○ Sharpness varies across frames "
                f"(avg {avg_sharp:.0f} ± {std_sharp:.0f}).  "
                "Some frames may be motion-blurred or out-of-focus."
            )

        # Flag genuine outliers: frames more than 2σ below the mean AND
        # at least 30% softer than the mean (prevents false positives when
        # the whole batch is a tight cluster, e.g. uniform anime content).
        # Never recommend removing more than n-2 frames (must keep ≥ 2).
        if n > 2 and std_sharp > 0:
            two_sigma_thresh = avg_sharp - 2.0 * std_sharp
            thirty_pct_thresh = avg_sharp * 0.70
            outlier_thresh = max(two_sigma_thresh, thirty_pct_thresh)
            blurry_outliers = [
                ind[i]["name"] for i, v in enumerate(sharpnesses)
                if v < outlier_thresh
            ]
            # Hard cap: never suggest removing so many frames stitching breaks
            max_removable = max(0, n - 2)
            blurry_outliers = blurry_outliers[:max_removable]
            if blurry_outliers:
                obs.append(
                    f"⚠ {len(blurry_outliers)} frame(s) are significantly softer "
                    f"than the rest of the batch (>2σ below average): "
                    f"<i>{', '.join(blurry_outliers[:4])}"
                    f"{'…' if len(blurry_outliers) > 4 else ''}</i>.  "
                    "These may be motion-blurred transitions — consider removing them."
                )

        # Noise
        if avg_noise > 15:
            obs.append(f"⚠ High average noise ({avg_noise:.1f}).  "
                       "Pre-denoising (e.g. Gaussian or bilateral filter) is recommended.")
        elif avg_noise > 5:
            obs.append(f"○ Mild noise ({avg_noise:.1f}).  "
                       "Optional light denoising before high-quality stitching.")

        # Brightness / exposure
        if bright_range > 60:
            obs.append(f"⚠ <b>Large brightness variation</b> across frames "
                       f"(range {bright_range:.0f}).  "
                       "Exposure normalisation is strongly recommended before stitching "
                       "to avoid seam-line banding.")
        elif bright_range > 30:
            obs.append(f"○ Moderate brightness spread ({bright_range:.0f}).  "
                       "Histogram matching between adjacent pairs will improve seam quality.")

        if avg_bright < 60:
            obs.append("⚠ Frames are <b>underexposed</b>.  "
                       "Gamma correction or CLAHE may improve feature detection.")
        elif avg_bright > 200:
            obs.append("⚠ Frames are <b>overexposed</b>.  "
                       "Tone-map or reduce brightness to recover detail before stitching.")

        # Resolution uniformity
        if not res_uniform:
            obs.append("⚠ Frames have <b>inconsistent resolutions</b>.  "
                       "Resize all frames to a common resolution before stitching "
                       "to avoid projection errors.")
        else:
            obs.append(f"✔ All frames share the same resolution ({max_w}×{max_h}).")

        # Saturation / colour
        if avg_sat < 30:
            obs.append("○ Frames appear mostly desaturated.  "
                       "Histogram correlation will be less discriminative; "
                       "rely on structural matchers (LoFTR/ORB).")

        # Pairwise quality
        if pw:
            if avg_score >= 0.65:
                obs.append(f"✔ Pair match quality is <b>strong</b> "
                           f"(avg stitch score {avg_score:.2f}).  "
                           "Direct stitching is likely to succeed.")
            elif avg_score >= 0.40:
                obs.append(f"○ Pair match quality is <b>acceptable</b> "
                           f"(avg stitch score {avg_score:.2f}).  "
                           "Light pre-processing will improve results.")
            else:
                obs.append(f"⚠ Pair match quality is <b>weak</b> "
                           f"(avg stitch score {avg_score:.2f}).  "
                           "Significant pre-processing or manual alignment may be required.")

            if n_weak:
                names_w = [f"{p['name_a']}↔{p['name_b']}" for p in weak_pairs[:3]]
                obs.append(f"⚠ {n_weak} weak consecutive pair(s) detected: "
                           f"<i>{', '.join(names_w)}"
                           f"{'…' if n_weak > 3 else ''}</i>.  "
                           "These transitions may produce visible seams or misalignments.")

            if better_matches:
                for bm in better_matches[:5]:
                    obs.append(
                        f"💡 Weak pair <i>{bm['weak_a']}↔{bm['weak_b']}</i> "
                        f"(score {bm['score_orig']:.3f}) has a better non-adjacent match: "
                        f"<b>{bm['best_a']}↔{bm['best_b']}</b> "
                        f"(score <b>{bm['score_best']:.3f}</b>, gap {bm['gap']} frame(s)).  "
                        "Consider replacing the weak pair with this one or skipping intermediate frames."
                    )
                if len(better_matches) > 5:
                    obs.append(
                        f"… and {len(better_matches) - 5} more weak pair(s) with better "
                        "non-adjacent alternatives (see table)."
                    )

            if n_dup:
                names_d = [f"{p['name_a']}↔{p['name_b']}" for p in dup_pairs[:3]]
                obs.append(f"⚠ {n_dup} near-duplicate pair(s) detected: "
                           f"<i>{', '.join(names_d)}</i>.  "
                           "Redundant frames add compute cost without improving coverage — "
                           "consider removing one from each duplicate pair.")

        # Memory / size
        if total_mb > 500:
            obs.append(f"⚠ Total uncompressed data is large (~{total_mb:.0f} MB).  "
                       "Downscale frames before stitching unless maximum output resolution "
                       "is required.")

        # ── Scenario recommendations ───────────────────────────────────
        def _section(title: str, color: str, items: List[str]) -> str:
            bullets = "".join(f"<li>{it}</li>" for it in items)
            return (
                f"<div style='margin-top:10px;'>"
                f"<span style='background:{color};color:#fff;"
                f"font-weight:bold;padding:2px 8px;border-radius:3px;'>"
                f"{title}</span>"
                f"<ul style='margin:4px 0 0 16px;padding:0;'>{bullets}</ul>"
                f"</div>"
            )

        best_items: List[str] = []
        balanced_items: List[str] = []
        fast_items: List[str] = []

        # Resolution advice
        if max_w > 0:
            best_items.append(
                f"Use <b>full native resolution</b> ({max_w}×{max_h}) throughout."
            )
            half_w, half_h = max_w // 2, max_h // 2
            balanced_items.append(
                f"Use <b>½ resolution</b> ({half_w}×{half_h}) for stitching, "
                f"then upscale the result."
            )
            q_w, q_h = max_w // 4, max_h // 4
            fast_items.append(
                f"Downscale to <b>¼ resolution</b> ({q_w}×{q_h}) for a rapid prototype."
            )

        # Pre-processing
        if avg_noise > 5:
            best_items.append(
                "Apply <b>bilateral denoising</b> (preserve edges) before matching."
            )
            balanced_items.append(
                "Apply a <b>light Gaussian blur</b> (σ=0.8) to suppress noise."
            )
            fast_items.append("Skip denoising — accept minor artefacts.")

        if bright_range > 30:
            best_items.append(
                "Run <b>per-frame exposure normalisation</b> (CLAHE or histogram matching) "
                "before stitching, then gain-compensate during blending."
            )
            balanced_items.append(
                "Apply <b>histogram matching</b> between consecutive frame pairs."
            )
            fast_items.append(
                "Use a simple <b>global mean-brightness normalisation</b>."
            )

        # Feature matching — decide based on whether outliers exist, not
        # on absolute sharpness (which is content-type dependent).
        has_blur_outliers = (n > 2 and std_sharp > 0 and
                             (avg_sharp - 2.0 * std_sharp) > float(np.percentile(sharpnesses, 10)))
        if has_blur_outliers and sharp_cv >= 0.25:
            best_items.append(
                "Use <b>LoFTR</b> (transformer-based) matching — it handles "
                "motion-blurred frames far better than ORB."
            )
            balanced_items.append(
                "Use <b>LoFTR</b> with a reduced tile size to save memory."
            )
            fast_items.append(
                "Use <b>ORB + BFMatcher</b> — fast, but expect fewer inliers "
                "on the blurry outlier frames."
            )
        else:
            best_items.append(
                "Use <b>LoFTR</b> for maximum correspondence quality."
            )
            balanced_items.append(
                "Use <b>LoFTR</b> or SIFT — sharpness is consistent across "
                "the batch, both will work well."
            )
            fast_items.append(
                "Use <b>ORB + BFMatcher</b> — sharpness is uniform, "
                "ORB inlier counts will be reliable."
            )

        # Homography / warp
        if avg_orb > 80 or (avg_ssim > 0.7 and avg_orb > 40):
            best_items.append(
                "Estimate a full <b>homography</b> (8-DOF perspective) per pair — "
                "feature density supports it."
            )
            balanced_items.append(
                "Use an <b>affine</b> warp (6-DOF) for speed while retaining most accuracy."
            )
        else:
            best_items.append(
                "Use <b>affine + RANSAC</b> warp — feature count may be too low "
                "for reliable homography estimation."
            )
            balanced_items.append(
                "Use <b>affine</b> warp with a relaxed RANSAC threshold (8–10 px)."
            )
        fast_items.append(
            "Use a <b>translation-only</b> alignment (fast, sufficient for roughly "
            "pre-aligned frames)."
        )

        # Blending
        best_items.append(
            "Use <b>multi-band blending</b> (Laplacian pyramid, 5–6 levels) "
            "for seamless transitions."
        )
        if n_weak:
            best_items.append(
                f"Manually verify / override affine for the {n_weak} weak pair(s) "
                "before blending."
            )
        balanced_items.append(
            "Use <b>linear feathering</b> (alpha blend) across a 20–40 px overlap zone."
        )
        fast_items.append(
            "Use a <b>hard cut</b> at the midpoint of the overlap — no blending."
        )

        # Output format
        best_items.append(
            "Save as <b>PNG</b> (lossless) or 16-bit TIFF for archival quality."
        )
        balanced_items.append(
            "Save as <b>JPEG quality 92–95</b> for a good size/quality trade-off."
        )
        fast_items.append(
            "Save as <b>JPEG quality 80</b> or WebP for minimal disk footprint."
        )

        # Frame count / compute note
        if n >= 8:
            best_items.append(
                f"With {n} frames, consider enabling the <b>graph-based stitcher</b> "
                "(Graph tab) to find the globally optimal stitch order."
            )
            balanced_items.append(
                f"With {n} frames, use <b>Auto-Order</b> to optimise frame sequence "
                "before stitching."
            )
            fast_items.append(
                f"Limit the fast prototype to the <b>highest-scoring {min(n, 4)} frames</b> "
                "to keep runtime under a few seconds."
            )

        if n_dup:
            best_items.append(
                f"Remove {n_dup} near-duplicate frame(s) to avoid redundant blending "
                "and output ghosting."
            )
            balanced_items.append(
                f"Remove {n_dup} near-duplicate frame(s) before stitching."
            )
            fast_items.append(
                "Skip duplicate frames entirely."
            )

        # ── Assemble HTML ──────────────────────────────────────────────
        obs_html = "".join(
            f"<li style='margin-bottom:2px;'>{o}</li>" for o in obs
        )

        html = (
            "<html><body style='font-family:sans-serif;font-size:11px;"
            "color:#d4d4d4;background:#1e1f22;'>"
            "<p style='font-weight:bold;font-size:12px;margin:0 0 4px;'>"
            "Observations</p>"
            f"<ul style='margin:0 0 6px 16px;padding:0;'>{obs_html}</ul>"
            "<hr style='border:1px solid #4f545c;margin:8px 0;'/>"
            "<p style='font-weight:bold;font-size:12px;margin:0 0 2px;'>"
            "Scenario Recommendations</p>"
        )
        html += _section("Best Quality",    "#1976D2", best_items)
        html += _section("Balanced",        "#388E3C", balanced_items)
        html += _section("Fast / Prototype","#F57C00", fast_items)
        html += "</body></html>"
        return html

    @Slot(str)
    def _stats_on_error(self, msg: str):
        self._stats_progress.hide()
        self._stats_status.setText("Error.")
        self._stats_run_btn.setEnabled(True)
        self._stats_worker = None
        QMessageBox.critical(self, "Statistics Error", msg)

    # ======================================================================
    # ── SUB-TAB 8: Animation Clusters ─────────────────────────────────────
    # ======================================================================

    def _build_anim_clusters_panel(self) -> QWidget:
        panel = QWidget()
        root = QVBoxLayout(panel)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # ── Source selector ───────────────────────────────────────────
        src_group = QGroupBox("Image Source")
        src_layout = QHBoxLayout(src_group)

        self._anim_use_frames_btn = QPushButton("Use Stitch Frame List")
        self._anim_use_frames_btn.setToolTip(
            "Analyse the images currently loaded in the Stitch tab."
        )
        self._anim_use_frames_btn.clicked.connect(self._anim_load_from_frames)
        src_layout.addWidget(self._anim_use_frames_btn)

        src_layout.addWidget(QLabel("  or  "))

        self._anim_files_edit = QLineEdit()
        self._anim_files_edit.setPlaceholderText("Select individual files or a directory…")
        self._anim_files_edit.setReadOnly(True)
        src_layout.addWidget(self._anim_files_edit, 1)

        btn_browse_files = QPushButton("Files…")
        btn_browse_files.clicked.connect(self._anim_browse_files)
        src_layout.addWidget(btn_browse_files)

        btn_browse_dir = QPushButton("Dir…")
        btn_browse_dir.clicked.connect(self._anim_browse_dir)
        src_layout.addWidget(btn_browse_dir)

        root.addWidget(src_group)

        # ── Options + run ─────────────────────────────────────────────
        opt_row = QHBoxLayout()

        opt_row.addWidget(QLabel("AC Threshold:"))
        self._anim_threshold_spin = QDoubleSpinBox()
        self._anim_threshold_spin.setRange(0.01, 1.0)
        self._anim_threshold_spin.setSingleStep(0.05)
        self._anim_threshold_spin.setValue(0.25)
        self._anim_threshold_spin.setDecimals(2)
        self._anim_threshold_spin.setToolTip(
            "Fraction of signal power in AC frequencies required to label a pixel as animated.\n"
            "Lower → more sensitive to subtle motion."
        )
        opt_row.addWidget(self._anim_threshold_spin)

        opt_row.addSpacing(8)
        opt_row.addWidget(QLabel("Min anim px:"))
        self._anim_min_px_spin = QSpinBox()
        self._anim_min_px_spin.setRange(10, 50000)
        self._anim_min_px_spin.setSingleStep(100)
        self._anim_min_px_spin.setValue(500)
        self._anim_min_px_spin.setToolTip(
            "Minimum number of animated pixels (at 320-px scale) required to attempt clustering.\n"
            "Increase to suppress noise detections."
        )
        opt_row.addWidget(self._anim_min_px_spin)

        opt_row.addStretch()

        self._anim_run_btn = QPushButton("Detect Phases")
        self._anim_run_btn.setStyleSheet(
            "background:#1976D2; color:white; font-weight:bold; padding:5px 14px;"
        )
        self._anim_run_btn.clicked.connect(lambda: self._anim_do_run())
        opt_row.addWidget(self._anim_run_btn)

        self._anim_progress = QProgressBar()
        self._anim_progress.setRange(0, 100)
        self._anim_progress.setValue(0)
        self._anim_progress.setTextVisible(True)
        self._anim_progress.hide()
        opt_row.addWidget(self._anim_progress, 1)

        root.addLayout(opt_row)

        self._anim_status = QLabel("")
        self._anim_status.setStyleSheet("color:#aaa; font-style:italic;")
        root.addWidget(self._anim_status)

        # ── Result table ──────────────────────────────────────────────
        result_group = QGroupBox("Animation Phases")
        result_layout = QVBoxLayout(result_group)

        self._anim_table = QTableWidget(0, 3)
        self._anim_table.setHorizontalHeaderLabels(["Image", "Filename", "Phase"])
        self._anim_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self._anim_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self._anim_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self._anim_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._anim_table.setAlternatingRowColors(False)
        self._anim_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._anim_table.verticalHeader().setVisible(False)
        self._anim_table.verticalHeader().setDefaultSectionSize(52)
        self._anim_table.setIconSize(QSize(48, 48))
        self._anim_table.setMinimumHeight(300)
        self._anim_table.setStyleSheet(
            "QTableWidget { background:#2c2f33; }"
            "QHeaderView::section { background:#1e1f22; color:#ccc; padding:4px; }"
        )
        result_layout.addWidget(self._anim_table)

        self._anim_legend = QLabel(
            "Rows are colour-coded by phase.  "
            "Requires scikit-learn — install with: pip install scikit-learn"
        )
        self._anim_legend.setStyleSheet("color:#888; font-size:10px; padding:2px 0;")
        self._anim_legend.setWordWrap(True)
        result_layout.addWidget(self._anim_legend)

        root.addWidget(result_group)
        return panel

    # ── Anim Clusters slots ────────────────────────────────────────────────

    @Slot()
    def _anim_load_from_frames(self):
        if not self._frame_paths:
            QMessageBox.information(self, "Animation Phases",
                                    "No frames loaded in the Stitch tab.")
            return
        self._anim_files_edit.clear()
        self._anim_cluster_paths = []
        self._anim_cluster_dir_path = ""
        self._anim_do_run(sorted(self._frame_paths))

    @Slot()
    def _anim_browse_files(self):
        start = self._anim_cluster_dir_path or (
            os.path.dirname(self._frame_paths[-1]) if self._frame_paths else ""
        )
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Select Images", start,
            "Images (*.png *.jpg *.jpeg *.webp *.bmp *.tiff *.tif)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if not paths:
            return
        self._anim_cluster_paths = sorted(paths)
        self._anim_cluster_dir_path = ""
        self._anim_files_edit.setText(f"{len(paths)} file(s) selected")

    @Slot()
    def _anim_browse_dir(self):
        start = self._anim_cluster_dir_path or (
            os.path.dirname(self._frame_paths[-1]) if self._frame_paths else ""
        )
        d = QFileDialog.getExistingDirectory(
            self, "Select Image Directory", start,
            QFileDialog.Option.DontUseNativeDialog,
        )
        if not d:
            return
        self._anim_cluster_dir_path = d
        self._anim_cluster_paths = []
        self._anim_files_edit.setText(d)

    @Slot()
    def _anim_do_run(self, paths: Optional[List[str]] = None):
        if paths is None:
            if self._anim_cluster_dir_path:
                import pathlib
                exts = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tiff", ".tif"}
                paths = sorted(
                    str(p) for p in pathlib.Path(self._anim_cluster_dir_path).iterdir()
                    if p.is_file() and p.suffix.lower() in exts
                )
                if not paths:
                    QMessageBox.information(self, "Animation Phases",
                                            "No image files found in the selected directory.")
                    return
            elif self._anim_cluster_paths:
                paths = self._anim_cluster_paths
            else:
                QMessageBox.information(
                    self, "Animation Phases",
                    "Select images using 'Use Stitch Frame List', 'Files…', or 'Dir…'."
                )
                return

        if not paths:
            return

        if self._anim_cluster_worker is not None:
            self._anim_cluster_worker.cancel()
            self._anim_cluster_worker = None

        self._anim_table.setRowCount(0)
        self._anim_item_map.clear()
        self._anim_progress.setValue(0)
        self._anim_progress.show()
        self._anim_status.setText(f"Analysing {len(paths)} image(s)…")
        self._anim_run_btn.setEnabled(False)

        worker = AnimClusterWorker(
            paths,
            ac_threshold=self._anim_threshold_spin.value(),
            min_anim_pixels=self._anim_min_px_spin.value(),
        )
        self._anim_cluster_worker = worker
        worker.signals.progress.connect(self._anim_on_progress)
        worker.signals.finished.connect(self._anim_on_finished)
        worker.signals.error.connect(self._anim_on_error)
        QThreadPool.globalInstance().start(worker)

    @Slot(int)
    def _anim_on_progress(self, pct: int):
        self._anim_progress.setValue(pct)

    @Slot(list)
    def _anim_on_finished(self, rows: List[dict]):
        self._anim_progress.hide()
        self._anim_cluster_worker = None
        self._anim_run_btn.setEnabled(True)

        n = len(rows)
        if n == 0:
            self._anim_status.setText("No images processed.")
            return

        is_anim = any(r.get("is_animated", False) for r in rows)
        if not is_anim:
            reason = rows[0].get("cluster_name", "Static")
            self._anim_status.setText(f"Result: {reason}")
        else:
            n_phases = len({r["cluster"] for r in rows})
            self._anim_status.setText(
                f"Done. {n} image(s) assigned to {n_phases} animation phase(s)."
            )

        table = self._anim_table
        table.setRowCount(n)
        self._anim_item_map.clear()

        for r, row in enumerate(rows):
            cluster    = row.get("cluster", 0)
            is_animated = row.get("is_animated", False)
            if is_animated:
                fg, bg = _ANIM_CLUSTER_COLORS[cluster % len(_ANIM_CLUSTER_COLORS)]
            else:
                fg, bg = "#aaaaaa", "#2c2f33"

            # Col 0: thumbnail placeholder
            thumb_item = QTableWidgetItem("")
            thumb_item.setData(Qt.ItemDataRole.UserRole, row["path"])
            thumb_item.setBackground(QColor(bg))
            table.setItem(r, 0, thumb_item)
            self._anim_item_map[row["path"]] = thumb_item
            QThreadPool.globalInstance().start(
                _ThumbTask(row["path"], 48, 0, self._anim_thumb_hub)
            )

            # Col 1: filename
            fname_item = QTableWidgetItem(os.path.basename(row["path"]))
            fname_item.setForeground(QColor(fg))
            fname_item.setBackground(QColor(bg))
            fname_item.setToolTip(row["path"])
            fname_item.setTextAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )
            table.setItem(r, 1, fname_item)

            # Col 2: phase name
            phase_item = QTableWidgetItem(row.get("cluster_name", ""))
            phase_item.setForeground(QColor(fg))
            phase_item.setBackground(QColor(bg))
            phase_item.setTextAlignment(
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
            )
            table.setItem(r, 2, phase_item)

    @Slot(str)
    def _anim_on_error(self, msg: str):
        self._anim_progress.hide()
        self._anim_status.setText("Error.")
        self._anim_run_btn.setEnabled(True)
        self._anim_cluster_worker = None
        QMessageBox.critical(self, "Animation Phase Detection Error", msg)

    @Slot(str, int, object)
    def _on_anim_thumb_loaded(self, path: str, _generation: int, img: QImage):
        item = self._anim_item_map.get(path)
        if item and not img.isNull():
            item.setIcon(QIcon(QPixmap.fromImage(img)))

    # ======================================================================
    # ── SUB-TAB 6: Sequence Builder ───────────────────────────────────────
    # ======================================================================

    def _build_seq_panel(self) -> QWidget:
        panel = QWidget()
        root = QVBoxLayout(panel)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # ── Source ────────────────────────────────────────────────────
        src_group = QGroupBox("Source")
        src_form  = QFormLayout(src_group)

        anchor_row = QHBoxLayout()
        self._seq_anchor_edit = QLineEdit()
        self._seq_anchor_edit.setPlaceholderText("Pick the base/anchor image…")
        self._seq_anchor_edit.setReadOnly(True)
        anchor_row.addWidget(self._seq_anchor_edit, 1)
        btn_anchor = QPushButton("Browse…")
        btn_anchor.clicked.connect(self._seq_browse_anchor)
        anchor_row.addWidget(btn_anchor)
        src_form.addRow("Anchor image:", anchor_row)

        dir_row = QHBoxLayout()
        self._seq_dir_edit = QLineEdit()
        self._seq_dir_edit.setPlaceholderText("Directory of candidate images…")
        self._seq_dir_edit.setReadOnly(True)
        dir_row.addWidget(self._seq_dir_edit, 1)
        btn_dir = QPushButton("Browse…")
        btn_dir.clicked.connect(self._seq_browse_dir)
        dir_row.addWidget(btn_dir)
        src_form.addRow("Candidates dir:", dir_row)

        btn_from_stitch = QPushButton("Use Stitch Frame List as Candidates")
        btn_from_stitch.setToolTip(
            "Populate the candidate pool from the current Stitch tab frame list."
        )
        btn_from_stitch.clicked.connect(self._seq_load_from_stitch)
        src_form.addRow("", btn_from_stitch)

        root.addWidget(src_group)

        # ── Options + run ─────────────────────────────────────────────
        opt_group  = QGroupBox("Options")
        opt_layout = QHBoxLayout(opt_group)

        opt_layout.addWidget(QLabel("Min fitness:"))
        self._seq_min_score_spin = QDoubleSpinBox()
        self._seq_min_score_spin.setRange(0.01, 0.99)
        self._seq_min_score_spin.setValue(0.15)
        self._seq_min_score_spin.setDecimals(2)
        self._seq_min_score_spin.setSingleStep(0.05)
        self._seq_min_score_spin.setToolTip(
            "Minimum stitching fitness to extend the chain.\n"
            "Fitness = ORB inlier ratio × displacement quality "
            "(peaks at ~30% of frame diagonal pan, zero for near-duplicates or non-overlapping).\n"
            "Start at 0.15; raise to filter weaker pairs."
        )
        opt_layout.addWidget(self._seq_min_score_spin)

        opt_layout.addSpacing(12)
        opt_layout.addWidget(QLabel("Min sharpness ratio:"))
        self._seq_blur_spin = QDoubleSpinBox()
        self._seq_blur_spin.setRange(0.0, 1.0)
        self._seq_blur_spin.setValue(0.50)
        self._seq_blur_spin.setDecimals(2)
        self._seq_blur_spin.setSingleStep(0.05)
        self._seq_blur_spin.setToolTip(
            "Reject candidates whose Laplacian sharpness is below this fraction "
            "of the anchor's sharpness.\n"
            "0.5 = must be at least 50% as sharp as the anchor (filters motion-blurred frames).\n"
            "Set to 0.0 to disable the sharpness filter."
        )
        opt_layout.addWidget(self._seq_blur_spin)

        opt_layout.addSpacing(12)
        opt_layout.addWidget(QLabel("Min pan %:"))
        self._seq_min_pan_spin = QDoubleSpinBox()
        self._seq_min_pan_spin.setRange(0.01, 0.50)
        self._seq_min_pan_spin.setValue(0.03)
        self._seq_min_pan_spin.setDecimals(2)
        self._seq_min_pan_spin.setSingleStep(0.01)
        self._seq_min_pan_spin.setToolTip(
            "Minimum camera translation as a fraction of the frame diagonal.\n"
            "Below this → near-duplicate (rejected).\n"
            "3% is usually right for anime panning; raise if duplicates appear."
        )
        opt_layout.addWidget(self._seq_min_pan_spin)

        opt_layout.addSpacing(12)
        opt_layout.addWidget(QLabel("Max pan %:"))
        self._seq_max_pan_spin = QDoubleSpinBox()
        self._seq_max_pan_spin.setRange(0.20, 0.99)
        self._seq_max_pan_spin.setValue(0.85)
        self._seq_max_pan_spin.setDecimals(2)
        self._seq_max_pan_spin.setSingleStep(0.05)
        self._seq_max_pan_spin.setToolTip(
            "Maximum camera translation as a fraction of the frame diagonal.\n"
            "Above this → frames don't overlap enough (rejected).\n"
            "85% is usually safe; lower if stitching fails at large offsets."
        )
        opt_layout.addWidget(self._seq_max_pan_spin)

        opt_layout.addStretch()

        self._seq_run_btn = QPushButton("⚡ Build Sequence")
        self._seq_run_btn.setStyleSheet(
            "background:#1976D2; color:white; font-weight:bold; padding:5px 14px;"
        )
        self._seq_run_btn.clicked.connect(self._seq_run)
        opt_layout.addWidget(self._seq_run_btn)

        root.addWidget(opt_group)

        # ── Progress ──────────────────────────────────────────────────
        prog_row = QHBoxLayout()
        self._seq_progress = QProgressBar()
        self._seq_progress.setRange(0, 100)
        self._seq_progress.setTextVisible(True)
        self._seq_progress.hide()
        prog_row.addWidget(self._seq_progress, 1)
        self._seq_status = QLabel("")
        self._seq_status.setStyleSheet("color:#aaa; font-style:italic;")
        prog_row.addWidget(self._seq_status)
        root.addLayout(prog_row)

        # ── Result chain ──────────────────────────────────────────────
        chain_group  = QGroupBox("Built Sequence  (drag to reorder · double-click row to replace image)")
        chain_layout = QVBoxLayout(chain_group)

        self._seq_chain_table = QTableWidget(0, 3)
        self._seq_chain_table.setHorizontalHeaderLabels(["Image", "Score to prev.", ""])
        self._seq_chain_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._seq_chain_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self._seq_chain_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self._seq_chain_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._seq_chain_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._seq_chain_table.setAlternatingRowColors(True)
        self._seq_chain_table.verticalHeader().setVisible(False)
        self._seq_chain_table.verticalHeader().setDefaultSectionSize(52)
        self._seq_chain_table.setIconSize(QSize(48, 48))
        self._seq_chain_table.setDragDropMode(QTableWidget.DragDropMode.InternalMove)
        self._seq_chain_table.setDefaultDropAction(Qt.DropAction.MoveAction)
        self._seq_chain_table.setDragEnabled(True)
        self._seq_chain_table.setAcceptDrops(True)
        self._seq_chain_table.setDropIndicatorShown(True)
        self._seq_chain_table.setMinimumHeight(260)
        self._seq_chain_table.setStyleSheet(
            "QTableWidget { background:#2c2f33; alternate-background-color:#36393f; }"
            "QHeaderView::section { background:#1e1f22; color:#ccc; padding:4px; }"
        )
        self._seq_chain_table.cellDoubleClicked.connect(self._seq_replace_row)
        self._seq_chain_table.model().rowsMoved.connect(self._seq_on_rows_moved)
        chain_layout.addWidget(self._seq_chain_table)

        # Edit buttons
        edit_row = QHBoxLayout()
        btn_add_before = QPushButton("Insert Before")
        btn_add_before.setToolTip("Insert a new image before the selected row.")
        btn_add_before.clicked.connect(lambda: self._seq_insert_image(before=True))
        btn_add_after = QPushButton("Insert After")
        btn_add_after.setToolTip("Insert a new image after the selected row.")
        btn_add_after.clicked.connect(lambda: self._seq_insert_image(before=False))
        btn_remove = QPushButton("Remove")
        btn_remove.setToolTip("Remove the selected row from the chain.")
        btn_remove.clicked.connect(self._seq_remove_row)
        btn_up = QPushButton("↑")
        btn_up.setFixedWidth(32)
        btn_up.clicked.connect(self._seq_move_up)
        btn_down = QPushButton("↓")
        btn_down.setFixedWidth(32)
        btn_down.clicked.connect(self._seq_move_down)
        for b in (btn_add_before, btn_add_after, btn_remove, btn_up, btn_down):
            apply_shadow_effect(b, radius=4, y_offset=2)
            edit_row.addWidget(b)
        edit_row.addStretch()

        btn_accept = QPushButton("✔ Use as Stitch List")
        btn_accept.setStyleSheet(
            "background:#388E3C; color:white; font-weight:bold; padding:5px 14px;"
        )
        btn_accept.setToolTip(
            "Load the current sequence into the Stitch tab frame list, replacing any existing frames."
        )
        btn_accept.clicked.connect(self._seq_accept)
        apply_shadow_effect(btn_accept, radius=6, y_offset=2)
        edit_row.addWidget(btn_accept)

        chain_layout.addLayout(edit_row)
        root.addWidget(chain_group)

        return panel

    # ── Sequence-builder slots ─────────────────────────────────────────────

    @Slot()
    def _seq_browse_anchor(self):
        start = self._seq_dir_path or os.path.dirname(self._seq_anchor_path) or ""
        p, _ = QFileDialog.getOpenFileName(
            self, "Select Anchor Image", start,
            "Images (*.png *.jpg *.jpeg *.webp *.bmp *.tiff)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if p:
            self._seq_anchor_path = p
            self._seq_anchor_edit.setText(p)
            # Auto-populate dir from anchor location if not already set
            if not self._seq_dir_path:
                self._seq_dir_path = os.path.dirname(p)
                self._seq_dir_edit.setText(self._seq_dir_path)

    @Slot()
    def _seq_browse_dir(self):
        start = self._seq_dir_path or os.path.dirname(self._seq_anchor_path) or ""
        d = QFileDialog.getExistingDirectory(
            self, "Select Candidate Directory", start,
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if d:
            self._seq_dir_path = d
            self._seq_dir_edit.setText(d)

    @Slot()
    def _seq_load_from_stitch(self):
        if not self._frame_paths:
            QMessageBox.information(self, "Sequence Builder",
                                    "The Stitch tab frame list is empty.")
            return
        # Use selected frame as anchor, rest as candidates
        row = self._frame_list.currentRow()
        anchor = self._frame_paths[row] if row >= 0 else self._frame_paths[0]
        self._seq_anchor_path = anchor
        self._seq_anchor_edit.setText(anchor)
        d = os.path.dirname(anchor)
        self._seq_dir_path = d
        self._seq_dir_edit.setText(d)
        QMessageBox.information(self, "Sequence Builder",
                                f"Anchor set to: {os.path.basename(anchor)}\n"
                                f"Candidates directory: {d}")

    @Slot()
    def _seq_run(self):
        if not self._seq_anchor_path or not os.path.isfile(self._seq_anchor_path):
            QMessageBox.warning(self, "Sequence Builder", "Please select a valid anchor image first.")
            return

        # Collect candidate paths from the directory
        import pathlib
        exts = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tif"}
        if self._seq_dir_path and os.path.isdir(self._seq_dir_path):
            candidates = sorted(
                str(p) for p in pathlib.Path(self._seq_dir_path).iterdir()
                if p.suffix.lower() in exts
            )
        else:
            QMessageBox.warning(self, "Sequence Builder",
                                "Please select a candidate directory first.")
            return

        if not candidates:
            QMessageBox.warning(self, "Sequence Builder",
                                "No image files found in the selected directory.")
            return

        if self._seq_worker is not None:
            self._seq_worker.cancel()
            self._seq_worker = None

        self._seq_chain_table.setRowCount(0)
        self._seq_chain = []
        self._seq_progress.setValue(0)
        self._seq_progress.show()
        self._seq_run_btn.setEnabled(False)
        n_cand = len(candidates)
        self._seq_status.setText(
            f"Searching {n_cand} candidates for anchor: {os.path.basename(self._seq_anchor_path)}…"
        )

        worker = SequenceBuilderWorker(
            self._seq_anchor_path,
            candidates,
            min_score=self._seq_min_score_spin.value(),
            blur_threshold=self._seq_blur_spin.value(),
            min_pan_ratio=self._seq_min_pan_spin.value(),
            max_pan_ratio=self._seq_max_pan_spin.value(),
        )
        self._seq_worker = worker
        worker.signals.progress.connect(self._seq_on_progress)
        worker.signals.result.connect(self._seq_on_result)
        worker.signals.error.connect(self._seq_on_error)
        QThreadPool.globalInstance().start(worker)

    @Slot(int)
    def _seq_on_progress(self, pct: int):
        self._seq_progress.setValue(pct)

    @Slot(list)
    def _seq_on_result(self, chain: List[dict]):
        self._seq_progress.hide()
        self._seq_run_btn.setEnabled(True)
        self._seq_worker = None
        self._seq_chain = chain
        self._seq_status.setText(f"Done. {len(chain)} frame(s) in sequence.")
        self._seq_populate_table(chain)

    def _seq_populate_table(self, chain: List[dict]):
        table = self._seq_chain_table
        table.setRowCount(0)
        self._seq_table_item_map.clear()
        for item in chain:
            r = table.rowCount()
            table.insertRow(r)
            name_item = QTableWidgetItem(item["name"])
            name_item.setData(Qt.ItemDataRole.UserRole, item["path"])
            name_item.setToolTip(item["path"])
            self._seq_table_item_map[item["path"]] = name_item
            QThreadPool.globalInstance().start(
                _ThumbTask(item["path"], 48, 0, self._seq_thumb_hub)
            )
            table.setItem(r, 0, name_item)

            score = item.get("score_to_prev")
            if score is None:
                score_item = QTableWidgetItem("— anchor —")
                score_item.setForeground(QColor("#aaa"))
            else:
                score_item = QTableWidgetItem(f"{score:.3f}")
                if score >= 0.6:
                    score_item.setForeground(QColor("#4CAF50"))
                    score_item.setBackground(QColor("#1b3a1f"))
                elif score >= 0.35:
                    score_item.setForeground(QColor("#FFC107"))
                    score_item.setBackground(QColor("#3a3000"))
                else:
                    score_item.setForeground(QColor("#f44336"))
                    score_item.setBackground(QColor("#3a1010"))
            score_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            table.setItem(r, 1, score_item)

            # "Replace" button cell
            replace_item = QTableWidgetItem("Replace…")
            replace_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
            replace_item.setForeground(QColor("#90CAF9"))
            table.setItem(r, 2, replace_item)

    def _seq_chain_from_table(self) -> List[dict]:
        """Read the current table contents back into a chain list."""
        table = self._seq_chain_table
        chain = []
        for r in range(table.rowCount()):
            name_item  = table.item(r, 0)
            score_item = table.item(r, 1)
            p = name_item.data(Qt.ItemDataRole.UserRole) if name_item else ""
            score_txt = score_item.text() if score_item else ""
            try:
                s = None if "anchor" in score_txt else float(score_txt)
            except ValueError:
                s = None
            chain.append({"path": p, "name": os.path.basename(p), "score_to_prev": s})
        return chain

    @Slot(int, int)
    def _seq_replace_row(self, row: int, col: int):
        """Double-click on any cell: open file picker to replace that row's image."""
        table = self._seq_chain_table
        name_item = table.item(row, 0)
        if name_item is None:
            return
        current_path = name_item.data(Qt.ItemDataRole.UserRole) or ""
        start = os.path.dirname(current_path) or self._seq_dir_path or ""
        p, _ = QFileDialog.getOpenFileName(
            self, "Replace Image", start,
            "Images (*.png *.jpg *.jpeg *.webp *.bmp *.tiff)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if not p:
            return
        name_item.setText(os.path.basename(p))
        name_item.setData(Qt.ItemDataRole.UserRole, p)
        name_item.setToolTip(p)
        # Clear score (unknown after manual replacement)
        score_item = table.item(row, 1)
        if score_item:
            score_item.setText("(replaced)")
            score_item.setForeground(QColor("#aaa"))

    @Slot()
    def _seq_insert_image(self, before: bool = True):
        table = self._seq_chain_table
        row = table.currentRow()
        if row < 0:
            row = table.rowCount() if not before else 0
        start = self._seq_dir_path or ""
        p, _ = QFileDialog.getOpenFileName(
            self, "Insert Image", start,
            "Images (*.png *.jpg *.jpeg *.webp *.bmp *.tiff)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if not p:
            return
        insert_at = row if before else row + 1
        table.insertRow(insert_at)
        name_item = QTableWidgetItem(os.path.basename(p))
        name_item.setData(Qt.ItemDataRole.UserRole, p)
        name_item.setToolTip(p)
        self._seq_table_item_map[p] = name_item
        QThreadPool.globalInstance().start(
            _ThumbTask(p, 48, 0, self._seq_thumb_hub)
        )
        table.setItem(insert_at, 0, name_item)
        score_item = QTableWidgetItem("(inserted)")
        score_item.setForeground(QColor("#aaa"))
        score_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        table.setItem(insert_at, 1, score_item)
        replace_item = QTableWidgetItem("Replace…")
        replace_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
        replace_item.setForeground(QColor("#90CAF9"))
        table.setItem(insert_at, 2, replace_item)
        table.setCurrentCell(insert_at, 0)

    @Slot()
    def _seq_remove_row(self):
        row = self._seq_chain_table.currentRow()
        if row >= 0:
            self._seq_chain_table.removeRow(row)

    @Slot()
    def _seq_move_up(self):
        table = self._seq_chain_table
        row = table.currentRow()
        if row <= 0:
            return
        self._seq_swap_rows(row - 1, row)
        table.setCurrentCell(row - 1, 0)

    @Slot()
    def _seq_move_down(self):
        table = self._seq_chain_table
        row = table.currentRow()
        if row < 0 or row >= table.rowCount() - 1:
            return
        self._seq_swap_rows(row, row + 1)
        table.setCurrentCell(row + 1, 0)

    def _seq_swap_rows(self, a: int, b: int):
        table = self._seq_chain_table
        for col in range(table.columnCount()):
            ia = table.takeItem(a, col)
            ib = table.takeItem(b, col)
            if ia:
                table.setItem(b, col, ia)
            if ib:
                table.setItem(a, col, ib)

    @Slot(object, int, int, object, int)
    def _seq_on_rows_moved(self, *_args):
        """QAbstractItemModel.rowsMoved — no extra action needed; table updates itself."""
        pass

    @Slot()
    def _seq_accept(self):
        """Push the current chain table into the Stitch tab frame list."""
        table = self._seq_chain_table
        if table.rowCount() == 0:
            QMessageBox.information(self, "Sequence Builder",
                                    "The sequence is empty — nothing to load.")
            return

        paths = []
        for r in range(table.rowCount()):
            item = table.item(r, 0)
            if item:
                p = item.data(Qt.ItemDataRole.UserRole)
                if p and os.path.isfile(p):
                    paths.append(p)

        if not paths:
            QMessageBox.warning(self, "Sequence Builder",
                                "No valid file paths found in the current sequence.")
            return

        self._frame_paths = paths
        self._frame_item_map.clear()
        self._frame_list.clear()
        for p in self._frame_paths:
            self._frame_list.addItem(self._make_frame_item(p))

        self._tab_widget.setCurrentIndex(0)   # switch to Stitch tab
        QMessageBox.information(
            self, "Sequence Builder",
            f"Loaded {len(paths)} frame(s) into the Stitch tab.\n"
            "Switch to the Stitch tab to run the pipeline."
        )

    @Slot(str)
    def _seq_on_error(self, msg: str):
        self._seq_progress.hide()
        self._seq_run_btn.setEnabled(True)
        self._seq_worker = None
        self._seq_status.setText("Error.")
        QMessageBox.critical(self, "Sequence Builder Error", msg)

    # ======================================================================
    # ── SUB-TAB 7: Hybrid Stitch ──────────────────────────────────────────
    # ======================================================================

    def _build_hybrid_panel(self) -> QWidget:
        self._hybrid_panel = HybridStitchPanel(parent=self)
        self._hybrid_panel.sequence_accepted.connect(self._on_hybrid_sequence_accepted)
        return self._hybrid_panel

    @Slot(list)
    def _on_hybrid_sequence_accepted(self, paths: List[str]):
        """Load the sequence from the Hybrid Stitch panel into the Stitch tab."""
        if not paths:
            return
        self._frame_paths = list(paths)
        self._frame_item_map.clear()
        self._frame_list.clear()
        for p in self._frame_paths:
            self._frame_list.addItem(self._make_frame_item(p))
        self._tab_widget.setCurrentIndex(0)
        QMessageBox.information(
            self, "Hybrid Stitch",
            f"Loaded {len(paths)} frame(s) into the Stitch tab.\n"
            "Switch to the Stitch tab to run the pipeline."
        )


StitchTab = EditTab
