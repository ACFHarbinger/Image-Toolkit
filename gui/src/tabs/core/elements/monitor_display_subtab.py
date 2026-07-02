import os
import shutil
import tempfile
import subprocess
import platform
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import Qt, QPointF, QTimer, Slot, QPoint
from PySide6.QtGui import QAction, QColor
from PySide6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QGroupBox, QDialog,
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QRadioButton, QButtonGroup, QStackedWidget,
    QFileDialog, QMessageBox, QMenu, QLabel,
    QLineEdit, QGridLayout, QPushButton,
)
from screeninfo import Monitor

from backend.src.constants import SUPPORTED_VIDEO_FORMATS, SUPPORTED_IMG_FORMATS
from .common.wallpaper_common_base import WallpaperCommonBase
from .graph.data import NodeData, GraphData
from ....components import MarqueeScrollArea
from ....styles.style import apply_shadow_effect

from .graph import (
    NodeItem, NODE_W, is_video,
    WallpaperGraphScene, WallpaperGraphView,
    NodeEditDialog,
)


_VIDEO_DURATION_CACHE: Dict[str, float] = {}


def _get_video_duration(path: str) -> Optional[float]:
    """Return video duration in seconds via ffprobe or cv2."""
    if path in _VIDEO_DURATION_CACHE:
        return _VIDEO_DURATION_CACHE[path]
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True, timeout=10,
        )
        val = result.stdout.strip()
        if val:
            dur = float(val)
            _VIDEO_DURATION_CACHE[path] = dur
            return dur
    except Exception:
        pass
    try:
        import cv2  # type: ignore
        cap = cv2.VideoCapture(path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        cap.release()
        if fps > 0:
            dur = frames / fps
            _VIDEO_DURATION_CACHE[path] = dur
            return dur
    except Exception:
        pass
    return None


def _node_duration(nd: NodeData) -> float:
    if nd.display_mode == "video_runtime":
        dur = _get_video_duration(nd.file_path)
        return dur if dur else nd.duration_sec
    return nd.duration_sec


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

        self._btn_clear_graph = QPushButton("🗑 Clear Graph")
        self._btn_clear_graph.setToolTip("Reset the graph and clear all nodes and edges")
        self._btn_clear_graph.setStyleSheet(
            "QPushButton { background:#992d22; color:white; border-radius:4px; padding:4px 8px; }"
            "QPushButton:hover { background:#c0392b; }"
        )
        self._btn_clear_graph.clicked.connect(self._clear_canvas)

        for btn in [self._btn_add_node, self._btn_self_edge, self._btn_connect,
                    self._btn_delete, btn_reset_view, self._btn_set_start, self._btn_clear_graph]:
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
        spacing = NODE_W + 20
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

    def _clear_canvas(self):
        if self._current_monitor_id is None:
            return
        self.clear_monitor_graph(self._current_monitor_id)

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

        is_vid = is_video(nd.file_path)
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
        from PySide6.QtWidgets import QColorDialog
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
                os.startfile(path)  # pyrefly: ignore [missing-attribute]
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
