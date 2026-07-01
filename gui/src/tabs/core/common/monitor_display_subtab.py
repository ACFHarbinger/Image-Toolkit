import os
import math
import uuid
import shutil
import tempfile
import subprocess
import platform
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any

from PySide6.QtCore import Qt, Signal, QPointF, QRectF, QTimer, Slot, QPoint
from PySide6.QtGui import (
    QPixmap, QFont, QPolygonF, QKeyEvent, QAction,
    QPainterPathStroker, QPainterPath,
    QPainter, QPen, QBrush, QColor, 
)
from PySide6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QGroupBox, QDialog, QDialogButtonBox,
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QGraphicsView,
    QListWidgetItem, QRadioButton, QButtonGroup, QStackedWidget,
    QFileDialog, QMessageBox, QColorDialog, QMenu, QListWidget, 
    QGraphicsScene, QGraphicsObject, QGraphicsItem, QLabel,
    QLineEdit, QGridLayout, QPushButton,
)
from screeninfo import Monitor

from backend.src.constants import SUPPORTED_VIDEO_FORMATS, SUPPORTED_IMG_FORMATS
from .wallpaper_common import WallpaperCommonBase
from ....components import MonitorDropWidget, MarqueeScrollArea
from ....styles.style import apply_shadow_effect
from ....helpers.video.video_thumbnailer import get_video_thumbnail_cache_path, VideoThumbnailer


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class NodeData:
    node_id: str
    file_path: str
    display_mode: str = "fixed"      # "fixed" | "video_runtime"
    duration_sec: float = 30.0
    pos_x: float = 0.0
    pos_y: float = 0.0


@dataclass
class EdgeData:
    edge_id: int
    source_id: str
    target_id: str


@dataclass
class GraphData:
    nodes: Dict[str, NodeData] = field(default_factory=dict)
    edges: List[EdgeData] = field(default_factory=list)
    end_behavior: str = "repeat_graph"
    end_color: str = "#000000"
    end_jump_node_id: Optional[str] = None
    basis_node_id: Optional[str] = None  # starting node of the slideshow

    def alloc_edge_id(self, source_id: str) -> int:
        """Return the next per-source edge index (1-based) for *source_id*."""
        existing = [e for e in self.edges if e.source_id == source_id]
        return len(existing) + 1

    def renumber_edges(self):
        """Re-assign edge_id values so each source node's edges are numbered 1…N."""
        from collections import defaultdict
        counter: Dict[str, int] = defaultdict(int)
        for e in self.edges:
            counter[e.source_id] += 1
            e.edge_id = counter[e.source_id]

    def to_dict(self) -> dict:
        return {
            "nodes": {
                nid: {
                    "node_id": nd.node_id,
                    "file_path": nd.file_path,
                    "display_mode": nd.display_mode,
                    "duration_sec": nd.duration_sec,
                    "pos_x": nd.pos_x,
                    "pos_y": nd.pos_y,
                }
                for nid, nd in self.nodes.items()
            },
            "edges": [
                {"edge_id": e.edge_id, "source_id": e.source_id, "target_id": e.target_id}
                for e in self.edges
            ],
            "end_behavior": self.end_behavior,
            "end_color": self.end_color,
            "end_jump_node_id": self.end_jump_node_id,
            "basis_node_id": self.basis_node_id,
        }

    @staticmethod
    def from_dict(d: dict) -> "GraphData":
        g = GraphData()
        g.end_behavior = d.get("end_behavior", "repeat_graph")
        g.end_color = d.get("end_color", "#000000")
        g.end_jump_node_id = d.get("end_jump_node_id")
        g.basis_node_id = d.get("basis_node_id")
        for nid, nd in d.get("nodes", {}).items():
            g.nodes[nid] = NodeData(**nd)
        for ed in d.get("edges", []):
            g.edges.append(EdgeData(**ed))
        return g


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _is_video(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in SUPPORTED_VIDEO_FORMATS


def _get_video_duration(path: str) -> Optional[float]:
    """Return video duration in seconds via ffprobe or cv2."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True, timeout=10,
        )
        val = result.stdout.strip()
        if val:
            return float(val)
    except Exception:
        pass
    try:
        import cv2  # type: ignore
        cap = cv2.VideoCapture(path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        cap.release()
        if fps > 0:
            return frames / fps
    except Exception:
        pass
    return None


def _build_reachable(graph: GraphData) -> set:
    """
    Return the set of node_ids reachable from basis_node_id via a BFS/DFS
    that always follows the lowest-numbered out-edge first.
    A node with no outgoing edges is a sink and is included if reachable.
    """
    if not graph.nodes:
        return set()
    start = graph.basis_node_id
    if not start or start not in graph.nodes:
        # Fallback: first node in insertion order
        start = next(iter(graph.nodes))
    
    # Build adjacency: source_id -> [target_id, ...] ordered by per-source edge_id
    from collections import defaultdict
    adj: Dict[str, List[str]] = defaultdict(list)
    for src in graph.nodes:
        src_edges = sorted(
            [e for e in graph.edges if e.source_id == src],
            key=lambda e: e.edge_id,
        )
        adj[src] = [e.target_id for e in src_edges]

    visited: set = set()
    stack = [start]
    while stack:
        nid = stack.pop()
        if nid in visited:
            continue
        visited.add(nid)
        for tgt in adj.get(nid, []):
            if tgt not in visited:
                stack.append(tgt)
    return visited


def _sink_nodes(graph: GraphData) -> set:
    """Return node_ids that have no outgoing edges."""
    srcs = {e.source_id for e in graph.edges}
    return {nid for nid in graph.nodes if nid not in srcs}


def _build_live_edges(graph: GraphData) -> set:
    """
    Return the set of (source_id, edge_id) tuples that will actually be
    traversed during a normal slideshow run.

    The runtime logic always follows the **lowest-numbered** outgoing edge
    from each node. An edge is live only if:
      - its source node is visited during the traversal (reachable from basis
        along first-edges only), and
      - it is that node's edge #1 (the single edge the runtime will take).

    All other edges — including edges from unreachable sources, and higher-
    numbered sibling edges on an otherwise-reachable source — are "dead".
    """
    if not graph.nodes:
        return set()

    start = graph.basis_node_id
    if not start or start not in graph.nodes:
        start = next(iter(graph.nodes))

    from collections import defaultdict
    # Map source_id -> edges sorted by edge_id (ascending)
    adj: Dict[str, List[EdgeData]] = defaultdict(list)
    for src in graph.nodes:
        src_edges = sorted(
            [e for e in graph.edges if e.source_id == src],
            key=lambda e: e.edge_id,
        )
        adj[src] = src_edges

    live: set = set()
    visited: set = set()
    current = start
    # Walk the same path the runtime takes — first edge only, stop at loops/sinks
    while current and current not in visited:
        visited.add(current)
        edges_here = adj.get(current, [])
        if not edges_here:
            break  # sink — no outgoing edge
        first_edge = edges_here[0]
        live.add((first_edge.source_id, first_edge.edge_id))
        current = first_edge.target_id

    return live


def _build_traversal(graph: GraphData) -> List[Tuple[str, float]]:
    """
    Return [(file_path, duration_sec), ...] for the graph traversal.
    Starts from basis_node_id; at each node follows edges in per-source
    edge_id order (edge #1 first). Stops when a sink or already-visited
    node is encountered to avoid infinite loops.
    """
    if not graph.nodes:
        return []
    
    start = graph.basis_node_id
    if not start or start not in graph.nodes:
        start = next(iter(graph.nodes))

    # If no edges, just show the basis node
    if not graph.edges:
        nd = graph.nodes[start]
        return [(nd.file_path, _node_duration(nd))]

    from collections import defaultdict
    adj: Dict[str, List[str]] = defaultdict(list)
    for src in graph.nodes:
        src_edges = sorted(
            [e for e in graph.edges if e.source_id == src],
            key=lambda e: e.edge_id,
        )
        adj[src] = [e.target_id for e in src_edges]

    seq: List[Tuple[str, float]] = []
    visited: set = set()
    current = start
    while True:
        nd = graph.nodes.get(current)
        if nd is None:
            break
        seq.append((nd.file_path, _node_duration(nd)))
        if current in visited:
            break  # detected loop — stop
        visited.add(current)
        neighbors = adj.get(current, [])
        if not neighbors:
            break  # sink node — stop
        current = neighbors[0]  # always follow edge #1

    return seq


def _node_duration(nd: NodeData) -> float:
    if nd.display_mode == "video_runtime":
        dur = _get_video_duration(nd.file_path)
        return dur if dur else nd.duration_sec
    return nd.duration_sec


# ---------------------------------------------------------------------------
# Graphics: NodeItem
# ---------------------------------------------------------------------------

_NODE_W = 140
_NODE_H = 115


class NodeItem(QGraphicsObject):
    """Visual node in the wallpaper sequence graph."""

    def __init__(self, node_data: NodeData):
        super().__init__()
        self.node_data = node_data
        self._pixmap: Optional[QPixmap] = None
        self._load_thumbnail()

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setPos(node_data.pos_x, node_data.pos_y)
        self.setToolTip(node_data.file_path)

    def _load_thumbnail(self):
        path = self.node_data.file_path
        if not os.path.exists(path):
            return
        try:
            if _is_video(path):
                cache_path = get_video_thumbnail_cache_path(path)
                if os.path.exists(cache_path):
                    pm = QPixmap(cache_path)
                else:
                    thumbnailer = VideoThumbnailer()
                    qimg = thumbnailer.generate(path, 120)
                    if qimg and not qimg.isNull():
                        pm = QPixmap.fromImage(qimg)
                        qimg.save(cache_path, "JPG") # pyrefly: ignore [no-matching-overload]
                    else:
                        pm = QPixmap()
            else:
                pm = QPixmap(path)

            if not pm.isNull():
                self._pixmap = pm.scaled(120, 72, Qt.AspectRatioMode.KeepAspectRatio,
                                         Qt.TransformationMode.SmoothTransformation)
        except Exception:
            pass

    def refresh_thumbnail(self):
        self._pixmap = None
        self._load_thumbnail()
        self.update()

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, _NODE_W, _NODE_H)

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Role assigned by WallpaperGraphScene._refresh_node_styles
        role = getattr(self, "_node_role", "reachable")
        is_sel = self.isSelected()

        if getattr(self, "_hovered_orange", False):
            bg_col = QColor("#e67e22"); border_col = QColor("#d35400"); border_w = 2
        elif role == "basis":
            bg_col = QColor("#2d3b1e") if is_sel else QColor("#2a3520")
            border_col = QColor("#ffeaa7") if is_sel else QColor("#f1c40f")
            border_w = 4 if is_sel else 3
        elif role == "sink":
            bg_col = QColor("#3b1a2d") if is_sel else QColor("#2e1a2b")
            border_col = QColor("#ff7eb3") if is_sel else QColor("#e056b8")
            border_w = 4 if is_sel else 3
        elif role == "unreachable":
            bg_col = QColor("#3a2020") if is_sel else QColor("#2e2020")
            border_col = QColor("#ff7675") if is_sel else QColor("#7f4040")
            border_w = 4 if is_sel else 2
        else:
            bg_col = QColor("#1a2b3c") if is_sel else QColor("#131c26")
            border_col = QColor("#00ffff") if is_sel else QColor("#3498db")
            border_w = 4 if is_sel else 2

        painter.setBrush(QBrush(bg_col))
        painter.setPen(QPen(border_col, border_w))
        painter.drawRoundedRect(QRectF(1, 1, _NODE_W - 2, _NODE_H - 2), 6, 6)

        # Role badge strip
        if role == "basis":
            badge = QRectF(1, 1, 42, 13)
            painter.fillRect(badge, QColor("#f1c40f"))
            painter.setPen(QPen(QColor("#1a1a00")))
            painter.setFont(QFont("Arial", 6, QFont.Weight.Bold))
            painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, "START")
        elif role == "sink":
            badge = QRectF(1, 1, 36, 13)
            painter.fillRect(badge, QColor("#e056b8"))
            painter.setPen(QPen(QColor("#1a001a")))
            painter.setFont(QFont("Arial", 6, QFont.Weight.Bold))
            painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, "END")
        elif role == "unreachable":
            badge = QRectF(1, 1, 52, 13)
            painter.fillRect(badge, QColor("#7f4040"))
            painter.setPen(QPen(QColor("#ffcccc")))
            painter.setFont(QFont("Arial", 6, QFont.Weight.Bold))
            painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, "SKIPPED")
        else:
            badge = QRectF(1, 1, 38, 13)
            painter.fillRect(badge, QColor("#3498db"))
            painter.setPen(QPen(QColor("#001a33")))
            painter.setFont(QFont("Arial", 6, QFont.Weight.Bold))
            painter.drawText(badge, Qt.AlignmentFlag.AlignCenter, "STEP")

        # Thumbnail area
        has_badge = True
        thumb_top = 15 if has_badge else 5
        thumb_rect = QRectF(5, thumb_top, _NODE_W - 10, 72 - (thumb_top - 5))
        if self._pixmap:
            pw, ph = self._pixmap.width(), self._pixmap.height()
            rx = thumb_rect.x() + (thumb_rect.width() - pw) / 2
            ry = thumb_rect.y() + (thumb_rect.height() - ph) / 2
            painter.drawPixmap(int(rx), int(ry), self._pixmap)
        else:
            painter.fillRect(thumb_rect, QColor("#23272a"))
            painter.setPen(QPen(QColor("#7289da")))
            painter.setFont(QFont("Arial", 14))
            icon = "\U0001f3ac" if _is_video(self.node_data.file_path) else "\U0001f5bc\ufe0f"
            painter.drawText(thumb_rect, Qt.AlignmentFlag.AlignCenter, icon)

        # Filename
        fname = os.path.basename(self.node_data.file_path)
        if len(fname) > 19:
            fname = fname[:16] + "..."
        painter.setPen(QPen(QColor("#ffffff")))
        painter.setFont(QFont("Arial", 7, QFont.Weight.Bold))
        painter.drawText(QRectF(2, 80, _NODE_W - 4, 16),
                         Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextSingleLine, fname)

        # Duration line
        if self.node_data.display_mode == "video_runtime":
            dur_text = "Full Runtime"
        else:
            s = self.node_data.duration_sec
            dur_text = f"{int(s//60)}m {int(s%60)}s" if s >= 60 else f"{s:.0f}s"
        painter.setPen(QPen(QColor("#b9bbbe")))
        painter.setFont(QFont("Arial", 7))
        painter.drawText(QRectF(2, 97, _NODE_W - 4, 14),
                         Qt.AlignmentFlag.AlignCenter, dur_text)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self.node_data.pos_x = self.pos().x()
            self.node_data.pos_y = self.pos().y()
            sc = self.scene()
            if sc and hasattr(sc, "_on_node_moved"):
                sc._on_node_moved(self.node_data.node_id)
        return super().itemChange(change, value)

    def mouseDoubleClickEvent(self, event):
        sc = self.scene()
        if sc and hasattr(sc, "node_edit_requested"):
            sc.node_edit_requested.emit(self.node_data.node_id)
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event):
        sc = self.scene()
        if sc and hasattr(sc, "_node_context_menu"):
            sc._node_context_menu(self.node_data.node_id, event.screenPos())
        event.accept()


# ---------------------------------------------------------------------------
# Graphics: EdgeItem
# ---------------------------------------------------------------------------

class EdgeItem(QGraphicsObject):
    """Visual directed edge (arrow) between two NodeItems, with an ID label."""

    def __init__(self, edge_data: EdgeData, src: NodeItem, tgt: NodeItem):
        super().__init__()
        self.edge_data = edge_data
        self.src = src
        self.tgt = tgt
        self._path = QPainterPath()
        self._arrow_tip = QPointF(0, 0)
        self._arrow_angle = 0.0
        self._label_pos = QPointF(0, 0)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setZValue(-1)
        self._update_path()

    def _is_self(self) -> bool:
        return self.edge_data.source_id == self.edge_data.target_id

    def update_path(self):
        self.prepareGeometryChange()
        self._update_path()
        self.update()

    def _node_center(self, item: NodeItem) -> QPointF:
        return item.mapToScene(QPointF(_NODE_W / 2, _NODE_H / 2))

    def _update_path(self):
        if self._is_self():
            self._build_self_loop()
        else:
            self._build_arrow()

    def _build_self_loop(self):
        cx = self.src.mapToScene(QPointF(_NODE_W / 2, 0)).x()
        top = self.src.mapToScene(QPointF(_NODE_W / 2, 0)).y()
        r = 28
        self._path = QPainterPath()
        self._path.moveTo(cx - 15, top)
        self._path.cubicTo(
            QPointF(cx - 15, top - r * 2.5),
            QPointF(cx + 15, top - r * 2.5),
            QPointF(cx + 15, top),
        )
        self._arrow_tip = QPointF(cx + 15, top)
        self._arrow_angle = math.pi / 2
        self._label_pos = QPointF(cx, top - r * 2.0)

    def _rect_edge_point(self, item: NodeItem, towards: QPointF) -> QPointF:
        center = self._node_center(item)
        dx = towards.x() - center.x()
        dy = towards.y() - center.y()
        length = math.hypot(dx, dy) or 1.0
        hw, hh = _NODE_W / 2 + 4, _NODE_H / 2 + 4
        if abs(dx) * hh >= abs(dy) * hw:
            t = hw / abs(dx) if dx != 0 else 1.0
        else:
            t = hh / abs(dy) if dy != 0 else 1.0
        return QPointF(center.x() + dx * t, center.y() + dy * t)

    def _build_arrow(self):
        sc = self._node_center(self.src)
        tc = self._node_center(self.tgt)
        sp = self._rect_edge_point(self.src, tc)
        tp = self._rect_edge_point(self.tgt, sc)

        dx = tp.x() - sp.x()
        dy = tp.y() - sp.y()
        length = math.hypot(dx, dy) or 1.0
        # Perpendicular offset for a slight curve to distinguish parallel edges
        offset = min(40.0, length * 0.15)
        mx = (sp.x() + tp.x()) / 2 - dy * offset / length
        my = (sp.y() + tp.y()) / 2 + dx * offset / length

        self._path = QPainterPath()
        self._path.moveTo(sp)
        self._path.quadTo(QPointF(mx, my), tp)

        self._arrow_tip = tp
        self._arrow_angle = math.atan2(tp.y() - my, tp.x() - mx)
        self._label_pos = QPointF(mx, my)

    def boundingRect(self) -> QRectF:
        return self._path.boundingRect().adjusted(-20, -20, 20, 20)

    def shape(self) -> QPainterPath:
        # Widen path for easier clicking
        stroker = QPainterPathStroker()
        stroker.setWidth(12)
        shape_path = stroker.createStroke(self._path)
        
        # Add the label rectangle to the clickable shape
        lp = self._label_pos
        text_rect = QRectF(lp.x() - 14, lp.y() - 9, 28, 18)
        shape_path.addRect(text_rect)
        return shape_path

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        is_sel = self.isSelected()
        is_active = getattr(self, "_edge_active", True)  # default True until first style refresh

        if is_sel:
            color = QColor("#f39c12")   # amber — selected (always visible)
            line_w = 2.5
        elif is_active:
            color = QColor("#7289da")   # soft indigo — active/live edge
            line_w = 2
        else:
            color = QColor("#6b2d2d")   # muted dark-red — dead/skipped edge
            line_w = 1.5

        pen = QPen(color, line_w)
        if not is_active and not is_sel:
            pen.setStyle(Qt.PenStyle.DashLine)  # dashed to reinforce "dead" status
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(self._path)
        self._draw_arrowhead(painter, color)

        # Edge ID label
        lp = self._label_pos
        label = f"#{self.edge_data.edge_id}"
        if is_active or is_sel:
            bg = QColor("#2c2f33")
        else:
            bg = QColor("#1e1212")   # darker tint for dead-edge labels
        text_rect = QRectF(lp.x() - 14, lp.y() - 9, 28, 18)
        painter.fillRect(text_rect, bg)
        painter.setPen(QPen(color))
        painter.setFont(QFont("Arial", 8, QFont.Weight.Bold))
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, label)

    def _draw_arrowhead(self, painter: QPainter, color: QColor):
        tip = self._arrow_tip
        angle = self._arrow_angle
        arrow_len, half_spread = 10, 0.45
        p1 = QPointF(tip.x() - arrow_len * math.cos(angle - half_spread),
                     tip.y() - arrow_len * math.sin(angle - half_spread))
        p2 = QPointF(tip.x() - arrow_len * math.cos(angle + half_spread),
                     tip.y() - arrow_len * math.sin(angle + half_spread))
        painter.setBrush(QBrush(color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon(QPolygonF([tip, p1, p2]))

    def contextMenuEvent(self, event):
        sc = self.scene()
        if sc and hasattr(sc, "_edge_context_menu"):
            sc._edge_context_menu(self.edge_data.edge_id, event.screenPos())
        event.accept()


# ---------------------------------------------------------------------------
# Scene
# ---------------------------------------------------------------------------

class TempEdgeItem(QGraphicsObject):
    """Temporary dashed edge that follows the mouse cursor during connection mode."""
    def __init__(self, source_item: NodeItem):
        super().__init__()
        self.source_item = source_item
        self.target_pos = QPointF(0, 0)
        self.setZValue(-1)

    def set_target_pos(self, pos: QPointF):
        self.target_pos = pos
        self.prepareGeometryChange()
        self.update()

    def boundingRect(self) -> QRectF:
        sp = self.source_item.pos() + QPointF(_NODE_W / 2, _NODE_H / 2)
        tp = self.target_pos
        rect = QRectF(sp, tp).normalized()
        return rect.adjusted(-50, -50, 50, 50)

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        sp = self.source_item.pos() + QPointF(_NODE_W / 2, _NODE_H / 2)
        tp = self.target_pos
        
        mx = (sp.x() + tp.x()) / 2
        my = (sp.y() + tp.y()) / 2 - 30
        path = QPainterPath()
        path.moveTo(sp)
        path.quadTo(QPointF(mx, my), tp)
        
        color = QColor("#f39c12")
        pen = QPen(color, 2, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)


class WallpaperGraphScene(QGraphicsScene):
    node_edit_requested = Signal(str)   # node_id
    graph_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._graph: Optional[GraphData] = None
        self._node_items: Dict[str, NodeItem] = {}
        self._edge_items: Dict[int, EdgeItem] = {}
        self._connecting_source_node_id: Optional[str] = None
        self._temp_edge_item: Optional[TempEdgeItem] = None
        self._hovered_target_node: Optional[NodeItem] = None

    # ---- Public API -------------------------------------------------------

    def load_graph(self, graph: GraphData):
        self._end_connection_mode()
        self._graph = graph
        self._node_items.clear()
        self._edge_items.clear()
        self.clear()
        # Auto-assign basis if not set
        if graph.nodes and not graph.basis_node_id:
            graph.basis_node_id = next(iter(graph.nodes))
        for nd in graph.nodes.values():
            self._add_node_item(nd)
        for ed in sorted(graph.edges, key=lambda e: (e.source_id, e.edge_id)):
            self._add_edge_item(ed)
        self._refresh_node_styles()

    def clear_graph(self):
        self._end_connection_mode()
        self._graph = None
        self._node_items.clear()
        self._edge_items.clear()
        self.clear()

    def add_node(self, file_path: str, pos: QPointF) -> str:
        nid = str(uuid.uuid4())
        is_video = file_path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS))
        display_mode = "video_runtime" if is_video else "fixed"
        nd = NodeData(node_id=nid, file_path=file_path,
                      display_mode=display_mode, duration_sec=30.0,
                      pos_x=pos.x(), pos_y=pos.y())
        self._graph.nodes[nid] = nd # pyrefly: ignore [missing-attribute]
        if self._graph.basis_node_id is None:
            self._graph.basis_node_id = nid
        self._add_node_item(nd)
        self.graph_changed.emit()

        parent = self.parent()
        if parent and hasattr(parent, "deselect_all_items"):
            parent.deselect_all_items()

        return nid

    def add_edge(self, source_id: str, target_id: str) -> int:
        eid = self._graph.alloc_edge_id(source_id) # pyrefly: ignore [missing-attribute]
        ed = EdgeData(edge_id=eid, source_id=source_id, target_id=target_id)
        self._graph.edges.append(ed) # pyrefly: ignore [missing-attribute]
        self._add_edge_item(ed)
        self.graph_changed.emit()
        return eid

    def remove_selected(self):
        for item in list(self.selectedItems()):
            if isinstance(item, EdgeItem):
                self._remove_edge(item.edge_data.source_id, item.edge_data.edge_id)
            elif isinstance(item, NodeItem):
                self._remove_node(item.node_data.node_id)
        self.graph_changed.emit()

    def node_labels(self) -> List[Tuple[str, str]]:
        """Return [(node_id, short_label), ...] for all nodes."""
        if self._graph is None:
            return []
        result = []
        for nid, nd in self._graph.nodes.items():
            label = os.path.basename(nd.file_path)
            if len(label) > 25:
                label = label[:22] + "..."
            result.append((nid, label))
        return result

    # ---- Internal helpers -------------------------------------------------

    def _add_node_item(self, nd: NodeData):
        item = NodeItem(nd)
        self.addItem(item)
        self._node_items[nd.node_id] = item

    def _add_edge_item(self, ed: EdgeData):
        src = self._node_items.get(ed.source_id)
        tgt = self._node_items.get(ed.target_id)
        if src is None or tgt is None:
            return
        item = EdgeItem(ed, src, tgt)
        self.addItem(item)
        # Key is (source_id, per-source edge_id) to avoid collisions
        self._edge_items[(ed.source_id, ed.edge_id)] = item

    def _remove_node(self, node_id: str):
        if self._graph is None:
            return
        # Remove edges that reference this node first
        # Must be done dynamically because _remove_edge renumbers remaining edges,
        # which would invalidate a statically collected list of edge IDs.
        while True:
            edges = [e for e in self._graph.edges 
                     if e.source_id == node_id or e.target_id == node_id]
            if not edges:
                break
            e = edges[0]
            self._remove_edge(e.source_id, e.edge_id)
        item = self._node_items.pop(node_id, None)
        if item:
            self.removeItem(item)
        self._graph.nodes.pop(node_id, None)
        # Clear basis if the node being removed was it
        if self._graph.basis_node_id == node_id:
            self._graph.basis_node_id = next(iter(self._graph.nodes), None)

    def _remove_edge(self, source_id: str, edge_id: int):
        if self._graph is None:
            return
        key = (source_id, edge_id)
        item = self._edge_items.pop(key, None)
        if item:
            self.removeItem(item)
        self._graph.edges = [
            e for e in self._graph.edges
            if not (e.source_id == source_id and e.edge_id == edge_id)
        ]
        # Renumber per-source IDs
        self._graph.renumber_edges()
        # Rebuild _edge_items map with updated keys
        new_edge_items = {}
        for it in list(self._edge_items.values()):
            new_edge_items[(it.edge_data.source_id, it.edge_data.edge_id)] = it
            it.update()
        self._edge_items = new_edge_items

    def start_connection_mode(self, source_node_id: str):
        self._end_connection_mode()
        source_item = self._node_items.get(source_node_id)
        if not source_item:
            return
        self._connecting_source_node_id = source_node_id
        self._temp_edge_item = TempEdgeItem(source_item)
        self.addItem(self._temp_edge_item)
        
        from PySide6.QtGui import QCursor
        views = self.views()
        if views:
            view = views[0]
            local_pos = view.mapFromGlobal(QCursor.pos())
            scene_pos = view.mapToScene(local_pos)
            self._temp_edge_item.set_target_pos(scene_pos)

    def _end_connection_mode(self):
        old_hovered = getattr(self, "_hovered_target_node", None)
        if old_hovered:
            try:
                old_hovered._hovered_orange = False
                old_hovered.update()
            except RuntimeError:
                pass
        self._hovered_target_node = None
        
        temp_item = getattr(self, "_temp_edge_item", None)
        if temp_item:
            try:
                temp_item.setVisible(False)
                temp_item.setEnabled(False)
            except RuntimeError:
                pass
            def safe_remove():
                try:
                    self.removeItem(temp_item)
                except RuntimeError:
                    pass
                finally:
                    if not hasattr(self, "_deleted_items_garbage"):
                        self._deleted_items_garbage = []
                    self._deleted_items_garbage.append(temp_item)
                    if len(self._deleted_items_garbage) > 5:
                        self._deleted_items_garbage.pop(0)
                    if getattr(self, "_temp_edge_item", None) is temp_item:
                        self._temp_edge_item = None
            QTimer.singleShot(0, safe_remove)
            
        self._connecting_source_node_id = None

    def handle_connection_press(self, scene_pos, button):
        if not self._connecting_source_node_id:
            return
            
        src_id = self._connecting_source_node_id
        self._connecting_source_node_id = None
            
        if button == Qt.MouseButton.LeftButton:
            target_node = getattr(self, "_hovered_target_node", None)
            if not target_node:
                for item in self.items(scene_pos):
                    if isinstance(item, NodeItem):
                        target_node = item
                        break
            if target_node:
                tgt_id = target_node.node_data.node_id
                QTimer.singleShot(0, lambda s=src_id, t=tgt_id: self.add_edge(s, t))
            QTimer.singleShot(0, self._end_connection_mode)
        elif button == Qt.MouseButton.RightButton:
            QTimer.singleShot(0, self._end_connection_mode)

    def handle_connection_move(self, scene_pos):
        if not self._connecting_source_node_id:
            return
            
        if hasattr(self, "_temp_edge_item") and self._temp_edge_item:
            self._temp_edge_item.set_target_pos(scene_pos)
            
        hovered_node = None
        for item in self.items(scene_pos):
            if isinstance(item, NodeItem):
                hovered_node = item
                break
                
        old_hovered = getattr(self, "_hovered_target_node", None)
        if old_hovered != hovered_node:
            if old_hovered:
                old_hovered._hovered_orange = False
                old_hovered.update()
            if hovered_node:
                hovered_node._hovered_orange = True # pyrefly: ignore [missing-attribute]
                hovered_node.update()
            self._hovered_target_node = hovered_node

    def mouseMoveEvent(self, event):
        if getattr(self, "_connecting_source_node_id", None):
            self.handle_connection_move(event.scenePos())
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        if getattr(self, "_connecting_source_node_id", None):
            self.handle_connection_press(event.scenePos(), event.button())
            event.accept()
        else:
            super().mousePressEvent(event)

    def _on_node_moved(self, node_id: str):
        for eitem in self._edge_items.values():
            ed = eitem.edge_data
            if ed.source_id == node_id or ed.target_id == node_id:
                eitem.update_path()

    # ---- Graph role styling -----------------------------------------------

    def _refresh_node_styles(self):
        """Recompute and apply visual roles (basis/sink/reachable/unreachable) to all NodeItems,
        and active/inactive state to all EdgeItems."""
        if self._graph is None:
            return
        reachable = _build_reachable(self._graph)
        sinks = _sink_nodes(self._graph)
        live_edges = _build_live_edges(self._graph)
        basis = self._graph.basis_node_id
        for nid, item in self._node_items.items():
            if nid == basis:
                role = "basis"
            elif nid in sinks and nid in reachable:
                role = "sink"
            elif nid in reachable:
                role = "reachable"
            else:
                role = "unreachable"
            item._node_role = role  # type: ignore[attr-defined]
            item.update()
        # Stamp each edge with whether it is part of the live traversal
        for (src_id, eid), eitem in self._edge_items.items():
            eitem._edge_active = (src_id, eid) in live_edges  # type: ignore[attr-defined]
            eitem.update()

    def set_basis_node(self, node_id: str):
        """Make node_id the new basis (start) node and refresh styles."""
        if self._graph is None:
            return
        self._graph.basis_node_id = node_id
        self._refresh_node_styles()
        self.graph_changed.emit()

    def _node_context_menu(self, node_id: str, screen_pos):
        if self._graph is None:
            return
        menu = QMenu()
        act_edit = menu.addAction("Edit Properties\u2026")
        act_connect_draw = menu.addAction("Draw Edge To\u2026")
        act_connect_list = menu.addAction("Select Edge Target from List\u2026")
        act_self = menu.addAction("Add Self-Edge (repeat this wallpaper)")
        menu.addSeparator()
        is_basis = (self._graph.basis_node_id == node_id)
        act_basis = menu.addAction("\u2605 Set as Start Node" if not is_basis else "\u2605 Already Start Node")
        act_basis.setEnabled(not is_basis)
        menu.addSeparator()
        act_del = menu.addAction("Delete Node")

        chosen = menu.exec(screen_pos)
        if chosen is None:
            return
        if chosen == act_edit:
            self.node_edit_requested.emit(node_id)
        elif chosen == act_self:
            self.add_edge(node_id, node_id)
        elif chosen == act_connect_draw:
            self.start_connection_mode(node_id)
        elif chosen == act_connect_list:
            others = [(nid, lbl) for nid, lbl in self.node_labels() if nid != node_id]
            if not others:
                QMessageBox.information(None, "No Other Nodes",
                                        "Add more nodes to the graph before connecting.")
                return
            dlg = _PickNodeDialog(others, title="Connect to Node")
            if dlg.exec() == QDialog.DialogCode.Accepted and dlg.selected_id:
                self.add_edge(node_id, dlg.selected_id)
        elif chosen == act_basis:
            self.set_basis_node(node_id)
        elif chosen == act_del:
            self._remove_node(node_id)
            self.graph_changed.emit()

    def _edge_context_menu(self, edge_id: int, screen_pos):
        # edge_id is the per-source index; we need source_id from scene items
        for (sid, eid), item in self._edge_items.items():
            if eid == edge_id and item.scene() is self:
                source_id = sid
                break
        else:
            return
        menu = QMenu()
        act_del = menu.addAction(f"Delete Edge #{edge_id}")
        if menu.exec(screen_pos) == act_del:
            self._remove_edge(source_id, edge_id)
            self.graph_changed.emit()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.remove_selected()
        else:
            super().keyPressEvent(event)


# ---------------------------------------------------------------------------
# Graph View
# ---------------------------------------------------------------------------

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
                    scene_pos = QPointF(scene_pos.x() + _NODE_W + 20, scene_pos.y())
            event.acceptProposedAction()
        else:
            super().dropEvent(event)

    def mousePressEvent(self, event):
        from PySide6.QtGui import QMouseEvent
        from PySide6.QtWidgets import QGraphicsItem
        
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
        from PySide6.QtGui import QMouseEvent
        
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
        from PySide6.QtGui import QMouseEvent
        
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


# ---------------------------------------------------------------------------
# Dialogs
# ---------------------------------------------------------------------------

class _PickNodeDialog(QDialog):
    """Simple list dialog to pick a node by label."""

    def __init__(self, node_labels: List[Tuple[str, str]], title: str = "Pick Node",
                 parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.selected_id: Optional[str] = None
        self._id_map: Dict[str, str] = {lbl: nid for nid, lbl in node_labels}

        lyt = QVBoxLayout(self)
        self._list = QListWidget()
        for nid, lbl in node_labels:
            item = QListWidgetItem(lbl)
            item.setData(Qt.ItemDataRole.UserRole, nid)
            self._list.addItem(item)
        self._list.itemDoubleClicked.connect(self._accept)
        lyt.addWidget(self._list)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._accept)
        btns.rejected.connect(self.reject)
        lyt.addWidget(btns)
        self.resize(320, 240)

    def _accept(self):
        items = self._list.selectedItems()
        if items:
            self.selected_id = items[0].data(Qt.ItemDataRole.UserRole)
            self.accept()


class NodeEditDialog(QDialog):
    """Edit a node's file path, display mode and duration."""

    def __init__(self, nd: NodeData, parent=None):
        super().__init__(parent)
        self.nd = nd
        self.setWindowTitle("Edit Wallpaper Node")
        lyt = QVBoxLayout(self)

        # File path
        fp_row = QHBoxLayout()
        self._path_lbl = QLabel(nd.file_path)
        self._path_lbl.setWordWrap(True)
        fp_row.addWidget(self._path_lbl, 1)
        btn_browse = QPushButton("Browse…")
        btn_browse.clicked.connect(self._browse)
        fp_row.addWidget(btn_browse)
        lyt.addLayout(fp_row)

        # Mode
        mode_grp = QGroupBox("Display Mode")
        mode_lyt = QVBoxLayout(mode_grp)
        self._radio_fixed = QRadioButton("Fixed duration")
        self._radio_runtime = QRadioButton("Video runtime (videos only)")
        self._bg = QButtonGroup(self)
        self._bg.addButton(self._radio_fixed)
        self._bg.addButton(self._radio_runtime)
        mode_lyt.addWidget(self._radio_fixed)
        mode_lyt.addWidget(self._radio_runtime)
        lyt.addWidget(mode_grp)

        if nd.display_mode == "video_runtime":
            self._radio_runtime.setChecked(True)
        else:
            self._radio_fixed.setChecked(True)

        # Duration
        dur_row = QHBoxLayout()
        dur_row.addWidget(QLabel("Duration (seconds):"))
        self._dur_spin = QDoubleSpinBox()
        self._dur_spin.setRange(0.5, 86400)
        self._dur_spin.setValue(nd.duration_sec)
        self._dur_spin.setSingleStep(1.0)
        dur_row.addWidget(self._dur_spin)
        lyt.addLayout(dur_row)

        self._radio_fixed.toggled.connect(lambda on: self._dur_spin.setEnabled(on))
        self._dur_spin.setEnabled(nd.display_mode != "video_runtime")

        # Video-runtime only available for videos
        if not _is_video(nd.file_path):
            self._radio_runtime.setEnabled(False)
            self._radio_fixed.setChecked(True)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        lyt.addWidget(btns)
        self.resize(420, 240)

    def _browse(self):
        all_exts = list(SUPPORTED_VIDEO_FORMATS) + [
            f".{e.lower().lstrip('.')}" for e in SUPPORTED_IMG_FORMATS
        ]
        ext_str = " ".join(f"*{e}" for e in all_exts)
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Wallpaper File", "",
            f"Media Files ({ext_str});;All Files (*)",
        )
        if path:
            self.nd.file_path = path
            self._path_lbl.setText(path)
            if not _is_video(path):
                self._radio_runtime.setEnabled(False)
                self._radio_fixed.setChecked(True)
            else:
                self._radio_runtime.setEnabled(True)

    def _save(self):
        self.nd.display_mode = "video_runtime" if self._radio_runtime.isChecked() else "fixed"
        self.nd.duration_sec = self._dur_spin.value()
        self.accept()


# ---------------------------------------------------------------------------
# Main tab widget
# ---------------------------------------------------------------------------

class MonitorDisplaySubTab(WallpaperCommonBase):
    """
    Graph-based wallpaper sequencer per monitor.

    Each monitor gets its own directed graph where:
    - Nodes are wallpaper files (image/video/GIF) with a display duration.
    - Directed edges define the playback sequence (ordered by edge ID).
    - Self-edges allow repeating the same wallpaper.
    - End behavior defines what happens after the last edge is traversed.
    """

    def __init__(self, parent=None):
        WallpaperCommonBase.__init__(self)
        if parent:
            self.setParent(parent)
        self._monitors: List[Monitor] = []
        self._graphs: Dict[str, GraphData] = {}   # monitor_id -> GraphData
        self._current_monitor_id: Optional[str] = None
        self._preview_tmp_dir: Optional[str] = None
        self.background_type: str = "Image"

        self._build_ui()

    # ---- UI construction --------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        # Monitor selector
        sel_box = self.create_monitor_layout_section("Select Monitor")
        root.addWidget(sel_box)

        # Placeholder shown when no monitors are detected
        self._placeholder = QLabel(
            "No monitors detected.\nClick 'Fetch Current Wallpapers' in the System Display(s) tab."
        )
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setStyleSheet("color:#b9bbbe;")

        # Main content: graph + end-behavior (shown once monitors are available)
        graph_content = QWidget()
        graph_content_lyt = QVBoxLayout(graph_content)
        graph_content_lyt.setContentsMargins(0, 0, 0, 0)
        graph_content_lyt.setSpacing(4)

        # Splitter: main vertical splitter (gallery top, graph horizontal layout bottom)
        self._splitter = QSplitter(Qt.Orientation.Vertical)

        # Graph panel
        graph_panel = QWidget()
        graph_lyt = QVBoxLayout(graph_panel)
        graph_lyt.setContentsMargins(0, 0, 0, 0)
        graph_lyt.setSpacing(4)

        # Toolbar
        tb = QHBoxLayout()
        self._btn_add_node = QPushButton("➕ Add Node")
        self._btn_add_node.setToolTip("Add a wallpaper file to the graph")
        self._btn_add_node.clicked.connect(self._add_node)

        self._btn_self_edge = QPushButton("↩ Self-Edge")
        self._btn_self_edge.setToolTip("Add a self-edge to the selected node (repeat it)")
        self._btn_self_edge.clicked.connect(self._add_self_edge)

        self._btn_connect = QPushButton("→ Connect")
        self._btn_connect.setToolTip("Add an edge from the selected node to another")
        self._btn_connect.clicked.connect(self._add_edge)

        self._btn_delete = QPushButton("🗑 Delete")
        self._btn_delete.setToolTip("Delete selected node or edge (Del key also works)")
        self._btn_delete.clicked.connect(self._delete_selected)

        btn_reset_view = QPushButton("⊡ Fit View")
        btn_reset_view.clicked.connect(self._fit_view)

        self._btn_preview = QPushButton("▶ Preview Timelapse")
        self._btn_preview.setToolTip("Generate a temporary preview video and open it")
        self._btn_preview.setStyleSheet(
            "QPushButton { background:#7289da; color:white; border-radius:4px; padding:4px 8px; }"
            "QPushButton:hover { background:#5f73bc; }"
        )
        self._btn_preview.clicked.connect(self._preview_timelapse)

        self._btn_set_start = QPushButton("\u2605 Set Start")
        self._btn_set_start.setToolTip("Mark the selected node as the slideshow start node")
        self._btn_set_start.setStyleSheet(
            "QPushButton { background:#b8860b; color:white; border-radius:4px; padding:4px 8px; }"
            "QPushButton:hover { background:#f1c40f; color:#1a1a00; }"
        )
        self._btn_set_start.clicked.connect(self._set_start_node)

        for btn in [self._btn_add_node, self._btn_self_edge, self._btn_connect,
                    self._btn_delete, btn_reset_view, self._btn_set_start]:
            btn.setFixedHeight(36)
            tb.addWidget(btn)
        tb.addStretch(1)
        self._btn_preview.setFixedHeight(36)
        tb.addWidget(self._btn_preview)
        graph_lyt.addLayout(tb)

        # Scene + View
        self._scene = WallpaperGraphScene(self)
        self._scene.node_edit_requested.connect(self._edit_node)
        self._scene.graph_changed.connect(self._on_graph_changed)
        self._scene.selectionChanged.connect(self._on_selection_changed)

        self._view = WallpaperGraphView(self._scene)
        self._view.setAcceptDrops(True)
        self._view.setMinimumHeight(600)
        graph_lyt.addWidget(self._view, 1)

        # Sequence summary label
        self._seq_label = QLabel("No graph loaded.")
        self._seq_label.setWordWrap(True)
        self._seq_label.setStyleSheet("color:#b9bbbe; font-size:11px; padding:2px;")
        graph_lyt.addWidget(self._seq_label)

        # Gallery panel for dragging and dropping files
        gallery_panel = QGroupBox("Gallery / Drag and Drop")
        gallery_panel.setStyleSheet(
            "QGroupBox { border:1px solid #4f545c; border-radius:6px; margin-top:8px; }"
            "QGroupBox::title { color:white; padding:0 6px; }"
        )
        gallery_lyt = QVBoxLayout(gallery_panel)
        gallery_lyt.setContentsMargins(6, 12, 6, 6)
        gallery_lyt.setSpacing(4)

        # Scan Directory Row
        scan_dir_layout = QHBoxLayout()
        self.scan_directory_path = QLineEdit()
        self.scan_directory_path.setPlaceholderText("Select directory to scan for graph files...")
        self.scan_directory_path.returnPressed.connect(
            lambda: self.populate_scan_image_gallery(self.scan_directory_path.text().strip())
        )
        btn_browse_scan = QPushButton("Browse...")
        apply_shadow_effect(
            btn_browse_scan, color_hex="#000000", radius=8, x_offset=0, y_offset=3
        )
        btn_browse_scan.clicked.connect(self.browse_scan_directory)
        scan_dir_layout.addWidget(QLabel("Scan Directory:"))
        scan_dir_layout.addWidget(self.scan_directory_path)
        scan_dir_layout.addWidget(btn_browse_scan)
        gallery_lyt.addLayout(scan_dir_layout)

        # Search Input
        gallery_lyt.addWidget(self.search_input)

        # Scroll Area for Thumbnails
        self.gallery_scroll_area = MarqueeScrollArea()
        self.gallery_scroll_area.setWidgetResizable(True)
        self.gallery_scroll_area.setStyleSheet(
            "QScrollArea { border: 1px solid #4f545c; background-color: #2c2f33; border-radius: 8px; }"
        )
        self.gallery_scroll_area.setMinimumHeight(600)

        self.scan_thumbnail_widget = QWidget()
        self.scan_thumbnail_widget.setStyleSheet(
            "QWidget { background-color: #2c2f33; }"
        )

        self.scan_thumbnail_layout = QGridLayout(self.scan_thumbnail_widget)
        self.scan_thumbnail_layout.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter
        )
        self.gallery_scroll_area.setWidget(self.scan_thumbnail_widget)
        gallery_lyt.addWidget(self.gallery_scroll_area, 1)

        # Pagination controls
        gallery_lyt.addWidget(
            self.pagination_widget, 0, Qt.AlignmentFlag.AlignCenter
        )

        self.gallery_layout = self.scan_thumbnail_layout

        # Horizontal Splitter for the graph workspace + props panel
        graph_horizontal_splitter = QSplitter(Qt.Orientation.Horizontal)
        graph_horizontal_splitter.addWidget(graph_panel)
        graph_horizontal_splitter.addWidget(self._build_props_panel())
        graph_horizontal_splitter.setSizes([700, 260])

        self._splitter.addWidget(gallery_panel)
        self._splitter.addWidget(graph_horizontal_splitter)
        self._splitter.setSizes([600, 600])

        graph_content_lyt.addWidget(self._splitter, 1)
        graph_content_lyt.addWidget(self._build_end_behavior_bar())

        # Stack: index 0 = placeholder, index 1 = graph content
        self._stack = QStackedWidget()
        self._stack.addWidget(self._placeholder)
        self._stack.addWidget(graph_content)
        self._stack.setCurrentIndex(0)

        root.addWidget(self._stack, 1)

    def _build_props_panel(self) -> QGroupBox:
        grp = QGroupBox("Node Properties")
        grp.setStyleSheet(
            "QGroupBox { border:1px solid #4f545c; border-radius:6px; margin-top:8px; }"
            "QGroupBox::title { color:white; padding:0 6px; }"
        )
        lyt = QVBoxLayout(grp)

        self._props_hint = QLabel("Double-click or right-click a node to edit it.")
        self._props_hint.setWordWrap(True)
        self._props_hint.setStyleSheet("color:#b9bbbe;")
        lyt.addWidget(self._props_hint)

        self._props_file = QLabel()
        self._props_file.setWordWrap(True)
        lyt.addWidget(self._props_file)

        mode_grp = QGroupBox("Display Mode")
        mode_lyt = QVBoxLayout(mode_grp)
        self._props_radio_fixed = QRadioButton("Fixed duration")
        self._props_radio_runtime = QRadioButton("Full video runtime")
        self._props_bg = QButtonGroup(self)
        self._props_bg.addButton(self._props_radio_fixed)
        self._props_bg.addButton(self._props_radio_runtime)
        mode_lyt.addWidget(self._props_radio_fixed)
        mode_lyt.addWidget(self._props_radio_runtime)
        lyt.addWidget(mode_grp)

        dur_row = QHBoxLayout()
        dur_row.addWidget(QLabel("Duration (s):"))
        self._props_dur = QDoubleSpinBox()
        self._props_dur.setRange(0.5, 86400)
        self._props_dur.setSingleStep(1.0)
        dur_row.addWidget(self._props_dur)
        lyt.addLayout(dur_row)

        self._props_apply = QPushButton("Apply")
        self._props_apply.clicked.connect(self._apply_props)
        lyt.addWidget(self._props_apply)

        lyt.addStretch(1)

        # Track which node is being shown in the panel
        self._props_node_id: Optional[str] = None
        self._props_radio_fixed.toggled.connect(
            lambda on: self._props_dur.setEnabled(on)
        )

        # Initially hide the editable parts
        mode_grp.setVisible(False)
        self._props_file.setVisible(False)
        self._props_dur.setEnabled(True)
        for w in [mode_grp, self._props_file, self._props_dur,
                  self._props_apply, dur_row]:
            pass  # shown on demand

        self._props_mode_grp = mode_grp
        self._props_dur_row_widget = None  # updated below

        self._props_mode_grp.setVisible(False)
        self._props_apply.setVisible(False)

        return grp

    def _build_end_behavior_bar(self) -> QGroupBox:
        grp = QGroupBox("End of Graph Behavior")
        grp.setStyleSheet(
            "QGroupBox { border:1px solid #4f545c; border-radius:6px; margin-top:8px; }"
            "QGroupBox::title { color:white; padding:0 6px; }"
        )
        lyt = QHBoxLayout(grp)
        lyt.setContentsMargins(6, 14, 6, 6)

        self._end_combo = QComboBox()
        self._end_combo.addItems([
            "Repeat Graph",
            "Solid Color",
            "Stay on Last Wallpaper",
            "Return to First Wallpaper",
            "Jump to Specific Wallpaper",
        ])
        self._end_combo.currentIndexChanged.connect(self._on_end_behavior_changed)
        lyt.addWidget(self._end_combo)

        # Color picker (only for "Solid Color")
        self._end_color_btn = QPushButton("  Pick Color")
        self._end_color_btn.setVisible(False)
        self._end_color_btn.clicked.connect(self._pick_end_color)
        self._end_color_preview = QLabel("   ")
        self._end_color_preview.setFixedSize(20, 20)
        self._end_color_preview.setVisible(False)
        self._end_color_current = "#000000"
        lyt.addWidget(self._end_color_preview)
        lyt.addWidget(self._end_color_btn)

        # Jump-to node picker (only for "Jump to Specific Wallpaper")
        self._end_jump_combo = QComboBox()
        self._end_jump_combo.setVisible(False)
        lyt.addWidget(self._end_jump_combo)

        lyt.addStretch(1)
        return grp

    # ---- Monitor management -----------------------------------------------

    def update_monitors(self, monitors: List[Monitor]):
        self._monitors = monitors
        self.monitors = monitors
        self.populate_monitor_layout()
        if monitors:
            self._stack.setCurrentIndex(1)
            # Auto-select the first monitor on update if nothing is selected or current is invalid
            if not self._current_monitor_id or self._current_monitor_id not in self.monitor_widgets:
                if self.monitor_widgets:
                    first_id = next(iter(self.monitor_widgets.keys()))
                    self._select_monitor(first_id)
        else:
            self._stack.setCurrentIndex(0)

    def populate_monitor_layout(self):
        super().populate_monitor_layout()
        for m_id, widget in self.monitor_widgets.items():
            widget.clicked.connect(self._select_monitor)

        # If we have a system display reference, sync the images to our newly created widgets!
        if hasattr(self, "_system_display_ref") and self._system_display_ref:
            for mid, sys_widget in self._system_display_ref.monitor_widgets.items():
                widget = self.monitor_widgets.get(mid)
                if widget and sys_widget.image_path:
                    thumb = self._system_display_ref._get_or_generate_thumbnail(sys_widget.image_path)
                    widget.set_image(sys_widget.image_path, thumb)

        # Re-apply selection style to current selected monitor if it exists
        if self._current_monitor_id and self._current_monitor_id in self.monitor_widgets:
            self.monitor_widgets[self._current_monitor_id].set_selected(True)

    def set_system_display_ref(self, system_display):
        self._system_display_ref = system_display

    def on_images_dropped(self, monitor_id: str, image_paths: list):
        if hasattr(self, "_system_display_ref") and self._system_display_ref:
            self._system_display_ref.on_images_dropped(monitor_id, image_paths)

    def handle_monitor_double_click(self, monitor_id: str):
        if hasattr(self, "_system_display_ref") and self._system_display_ref:
            self._system_display_ref.handle_monitor_double_click(monitor_id)

    def handle_clear_monitor_queue(self, monitor_id: str):
        if hasattr(self, "_system_display_ref") and self._system_display_ref:
            self._system_display_ref.handle_clear_monitor_queue(monitor_id)

    def swap_monitors(self, m0: str, m1: str = ""):
        if hasattr(self, "_system_display_ref") and self._system_display_ref:
            self._system_display_ref.swap_monitors(m0, m1)

    def on_monitor_context_menu(self, monitor_id: str, menu: Any):
        if hasattr(self, "_system_display_ref") and self._system_display_ref:
            self._system_display_ref.on_monitor_context_menu(monitor_id, menu)

    def _select_monitor(self, monitor_id: str):
        self._current_monitor_id = monitor_id
        for mid, widget in self.monitor_widgets.items():
            if isinstance(widget, MonitorDropWidget):
                widget.set_selected(mid == monitor_id)
        self._on_monitor_selected(monitor_id)

    @Slot(str)
    def _on_monitor_selected(self, monitor_id: str):
        self._current_monitor_id = monitor_id
        if monitor_id not in self._graphs:
            self._graphs[monitor_id] = GraphData()
        graph = self._graphs[monitor_id]
        self._scene.load_graph(graph)
        self._sync_end_behavior_ui(graph)
        self._update_end_jump_combo()
        self._update_seq_label()
        QTimer.singleShot(50, self._fit_view)

    # ---- Graph operations -------------------------------------------------

    def _current_graph(self) -> Optional[GraphData]:
        if self._current_monitor_id is None:
            return None
        return self._graphs.get(self._current_monitor_id)

    def _add_node(self):
        if self._current_monitor_id is None:
            return
        all_exts = list(SUPPORTED_VIDEO_FORMATS) + [
            f".{e.lower().lstrip('.')}" for e in SUPPORTED_IMG_FORMATS
        ]
        ext_str = " ".join(f"*{e}" for e in all_exts)
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Select Wallpaper File(s)", "",
            f"Media Files ({ext_str});;All Files (*)",
        )
        if not paths:
            return
        center = self._view.mapToScene(self._view.viewport().rect().center())
        spacing = _NODE_W + 20
        for i, path in enumerate(paths):
            pos = QPointF(center.x() + i * spacing - len(paths) * spacing / 2, center.y())
            self._scene.add_node(path, pos)

    def _selected_node_id(self) -> Optional[str]:
        for item in self._scene.selectedItems():
            if isinstance(item, NodeItem):
                return item.node_data.node_id
        return None

    def _add_self_edge(self):
        nid = self._selected_node_id()
        if nid is None:
            QMessageBox.information(self, "No Node Selected",
                                    "Select a node first, then click 'Self-Edge'.")
            return
        self._scene.add_edge(nid, nid)

    def _add_edge(self):
        src_id = self._selected_node_id()
        if src_id is None:
            QMessageBox.information(self, "No Node Selected",
                                    "Select the SOURCE node first, then click 'Connect'.")
            return
        self._scene.start_connection_mode(src_id)

    def _delete_selected(self):
        self._scene.remove_selected()

    def _set_start_node(self):
        nid = self._selected_node_id()
        if nid is None:
            QMessageBox.information(self, "No Node Selected",
                                    "Select a node first, then click '\u2605 Set Start'.")
            return
        self._scene.set_basis_node(nid)

    def _fit_view(self):
        rect = self._scene.itemsBoundingRect()
        if rect.isEmpty():
            self._view.resetTransform()
        else:
            self._view.fitInView(rect.adjusted(-20, -20, 20, 20),
                                 Qt.AspectRatioMode.KeepAspectRatio)

    @Slot(str)
    def _edit_node(self, node_id: str):
        graph = self._current_graph()
        if graph is None:
            return
        nd = graph.nodes.get(node_id)
        if nd is None:
            return
        dlg = NodeEditDialog(nd, parent=self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            # Update the visual
            item = self._scene._node_items.get(node_id)
            if item:
                item.refresh_thumbnail()
                item.update()
            self._on_graph_changed()

    @Slot()
    def _on_graph_changed(self):
        self._scene._refresh_node_styles()
        self._update_seq_label()
        self._update_end_jump_combo()
        graph = self._current_graph()
        if graph:
            # Persist end-behavior selections back to graph
            self._read_end_behavior_to_graph(graph)

    # ---- Properties panel -------------------------------------------------

    @Slot()
    def _on_selection_changed(self):
        items = self._scene.selectedItems()
        for item in items:
            if isinstance(item, NodeItem):
                self._show_node_in_props(item.node_data)
                return
        # Nothing or only edge selected → hide props details
        self._props_hint.setVisible(True)
        self._props_file.setVisible(False)
        self._props_mode_grp.setVisible(False)
        self._props_apply.setVisible(False)
        self._props_node_id = None

    def _show_node_in_props(self, nd: NodeData):
        self._props_node_id = nd.node_id
        self._props_hint.setVisible(False)
        fname = os.path.basename(nd.file_path)
        self._props_file.setText(f"<b>{fname}</b><br><small style='color:#888'>{nd.file_path}</small>")
        self._props_file.setVisible(True)
        self._props_mode_grp.setVisible(True)
        self._props_apply.setVisible(True)
        self._props_dur.setVisible(True)

        is_vid = _is_video(nd.file_path)
        self._props_radio_runtime.setEnabled(is_vid)
        if nd.display_mode == "video_runtime" and is_vid:
            self._props_radio_runtime.setChecked(True)
        else:
            self._props_radio_fixed.setChecked(True)
        self._props_dur.setValue(nd.duration_sec)
        self._props_dur.setEnabled(nd.display_mode != "video_runtime")

    def _apply_props(self):
        graph = self._current_graph()
        if graph is None or self._props_node_id is None:
            return
        nd = graph.nodes.get(self._props_node_id)
        if nd is None:
            return
        nd.display_mode = (
            "video_runtime" if self._props_radio_runtime.isChecked() else "fixed"
        )
        nd.duration_sec = self._props_dur.value()
        item = self._scene._node_items.get(self._props_node_id)
        if item:
            item.update()
        self._update_seq_label()

    # ---- End behavior UI --------------------------------------------------

    _END_KEYS = [
        "repeat_graph",
        "solid_color",
        "stay_last",
        "return_first",
        "jump_to",
    ]

    def _sync_end_behavior_ui(self, graph: GraphData):
        try:
            idx = self._END_KEYS.index(graph.end_behavior)
        except ValueError:
            idx = 0
        self._end_combo.blockSignals(True)
        self._end_combo.setCurrentIndex(idx)
        self._end_combo.blockSignals(False)
        self._end_color_current = graph.end_color
        self._refresh_end_color_preview()
        self._on_end_behavior_changed(idx)

    @Slot(int)
    def _on_end_behavior_changed(self, idx: int):
        is_color = idx == 1
        is_jump = idx == 4
        self._end_color_preview.setVisible(is_color)
        self._end_color_btn.setVisible(is_color)
        self._end_jump_combo.setVisible(is_jump)
        # Persist to graph
        graph = self._current_graph()
        if graph:
            self._read_end_behavior_to_graph(graph)

    def _read_end_behavior_to_graph(self, graph: GraphData):
        idx = self._end_combo.currentIndex()
        graph.end_behavior = self._END_KEYS[idx] if 0 <= idx < len(self._END_KEYS) else "repeat_graph"
        graph.end_color = self._end_color_current
        if graph.end_behavior == "jump_to":
            data = self._end_jump_combo.currentData()
            graph.end_jump_node_id = data if data else None

    def _pick_end_color(self):
        initial = QColor(self._end_color_current)
        col = QColorDialog.getColor(initial, self, "Pick End Color")
        if col.isValid():
            self._end_color_current = col.name().upper()
            self._refresh_end_color_preview()
            graph = self._current_graph()
            if graph:
                graph.end_color = self._end_color_current

    def _refresh_end_color_preview(self):
        self._end_color_preview.setStyleSheet(
            f"background-color:{self._end_color_current}; border:1px solid #4f545c;"
        )

    def _update_end_jump_combo(self):
        self._end_jump_combo.blockSignals(True)
        self._end_jump_combo.clear()
        graph = self._current_graph()
        if graph:
            for nid, lbl in self._scene.node_labels():
                self._end_jump_combo.addItem(lbl, nid)
            if graph.end_jump_node_id:
                for i in range(self._end_jump_combo.count()):
                    if self._end_jump_combo.itemData(i) == graph.end_jump_node_id:
                        self._end_jump_combo.setCurrentIndex(i)
                        break
        self._end_jump_combo.blockSignals(False)

    # ---- Sequence summary -------------------------------------------------

    def _update_seq_label(self):
        graph = self._current_graph()
        if graph is None or (not graph.nodes and not graph.edges):
            self._seq_label.setText("Graph is empty. Add nodes and edges to build the sequence.")
            return
        seq = _build_traversal(graph)
        if not seq:
            self._seq_label.setText("No traversal possible. Add edges connecting the nodes.")
            return
        parts = []
        for i, (fp, dur) in enumerate(seq, 1):
            fname = os.path.basename(fp)
            if len(fname) > 20:
                fname = fname[:17] + "..."
            parts.append(f"[{i}] {fname} ({dur:.0f}s)")
        total = sum(d for _, d in seq)
        self._seq_label.setText(
            f"Sequence ({len(seq)} step{'s' if len(seq) != 1 else ''},"
            f" ~{total:.0f}s total):  "
            + "  →  ".join(parts)
        )

    # ---- Preview ----------------------------------------------------------

    @Slot()
    def _preview_timelapse(self):
        graph = self._current_graph()
        if graph is None:
            return
        seq = _build_traversal(graph)
        if not seq:
            QMessageBox.information(self, "Empty Sequence",
                                    "Add nodes and edges to build a sequence before previewing.")
            return
        if not shutil.which("ffmpeg"):
            QMessageBox.warning(self, "ffmpeg Not Found",
                                "ffmpeg must be installed to generate a preview video.\n"
                                "Install it via your package manager (e.g. sudo apt install ffmpeg).")
            return

        # Clean up previous temp dir
        if self._preview_tmp_dir and os.path.isdir(self._preview_tmp_dir):
            shutil.rmtree(self._preview_tmp_dir, ignore_errors=True)

        self._preview_tmp_dir = tempfile.mkdtemp(prefix="wallpaper_preview_")
        tmp = self._preview_tmp_dir

        self._btn_preview.setText("Generating…")
        self._btn_preview.setEnabled(False)
        QTimer.singleShot(0, lambda: self._generate_preview(seq, tmp))

    def _generate_preview(self, seq: List[Tuple[str, float]], tmp: str):
        try:
            concat_list = os.path.join(tmp, "concat.txt")
            segment_paths = []
            resolution = "1280:720"
            vf_pad = (
                f"scale={resolution}:force_original_aspect_ratio=decrease,"
                f"pad={resolution}:(ow-iw)/2:(oh-ih)/2:black"
            )

            for i, (fp, dur) in enumerate(seq):
                seg = os.path.join(tmp, f"seg{i:04d}.mp4")
                ext = os.path.splitext(fp)[1].lower()
                if ext in SUPPORTED_VIDEO_FORMATS:
                    cmd = ["ffmpeg", "-y", "-i", fp,
                           "-t", str(dur),
                           "-vf", vf_pad,
                           "-c:v", "libx264", "-pix_fmt", "yuv420p",
                           "-an", seg]
                else:
                    cmd = ["ffmpeg", "-y",
                           "-loop", "1", "-i", fp,
                           "-t", str(dur),
                           "-vf", vf_pad,
                           "-c:v", "libx264", "-pix_fmt", "yuv420p",
                           "-an", seg]
                result = subprocess.run(cmd, capture_output=True, timeout=120)
                if result.returncode != 0:
                    raise RuntimeError(
                        f"ffmpeg failed on segment {i}:\n"
                        + result.stderr.decode(errors="replace")[-500:]
                    )
                segment_paths.append(seg)

            with open(concat_list, "w") as f:
                for sp in segment_paths:
                    f.write(f"file '{sp}'\n")

            out_path = os.path.join(tmp, "preview.mp4")
            cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
                   "-i", concat_list, "-c", "copy", out_path]
            result = subprocess.run(cmd, capture_output=True, timeout=120)
            if result.returncode != 0:
                raise RuntimeError(
                    "ffmpeg concat failed:\n"
                    + result.stderr.decode(errors="replace")[-500:]
                )

            self._open_file(out_path)
        except Exception as e:
            QMessageBox.critical(self, "Preview Error", f"Failed to generate preview:\n{e}")
        finally:
            self._btn_preview.setText("▶ Preview Timelapse")
            self._btn_preview.setEnabled(True)

    def _open_file(self, path: str):
        sys_name = platform.system()
        try:
            if sys_name == "Windows":
                os.startfile(path) # pyrefly: ignore [missing-attribute]
            elif sys_name == "Darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            QMessageBox.warning(self, "Open Error", f"Could not open preview:\n{path}\n{e}")

    # ---- Serialization ----------------------------------------------------

    def collect_graphs(self) -> dict:
        self._persist_current()
        return {
            mid: g.to_dict()
            for mid, g in self._graphs.items()
        }

    def restore_graphs(self, data: dict):
        self._graphs = {
            mid: GraphData.from_dict(gd)
            for mid, gd in data.items()
        }
        # Reload current monitor's graph if applicable
        if self._current_monitor_id and self._current_monitor_id in self._graphs:
            graph = self._graphs[self._current_monitor_id]
            self._scene.load_graph(graph)
            self._sync_end_behavior_ui(graph)
            self._update_end_jump_combo()
            self._update_seq_label()

    def _persist_current(self):
        """Flush UI end-behavior state back into the current graph."""
        graph = self._current_graph()
        if graph:
            self._read_end_behavior_to_graph(graph)

    # ---- Thumbnail Actions ------------------------------------------------
    
    @Slot(str)
    def handle_thumbnail_double_click(self, image_path: str):
        if self._current_monitor_id is None:
            return
        center = self._view.mapToScene(self._view.viewport().rect().center())
        self._scene.add_node(image_path, center)

    @Slot(QPoint, str)
    def show_image_context_menu(self, global_pos: QPoint, path: str):
        menu = QMenu(self)

        is_video = path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS))
        view_text = "Play Video" if is_video else "View Full Size Preview"
        view_action = QAction(view_text, self)
        if self._system_display_ref and hasattr(self._system_display_ref, "handle_full_image_preview"):
            view_action.triggered.connect(lambda: self._system_display_ref.handle_full_image_preview(path))
        else:
            view_action.setEnabled(False)
        menu.addAction(view_action)

        add_action = QAction("➕ Add to Graph Canvas", self)
        add_action.triggered.connect(lambda: self.handle_thumbnail_double_click(path))
        menu.addAction(add_action)

        menu.addSeparator()
        delete_action = QAction("🗑️ Delete File (Permanent)", self)
        if self._system_display_ref and hasattr(self._system_display_ref, "handle_delete_image"):
            delete_action.triggered.connect(lambda: self._system_display_ref.handle_delete_image(path))
        else:
            delete_action.setEnabled(False)
        menu.addAction(delete_action)

        menu.exec(global_pos)

    # ---- Cleanup ----------------------------------------------------------

    def closeEvent(self, event):
        if self._preview_tmp_dir and os.path.isdir(self._preview_tmp_dir):
            shutil.rmtree(self._preview_tmp_dir, ignore_errors=True)
        super().closeEvent(event)
