import os
import uuid
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

from PySide6.QtCore import Qt, Signal, QPointF, QTimer, QRectF, QRect
from PySide6.QtGui import QKeyEvent, QColor, QPen, QPainter, QPainterPath
from PySide6.QtWidgets import (
    QGraphicsScene, QMenu, QMessageBox, QDialog,
    QListWidget, QListWidgetItem, QDialogButtonBox, QVBoxLayout,
)

from .data import NodeData, EdgeData, GraphData
from .node_item import NodeItem, is_video, NODE_W, NODE_H
from .edge_item import EdgeItem


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

    # Map source_id -> edges sorted by edge_id (ascending)
    adj: Dict[str, List[EdgeData]] = defaultdict(list)
    for src in graph.nodes:
        # Keep all edges sorted by ID
        src_edges = sorted(
            [e for e in graph.edges if e.source_id == src],
            key=lambda e: e.edge_id,
        )
        adj[src] = src_edges

    live: set = set()
    visited: set = set()
    
    # Use a queue or stack for traversal to handle complex paths
    # that aren't just a simple line.
    stack = [start]
    while stack:
        current = stack.pop()
        if current in visited:
            continue
        visited.add(current)
        
        edges_here = adj.get(current, [])
        for edge in edges_here:
            # 1. MARK ALL OUTGOING EDGES AS LIVE
            live.add((edge.source_id, edge.edge_id))
            
            # 2. Add target to stack to continue traversal
            if edge.target_id not in visited:
                stack.append(edge.target_id)

    return live


class WallpaperGraphScene(QGraphicsScene):
    node_edit_requested = Signal(str)   # node_id
    graph_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._graph: Optional[GraphData] = None
        self._node_items: Dict[str, NodeItem] = {}
        self._edge_items: Dict[Tuple[str, int], EdgeItem] = {}
        self._connecting_source_node_id: Optional[str] = None
        self._temp_connection_pos: Optional[QPointF] = None
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
        is_vid = is_video(file_path)
        display_mode = "video_runtime" if is_vid else "fixed"
        nd = NodeData(node_id=nid, file_path=file_path,
                      display_mode=display_mode, duration_sec=30.0,
                      pos_x=pos.x(), pos_y=pos.y())
        self._graph.nodes[nid] = nd # pyrefly: ignore [missing-attribute]
        if self._graph.basis_node_id is None: # pyrefly: ignore [missing-attribute]
            self._graph.basis_node_id = nid # pyrefly: ignore [missing-attribute]
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
            
        def do_start():
            self._connecting_source_node_id = source_node_id
            
            from PySide6.QtGui import QCursor
            views = self.views()
            if views:
                view = views[0]
                local_pos = view.mapFromGlobal(QCursor.pos())
                scene_pos = view.mapToScene(local_pos)
                self._temp_connection_pos = scene_pos
            else:
                self._temp_connection_pos = QPointF(0, 0)
            self.update()
            
        QTimer.singleShot(0, do_start)

    def _end_connection_mode(self):
        old_hovered = getattr(self, "_hovered_target_node", None)
        if old_hovered:
            try:
                old_hovered._hovered_orange = False
                old_hovered.update()
            except RuntimeError:
                pass
        self._hovered_target_node = None
        self._connecting_source_node_id = None
        self._temp_connection_pos = None
        self.update()

    def handle_connection_press(self, scene_pos, button):
        if not self._connecting_source_node_id:
            return
            
        src_id = self._connecting_source_node_id
            
        if button == Qt.MouseButton.LeftButton:
            target_node = getattr(self, "_hovered_target_node", None)
            if not target_node:
                for item in self._node_items.values():
                    if item.boundingRect().translated(item.pos()).contains(scene_pos):
                        target_node = item
                        break
            if target_node:
                tgt_id = target_node.node_data.node_id
                QTimer.singleShot(0, lambda s=src_id, t=tgt_id: self.add_edge(s, t))
            self._end_connection_mode()
        elif button == Qt.MouseButton.RightButton:
            self._end_connection_mode()

    def handle_connection_move(self, scene_pos):
        if not self._connecting_source_node_id:
            return
            
        self._temp_connection_pos = scene_pos
        self.update()
            
        hovered_node = None
        for item in self._node_items.values():
            if item.boundingRect().translated(item.pos()).contains(scene_pos):
                hovered_node = item
                break
                
        old_hovered = getattr(self, "_hovered_target_node", None)
        if old_hovered != hovered_node:
            if old_hovered:
                try:
                    old_hovered._hovered_orange = False
                    old_hovered.update()
                except RuntimeError:
                    pass
            if hovered_node:
                try:
                    hovered_node._hovered_orange = True # pyrefly: ignore [missing-attribute]
                    hovered_node.update()
                except RuntimeError:
                    pass
            self._hovered_target_node = hovered_node

    def drawForeground(self, painter: QPainter, rect: QRect | QRectF):
        super().drawForeground(painter, rect)
        if not getattr(self, "_connecting_source_node_id", None):
            return
            
        source_item = self._node_items.get(self._connecting_source_node_id)
        if not source_item:
            return
            
        try:
            sp = source_item.pos() + QPointF(NODE_W / 2, NODE_H / 2)
            tp = getattr(self, "_temp_connection_pos", None)
            if tp is None:
                return
                
            mx = (sp.x() + tp.x()) / 2
            my = (sp.y() + tp.y()) / 2 - 30
            path = QPainterPath()
            path.moveTo(sp)
            path.quadTo(QPointF(mx, my), tp)
            
            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            color = QColor("#f39c12")
            pen = QPen(color, 2, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)
            painter.restore()
        except Exception:
            pass

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
            item._node_role = role # pyrefly: ignore [missing-attribute]
            item.update()
        # Stamp each edge with whether it is part of the live traversal
        for (src_id, eid), eitem in self._edge_items.items():
            eitem._edge_active = (src_id, eid) in live_edges # pyrefly: ignore [missing-attribute]
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
