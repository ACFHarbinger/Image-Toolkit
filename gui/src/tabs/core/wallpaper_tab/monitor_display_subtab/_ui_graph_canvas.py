"""Main layout/toolbar/graph-canvas/gallery UI builder for ``MonitorDisplaySubTab``.

Extracted from ``MonitorDisplaySubTab._build_ui`` -- pure code motion, no
logic change, to keep the file under the codebase's 500-code-line
convention (§5.17).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, cast

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .....components import MarqueeScrollArea
from .....styles import apply_shadow_effect, set_button_role
from ..graph import WallpaperGraphScene, WallpaperGraphView

if TYPE_CHECKING:
    from ...protos.monitor_display_subtab import MonitorDisplaySubTabHostProtocol


class _UIGraphCanvasMixin:
    """Builds the placeholder/graph-content stack, toolbar, canvas, and gallery."""

    scan_directory_path: Optional[QLineEdit]
    gallery_scroll_area: Optional[QScrollArea]
    gallery_layout: Optional[QGridLayout]

    def _build_ui(self: "MonitorDisplaySubTabHostProtocol"):
        root = QVBoxLayout(cast(QWidget, self))
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(6)

        # Monitor selector
        sel_box = self.create_monitor_layout_section("Select Monitor (Drag to Reorder)")
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

        self._build_graph_toolbar(graph_lyt)

        # Scene + View
        self._scene = WallpaperGraphScene(self)
        self._scene.node_edit_requested.connect(self._edit_node)
        self._scene.graph_changed.connect(self._on_graph_changed)
        self._scene.selectionChanged.connect(self._on_selection_changed)

        self._view = WallpaperGraphView(self._scene)
        self._view.setAcceptDrops(True)
        self._view.setMinimumHeight(600)
        graph_lyt.addWidget(self._view, 1)

        self._build_bottom_toolbar(graph_lyt)

        # Sequence summary label
        self._seq_label = QLabel("No graph loaded.")
        self._seq_label.setWordWrap(True)
        self._seq_label.setStyleSheet("color:#b9bbbe; font-size:11px; padding:2px;")
        graph_lyt.addWidget(self._seq_label)

        gallery_panel = self._build_gallery_panel()

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

    def _build_graph_toolbar(self: "MonitorDisplaySubTabHostProtocol", graph_lyt) -> None:
        tb = QHBoxLayout()
        graph_lbl = QLabel("Graph Canvas")
        graph_lbl.setStyleSheet("font-weight: bold; padding: 4px;")
        tb.addWidget(graph_lbl)
        tb.addStretch(1)

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
        set_button_role(self._btn_delete, "danger")
        self._btn_delete.clicked.connect(self._delete_selected)

        btn_reset_view = QPushButton("⊡ Fit View")
        btn_reset_view.clicked.connect(self._fit_view)

        self._btn_set_start = QPushButton("★ Set Start")
        self._btn_set_start.setToolTip("Mark the selected node as the slideshow start node")
        self._btn_set_start.clicked.connect(self._set_start_node)

        self._btn_clear_graph = QPushButton("🗑 Clear Graph")
        self._btn_clear_graph.setToolTip("Reset the graph and clear all nodes and edges")
        set_button_role(self._btn_clear_graph, "danger")
        self._btn_clear_graph.clicked.connect(self._clear_canvas)

        for btn in [self._btn_add_node, self._btn_self_edge, self._btn_connect,
                    self._btn_delete, btn_reset_view, self._btn_set_start, self._btn_clear_graph]:
            btn.setFixedHeight(36)
            tb.addWidget(btn)
        graph_lyt.addLayout(tb)

    def _build_bottom_toolbar(self: "MonitorDisplaySubTabHostProtocol", graph_lyt) -> None:
        # Bottom toolbar: queue export/preview + slideshow controls, plus a
        # per-display timer/counter reflecting the currently selected monitor
        bottom_tb = QHBoxLayout()

        self._btn_export_queue = QPushButton("⇥ Export to Queue")
        self._btn_export_queue.setToolTip(
            "Append the graph's current traversal sequence to the monitor's Wallpaper Queue"
        )
        set_button_role(self._btn_export_queue, "success")
        self._btn_export_queue.clicked.connect(self._export_graph_to_queue)

        self._btn_preview = QPushButton("▶ Preview Timelapse")
        self._btn_preview.setToolTip("Generate a temporary preview video and open it")
        self._btn_preview.clicked.connect(self._preview_timelapse)

        self._btn_inapp_slideshow = QPushButton("▶ Start In-App Slideshow")
        self._btn_inapp_slideshow.setCheckable(True)
        self._btn_inapp_slideshow.setToolTip(
            "Cycle this display's Wallpaper Queue locally while the app stays open.\n"
            "Each entry uses its own duration (fixed time, or full video runtime)."
        )
        set_button_role(self._btn_inapp_slideshow, "success")
        self._btn_inapp_slideshow.clicked.connect(self._toggle_inapp_slideshow)

        self._btn_daemon_slideshow = QPushButton("⏱ Start Slideshow Daemon")
        self._btn_daemon_slideshow.setCheckable(True)
        self._btn_daemon_slideshow.setToolTip(
            "Cycle this display's Wallpaper Queue via a detached background process\n"
            "that keeps running after the app closes. Only one display's daemon can\n"
            "run at a time."
        )
        set_button_role(self._btn_daemon_slideshow, "success")
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

    def _build_gallery_panel(self: "MonitorDisplaySubTabHostProtocol") -> QGroupBox:
        # Gallery panel for dragging and dropping files
        gallery_panel = QGroupBox("Gallery / Drag and Drop")
        gallery_lyt = QVBoxLayout(gallery_panel)
        gallery_lyt.setContentsMargins(6, 12, 6, 6)
        gallery_lyt.setSpacing(4)

        # Scan Directory Row
        scan_dir_layout = QHBoxLayout()
        scan_directory_path = QLineEdit()
        self.scan_directory_path = scan_directory_path
        scan_directory_path.setPlaceholderText("Select directory to scan for graph files...")
        scan_directory_path.returnPressed.connect(
            lambda: self.populate_scan_image_gallery(scan_directory_path.text().strip())
        )
        btn_browse_scan = QPushButton("Browse...")
        apply_shadow_effect(
            btn_browse_scan, color_hex="#000000", radius=8, x_offset=0, y_offset=3
        )
        btn_browse_scan.clicked.connect(self.browse_scan_directory)
        scan_dir_layout.addWidget(QLabel("Scan Directory:"))
        scan_dir_layout.addWidget(scan_directory_path)
        scan_dir_layout.addWidget(btn_browse_scan)
        gallery_lyt.addLayout(scan_dir_layout)

        # Search Input
        gallery_lyt.addWidget(self.search_input)

        # Virtual-scroll gallery (GUI/UX §2.1 Option A) — replaces the
        # MarqueeScrollArea + QGridLayout grid; pagination is dropped.
        self.gallery = self._build_virtual_gallery()
        self.gallery_scroll_area = self.gallery  # setEnabled() callers
        gallery_lyt.addWidget(self.gallery, 1)

        return gallery_panel


__all__ = ["_UIGraphCanvasMixin"]
