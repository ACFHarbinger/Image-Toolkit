"""Node-properties panel + end-of-graph-behavior bar UI builder.

Extracted from ``MonitorDisplaySubTab`` -- pure code motion, no logic change
(see ``_ui_graph_canvas.py``'s docstring).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, cast

from PySide6.QtCore import QObject, Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
)

if TYPE_CHECKING:
    from ...protos.monitor_display_subtab import MonitorDisplaySubTabHostProtocol


class _UIPropsEndMixin:
    """Builds the "Node Properties" panel and the "End of Graph Behavior" bar."""

    def _build_props_panel(self: "MonitorDisplaySubTabHostProtocol") -> QGroupBox:
        grp = QGroupBox("Node Properties")
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
        self._props_bg = QButtonGroup(cast(QObject, self))
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

        # Outgoing edges: create, remove, and reorder edges sourced from
        # this node directly here, instead of only via the canvas.
        edges_grp = QGroupBox("Outgoing Edges")
        edges_lyt = QVBoxLayout(edges_grp)

        edges_hint = QLabel(
            "Playback always follows the topmost edge first. Drag to "
            "reorder, right-click to remove."
        )
        edges_hint.setWordWrap(True)
        edges_hint.setStyleSheet("color:#b9bbbe; font-size:10px;")
        edges_lyt.addWidget(edges_hint)

        self._props_edges_list = QListWidget()
        self._props_edges_list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self._props_edges_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self._props_edges_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self._props_edges_list.setMaximumHeight(140)
        self._props_edges_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._props_edges_list.customContextMenuRequested.connect(
            self._props_edges_context_menu
        )
        edges_lyt.addWidget(self._props_edges_list)
        # Populated on drop via the model's rowsMoved signal
        self._props_edges_list.model().rowsMoved.connect(
            self._on_props_edges_reordered
        )

        add_edge_row = QHBoxLayout()
        self._props_edge_target_combo = QComboBox()
        add_edge_row.addWidget(self._props_edge_target_combo, 1)
        add_edge_row.addWidget(QLabel("×"))
        self._props_edge_repeat_spin = QSpinBox()
        self._props_edge_repeat_spin.setRange(1, 999)
        self._props_edge_repeat_spin.setValue(1)
        self._props_edge_repeat_spin.setToolTip(
            "Number of times the target wallpaper repeats back-to-back "
            "when this edge is taken"
        )
        self._props_edge_repeat_spin.setFixedWidth(56)
        add_edge_row.addWidget(self._props_edge_repeat_spin)
        self._props_edge_add_btn = QPushButton("+ Add Edge")
        self._props_edge_add_btn.clicked.connect(self._add_props_edge)
        add_edge_row.addWidget(self._props_edge_add_btn)
        edges_lyt.addLayout(add_edge_row)

        lyt.addWidget(edges_grp)

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

        self._props_mode_grp = mode_grp
        self._props_dur_row_widget = None  # updated below
        self._props_edges_grp = edges_grp

        self._props_mode_grp.setVisible(False)
        self._props_apply.setVisible(False)
        self._props_edges_grp.setVisible(False)

        return grp

    def _build_end_behavior_bar(self: "MonitorDisplaySubTabHostProtocol") -> QGroupBox:
        grp = QGroupBox("End of Graph Behavior")
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


__all__ = ["_UIPropsEndMixin"]
