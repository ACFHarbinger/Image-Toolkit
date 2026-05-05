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

        self._init_ui()

    # ======================================================================
    # Top-level UI
    # ======================================================================

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._tab_widget = QTabWidget()
        self._tab_widget.addTab(self._build_stitch_panel(), "Stitch")
        self._tab_widget.addTab(self._build_graph_panel(),  "Graph")
        self._tab_widget.addTab(self._build_adjust_panel(), "Adjust")
        self._tab_widget.addTab(self._build_canvas_panel(), "Canvas")

        root.addWidget(self._tab_widget)

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
                item = QListWidgetItem(os.path.basename(p))
                item.setData(Qt.ItemDataRole.UserRole, p)
                item.setToolTip(p)
                self._frame_list.addItem(item)
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
            item = QListWidgetItem(f"[adj] {os.path.basename(self._adj_img_path)}")
            item.setData(Qt.ItemDataRole.UserRole, tmp_path)
            item.setToolTip(tmp_path)
            self._frame_list.addItem(item)
            self._refresh_pair_combo()
        self._tab_widget.setCurrentIndex(0)

    def _adj_send_to_canvas(self):
        tmp_path = self._adj_export_to_temp()
        if not tmp_path:
            return
        if tmp_path not in self._cv_paths:
            self._cv_paths.append(tmp_path)
            item = QListWidgetItem(f"[adj] {os.path.basename(self._adj_img_path)}")
            item.setData(Qt.ItemDataRole.UserRole, tmp_path)
            item.setToolTip(tmp_path)
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
                item = QListWidgetItem(os.path.basename(p))
                item.setData(Qt.ItemDataRole.UserRole, p)
                item.setToolTip(p)
                self._cv_list.addItem(item)

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
                    item = QListWidgetItem(os.path.basename(p))
                    item.setData(Qt.ItemDataRole.UserRole, p)
                    item.setToolTip(p)
                    self._frame_list.addItem(item)
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
                    item = QListWidgetItem(os.path.basename(p))
                    item.setData(Qt.ItemDataRole.UserRole, p)
                    item.setToolTip(p)
                    self._cv_list.addItem(item)

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


StitchTab = EditTab
