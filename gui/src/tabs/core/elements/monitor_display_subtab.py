import os
import shutil
import sys
import json
import time
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

from backend.src.constants import (
    SUPPORTED_VIDEO_FORMATS,
    SUPPORTED_IMG_FORMATS,
    MONITOR_SLIDESHOW_DAEMON_CONFIG_PATH,
    ROOT_DIR,
)
from backend.src.utils.display import monitor_slideshow_daemon as _monitor_slideshow
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
    Starts from basis_node_id; at each node follows the lowest-edge_id
    outgoing edge that hasn't been used yet (so a self-edge is taken once
    to repeat the node, then the next unused edge continues the chain).
    Each edge can only be consumed once, which bounds the walk to at most
    len(graph.edges) hops and terminates any cycle.
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
    adj: Dict[str, List] = defaultdict(list)
    for src in graph.nodes:
        src_edges = sorted(
            [e for e in graph.edges if e.source_id == src],
            key=lambda e: e.edge_id,
        )
        adj[src] = src_edges

    seq: List[Tuple[str, float]] = []
    used_edges: set = set()  # (source_id, edge_id) — edge_id is only unique per-source
    current = start
    while True:
        nd = graph.nodes.get(current)
        if nd is None:
            break
        seq.append((nd.file_path, _node_duration(nd)))

        next_edge = next(
            (e for e in adj.get(current, [])
             if (e.source_id, e.edge_id) not in used_edges),
            None,
        )
        if next_edge is None:
            break  # no unused outgoing edges — sink or cycle exhausted
        used_edges.add((next_edge.source_id, next_edge.edge_id))
        current = next_edge.target_id

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

        # Per-entry queue durations: monitor_id -> [seconds, ...] parallel to
        # monitor_slideshow_queues[monitor_id]. Local to this subtab (not
        # shared with System Display) since it models the graph-driven,
        # per-item duration semantics unique to this queue export/slideshow.
        self._queue_durations: Dict[str, List[float]] = {}

        # In-app slideshow: delegated to the native scheduler
        # (base.run_monitor_slideshow, via monitor_slideshow_daemon.py) which
        # runs its own std::thread inside this GUI process. It's a
        # process-wide singleton, so only one display's in-app slideshow can
        # be active at a time -- same constraint as the background daemon.
        self._inapp_active_monitor_id: Optional[str] = None

        # Background daemon: only one display can run it at a time (single
        # shared config file / detached process)
        self._daemon_active_monitor_id: Optional[str] = None

        self._build_ui()

        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self._update_queue_status_label)
        self._status_timer.start(1000)
        QTimer.singleShot(500, self._check_daemon_status_on_startup)

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

        # Bottom toolbar: queue export/preview + slideshow controls, plus a
        # per-display timer/counter reflecting the currently selected monitor
        bottom_tb = QHBoxLayout()

        self._btn_export_queue = QPushButton("⇥ Export to Queue")
        self._btn_export_queue.setToolTip(
            "Append the graph's current traversal sequence to the monitor's Wallpaper Queue"
        )
        self._btn_export_queue.setStyleSheet(
            "QPushButton { background:#2ecc71; color:white; border-radius:4px; padding:4px 8px; }"
            "QPushButton:hover { background:#27ae60; }"
        )
        self._btn_export_queue.clicked.connect(self._export_graph_to_queue)

        self._btn_preview = QPushButton("▶ Preview Timelapse")
        self._btn_preview.setToolTip("Generate a temporary preview video and open it")
        self._btn_preview.setStyleSheet(
            "QPushButton { background:#7289da; color:white; border-radius:4px; padding:4px 8px; }"
            "QPushButton:hover { background:#5f73bc; }"
        )
        self._btn_preview.clicked.connect(self._preview_timelapse)

        self._btn_inapp_slideshow = QPushButton("▶ Start In-App Slideshow")
        self._btn_inapp_slideshow.setCheckable(True)
        self._btn_inapp_slideshow.setToolTip(
            "Cycle this display's Wallpaper Queue locally while the app stays open.\n"
            "Each entry uses its own duration (fixed time, or full video runtime)."
        )
        self._btn_inapp_slideshow.setStyleSheet(
            "QPushButton { background:#5865f2; color:white; border-radius:4px; padding:4px 8px; }"
            "QPushButton:hover { background:#4752c4; }"
            "QPushButton:checked { background:#c0392b; }"
            "QPushButton:checked:hover { background:#a93226; }"
        )
        self._btn_inapp_slideshow.clicked.connect(self._toggle_inapp_slideshow)

        self._btn_daemon_slideshow = QPushButton("⏱ Start Slideshow Daemon")
        self._btn_daemon_slideshow.setCheckable(True)
        self._btn_daemon_slideshow.setToolTip(
            "Cycle this display's Wallpaper Queue via a detached background process\n"
            "that keeps running after the app closes. Only one display's daemon can\n"
            "run at a time."
        )
        self._btn_daemon_slideshow.setStyleSheet(
            "QPushButton { background:#b8860b; color:white; border-radius:4px; padding:4px 8px; }"
            "QPushButton:hover { background:#966f09; }"
            "QPushButton:checked { background:#c0392b; }"
            "QPushButton:checked:hover { background:#a93226; }"
        )
        self._btn_daemon_slideshow.clicked.connect(self._toggle_daemon_slideshow)

        for btn in [self._btn_export_queue, self._btn_preview,
                    self._btn_inapp_slideshow, self._btn_daemon_slideshow]:
            btn.setFixedHeight(36)
            bottom_tb.addWidget(btn)

        bottom_tb.addStretch(1)

        self._queue_position_label = QLabel("-- / --")
        self._queue_position_label.setToolTip(
            "Active wallpaper position within this display's Wallpaper Queue"
        )
        self._queue_position_label.setStyleSheet(
            "color:#f1c40f; font-weight:bold; font-size:14px;"
        )
        bottom_tb.addWidget(self._queue_position_label)

        self._queue_timer_label = QLabel("Timer: --:--")
        self._queue_timer_label.setStyleSheet(
            "color:#2ecc71; font-weight:bold; font-size:14px;"
        )
        self._queue_timer_label.setFixedWidth(110)
        bottom_tb.addWidget(self._queue_timer_label)

        graph_lyt.addLayout(bottom_tb)

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
        self._update_slideshow_buttons()
        self._update_queue_status_label()
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
        def do_selection_update():
            try:
                if not self._scene:
                    return
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
            except RuntimeError:
                pass
        QTimer.singleShot(0, do_selection_update)

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

    # ---- Export to Queue ---------------------------------------------------

    @Slot()
    def _export_graph_to_queue(self):
        if self._current_monitor_id is None:
            return
        graph = self._current_graph()
        if graph is None:
            return
        seq = _build_traversal(graph)
        if not seq:
            QMessageBox.information(
                self, "Empty Sequence",
                "Add nodes and edges to build a sequence before exporting to the queue.",
            )
            return

        monitor_id = self._current_monitor_id
        queue = self.monitor_slideshow_queues.setdefault(monitor_id, [])
        # Ensure any pre-existing entries have durations before we append,
        # so the parallel durations list stays index-aligned with the queue.
        durations = self._reconcile_queue_durations(monitor_id)
        was_empty = not queue
        for fp, dur in seq:
            queue.append(fp)
            durations.append(dur)

        if was_empty or not self.monitor_image_paths.get(monitor_id):
            self.monitor_image_paths[monitor_id] = queue[0]
            self.monitor_current_index[monitor_id] = 0

        self.update_monitor_widget_ui(monitor_id)
        self._refresh_open_queue_window(monitor_id)
        self.check_all_monitors_set()
        self._update_queue_status_label()

        QMessageBox.information(
            self, "Exported to Queue",
            f"Appended {len(seq)} item{'s' if len(seq) != 1 else ''} from the graph "
            f"to the Wallpaper Queue, each with its own duration from the graph.",
        )

    # ---- Per-entry queue durations -----------------------------------------

    def _default_entry_duration(self, path: str) -> float:
        """Full runtime for a video, else the default fixed duration -- the
        same fallback semantics used for graph nodes without an explicit
        duration (see _node_duration)."""
        if path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS)):
            dur = _get_video_duration(path)
            if dur:
                return dur
        return 30.0

    def _reconcile_queue_durations(self, monitor_id: str) -> List[float]:
        """Keep self._queue_durations[monitor_id] index-aligned with
        monitor_slideshow_queues[monitor_id], padding new entries (added by
        drag/drop, the context menu, etc.) with a sensible default and
        truncating stale ones. Returns the (mutable) durations list."""
        queue = self.monitor_slideshow_queues.get(monitor_id, [])
        durations = self._queue_durations.setdefault(monitor_id, [])
        if len(durations) < len(queue):
            durations.extend(
                self._default_entry_duration(p) for p in queue[len(durations):]
            )
        elif len(durations) > len(queue):
            del durations[len(queue):]
        return durations

    @Slot(str, list)
    def on_queue_reordered(self, monitor_id: str, new_queue: List[str]):
        super().on_queue_reordered(monitor_id, new_queue)
        # A manual drag-reorder in the Wallpaper Queue window carries no
        # duration metadata, so the old index-aligned durations no longer
        # correspond to the right entries. Reset rather than risk silently
        # misapplying a stale duration to the wrong item; the next
        # reconcile recomputes sane per-item defaults.
        self._queue_durations[monitor_id] = []

    def handle_item_swap_request(self, s_mid: str, s_idx: int, t_mid: str, t_idx: int):
        s_durs = self._reconcile_queue_durations(s_mid)
        t_durs = self._reconcile_queue_durations(t_mid)
        super().handle_item_swap_request(s_mid, s_idx, t_mid, t_idx)
        if s_idx < len(s_durs) and t_idx < len(t_durs):
            s_durs[s_idx], t_durs[t_idx] = t_durs[t_idx], s_durs[s_idx]

    # ---- In-app slideshow ---------------------------------------------------
    #
    # Delegated to base.run_monitor_slideshow (base/src/utils/monitor_slideshow.cpp)
    # via monitor_slideshow_daemon.start()/stop()/status(). That native
    # scheduler runs its own std::thread inside this GUI process and calls
    # WallpaperManager.apply_wallpaper back on each tick -- independent of
    # the Qt event loop and GIL, so it keeps advancing reliably even if
    # something on the Python/Qt side stalls.

    @Slot()
    def _toggle_inapp_slideshow(self):
        monitor_id = self._current_monitor_id
        if monitor_id is None:
            return
        if self._inapp_active_monitor_id == monitor_id:
            self._stop_inapp_slideshow()
        else:
            self._start_inapp_slideshow(monitor_id)

    def _start_inapp_slideshow(self, monitor_id: str):
        queue = self.monitor_slideshow_queues.get(monitor_id, [])
        if not queue:
            QMessageBox.information(
                self, "Empty Queue",
                "This display's Wallpaper Queue is empty. Use 'Export to Queue' "
                "or drop files onto the monitor first.",
            )
            self._update_slideshow_buttons()
            return
        if self._daemon_active_monitor_id == monitor_id:
            QMessageBox.warning(
                self, "Slideshow Conflict",
                "The Slideshow Daemon is running for this display. "
                "Stop it before starting the in-app slideshow.",
            )
            self._update_slideshow_buttons()
            return
        if self._inapp_active_monitor_id and self._inapp_active_monitor_id != monitor_id:
            reply = QMessageBox.question(
                self, "Slideshow Already Running",
                "The in-app slideshow is already running for another display "
                f"(Monitor {self._inapp_active_monitor_id}). Only one display "
                "can run it at a time. Switch it to this display?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                self._update_slideshow_buttons()
                return
            self._stop_inapp_slideshow()

        durations = self._reconcile_queue_durations(monitor_id)

        style = "Fill"
        video_style = "Scaled and Cropped"
        if getattr(self, "_system_display_ref", None):
            style = getattr(self._system_display_ref, "wallpaper_style", style)
            video_style = getattr(self._system_display_ref, "video_style", video_style)

        other_paths = {
            mid: p for mid, p in self.monitor_image_paths.items()
            if mid != monitor_id and p
        }

        try:
            _monitor_slideshow.start(
                monitor_id, queue, durations,
                monitors=self.monitors,
                style=style,
                video_style=video_style,
                other_paths=other_paths,
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to start in-app slideshow: {e}")
            self._update_slideshow_buttons()
            return

        self._inapp_active_monitor_id = monitor_id
        self._update_slideshow_buttons()
        self._update_queue_status_label()

    def _stop_inapp_slideshow(self):
        if self._inapp_active_monitor_id is None:
            return
        try:
            _monitor_slideshow.stop()
        except Exception:
            pass
        self._inapp_active_monitor_id = None
        self._update_slideshow_buttons()
        self._update_queue_status_label()

    def _sync_inapp_state_from_native(self, monitor_id: str, status: dict):
        """The native scheduler applies wallpapers directly via
        WallpaperManager (off the Qt thread), so it never touches this
        subtab's own bookkeeping. Reconcile monitor_image_paths / the
        current-index / the drop-widget thumbnail from the native status on
        each poll tick so the rest of the UI (queue window highlighting,
        "Set Active Wallpaper from Queue" checkmarks, etc.) stays in sync."""
        idx = status.get("current_index")
        if idx is None or idx < 0:
            return
        queue = self.monitor_slideshow_queues.get(monitor_id, [])
        if not (0 <= idx < len(queue)):
            return
        path = queue[idx]
        if self.monitor_image_paths.get(monitor_id) == path:
            return
        self.monitor_image_paths[monitor_id] = path
        self.monitor_current_index[monitor_id] = idx
        self.update_monitor_widget_ui(monitor_id)
        self.check_all_monitors_set()

    # ---- Background slideshow daemon ---------------------------------------

    def _read_daemon_status(self) -> Optional[dict]:
        try:
            with open(MONITOR_SLIDESHOW_DAEMON_CONFIG_PATH, "r") as f:
                return json.load(f)
        except Exception:
            return None

    def _check_daemon_status_on_startup(self):
        status = self._read_daemon_status()
        if status and status.get("running"):
            self._daemon_active_monitor_id = str(status.get("monitor_id"))
            self._update_slideshow_buttons()
            self._update_queue_status_label()

    @Slot()
    def _toggle_daemon_slideshow(self):
        monitor_id = self._current_monitor_id
        if monitor_id is None:
            return
        if self._daemon_active_monitor_id == monitor_id:
            self._stop_daemon_slideshow()
        else:
            self._start_daemon_slideshow(monitor_id)

    def _start_daemon_slideshow(self, monitor_id: str):
        queue = self.monitor_slideshow_queues.get(monitor_id, [])
        if not queue:
            QMessageBox.information(
                self, "Empty Queue",
                "This display's Wallpaper Queue is empty. Use 'Export to Queue' "
                "or drop files onto the monitor first.",
            )
            self._update_slideshow_buttons()
            return
        if self._inapp_active_monitor_id == monitor_id:
            QMessageBox.warning(
                self, "Slideshow Conflict",
                "The in-app slideshow is running for this display. "
                "Stop it before starting the Slideshow Daemon.",
            )
            self._update_slideshow_buttons()
            return
        if self._daemon_active_monitor_id and self._daemon_active_monitor_id != monitor_id:
            reply = QMessageBox.question(
                self, "Daemon Already Running",
                "The Slideshow Daemon is already running for another display "
                f"(Monitor {self._daemon_active_monitor_id}). Only one display "
                "can run the daemon at a time. Switch it to this display?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                self._update_slideshow_buttons()
                return
            self._stop_daemon_slideshow()

        durations = self._reconcile_queue_durations(monitor_id)

        style = "Fill"
        video_style = "Scaled and Cropped"
        if getattr(self, "_system_display_ref", None):
            style = getattr(self._system_display_ref, "wallpaper_style", style)
            video_style = getattr(self._system_display_ref, "video_style", video_style)

        other_paths = {
            mid: p for mid, p in self.monitor_image_paths.items()
            if mid != monitor_id and p
        }
        geometries = {
            str(i): {"x": m.x, "y": m.y, "width": m.width, "height": m.height}
            for i, m in enumerate(self.monitors)
        }
        current_path = self.monitor_image_paths.get(monitor_id)
        current_index = queue.index(current_path) if current_path in queue else -1

        config = {
            "running": True,
            "monitor_id": monitor_id,
            "queue": list(queue),
            "durations": list(durations),
            "style": style,
            "video_style": video_style,
            "monitor_geometries": geometries,
            "other_current_paths": other_paths,
            "current_index": current_index,
            "last_change_timestamp": 0,
        }
        try:
            MONITOR_SLIDESHOW_DAEMON_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(MONITOR_SLIDESHOW_DAEMON_CONFIG_PATH, "w") as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to write daemon config: {e}")
            return

        script_path = ROOT_DIR / "backend" / "src" / "utils" / "display" / "monitor_slideshow_daemon.py"
        if not script_path.exists():
            QMessageBox.critical(self, "Error", f"Daemon script not found at:\n{script_path}")
            return
        try:
            if platform.system() == "Windows":
                subprocess.Popen(
                    [sys.executable, str(script_path)],
                    creationflags=subprocess.CREATE_NO_WINDOW, # pyrefly: ignore [missing-attribute]
                )
            else:
                subprocess.Popen(
                    [sys.executable, str(script_path)],
                    start_new_session=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to start daemon: {e}")
            return

        self._daemon_active_monitor_id = monitor_id
        self._update_slideshow_buttons()
        self._update_queue_status_label()

    def _stop_daemon_slideshow(self):
        try:
            if MONITOR_SLIDESHOW_DAEMON_CONFIG_PATH.exists():
                with open(MONITOR_SLIDESHOW_DAEMON_CONFIG_PATH, "r") as f:
                    config = json.load(f)
                config["running"] = False
                with open(MONITOR_SLIDESHOW_DAEMON_CONFIG_PATH, "w") as f:
                    json.dump(config, f, indent=2)
        except Exception:
            pass
        self._daemon_active_monitor_id = None
        self._update_slideshow_buttons()
        self._update_queue_status_label()

    # ---- Slideshow status UI -------------------------------------------------

    def _update_slideshow_buttons(self):
        monitor_id = self._current_monitor_id
        inapp_running = bool(monitor_id and self._inapp_active_monitor_id == monitor_id)
        daemon_running = bool(monitor_id and self._daemon_active_monitor_id == monitor_id)

        self._btn_inapp_slideshow.blockSignals(True)
        self._btn_inapp_slideshow.setChecked(inapp_running)
        self._btn_inapp_slideshow.setText(
            "⏹ Stop In-App Slideshow" if inapp_running else "▶ Start In-App Slideshow"
        )
        self._btn_inapp_slideshow.blockSignals(False)

        self._btn_daemon_slideshow.blockSignals(True)
        self._btn_daemon_slideshow.setChecked(daemon_running)
        self._btn_daemon_slideshow.setText(
            "⏹ Stop Slideshow Daemon" if daemon_running else "⏱ Start Slideshow Daemon"
        )
        self._btn_daemon_slideshow.blockSignals(False)

    def _update_queue_status_label(self):
        monitor_id = self._current_monitor_id
        if monitor_id is None:
            self._queue_position_label.setText("-- / --")
            self._queue_timer_label.setText("Timer: --:--")
            return

        queue = self.monitor_slideshow_queues.get(monitor_id, [])
        total = len(queue)
        idx = self.monitor_current_index.get(monitor_id, -1)
        remaining: Optional[int] = None

        if self._inapp_active_monitor_id == monitor_id:
            status = _monitor_slideshow.status()
            if status and status.get("running"):
                self._sync_inapp_state_from_native(monitor_id, status)
                idx = status.get("current_index", idx)
                if idx is not None and idx < 0:
                    idx = -1
                last_change = status.get("last_change_timestamp", 0)
                dur = status.get("current_duration")
                if dur and last_change > 0:
                    remaining = max(0, int(round(dur - (time.time() - last_change))))
        elif self._daemon_active_monitor_id == monitor_id:
            status = self._read_daemon_status()
            if status and status.get("running"):
                daemon_idx = status.get("current_index")
                if daemon_idx is not None:
                    idx = daemon_idx
                last_change = status.get("last_change_timestamp", 0)
                dur = status.get("current_duration")
                if dur and last_change > 0:
                    remaining = max(0, int(round(dur - (time.time() - last_change))))

        current_num = idx + 1 if 0 <= idx < total else 0
        self._queue_position_label.setText(f"{current_num} / {total}" if total else "-- / --")

        if remaining is not None:
            m, s = divmod(remaining, 60)
            self._queue_timer_label.setText(f"Timer: {m:02}:{s:02}")
        else:
            self._queue_timer_label.setText("Timer: --:--")

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
        # In-app slideshows only make sense "while the user remains in-app",
        # so stop the native scheduler here. The background daemon is
        # intentionally left running -- that is its whole point.
        if self._inapp_active_monitor_id is not None:
            self._stop_inapp_slideshow()

        if self._preview_tmp_dir and os.path.isdir(self._preview_tmp_dir):
            shutil.rmtree(self._preview_tmp_dir, ignore_errors=True)
        super().closeEvent(event)
