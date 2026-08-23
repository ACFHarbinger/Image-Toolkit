"""End-of-graph-behavior selection logic for ``MonitorDisplaySubTab``.

Extracted from ``monitor_display_subtab.py`` -- pure code motion, no logic
change (see ``_ui_graph_canvas.py``'s docstring).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from PySide6.QtCore import Slot
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget

from ..graph.data_schema import GraphData

if TYPE_CHECKING:
    from ...protos.monitor_display_subtab import MonitorDisplaySubTabHostProtocol


class _EndBehaviorMixin:
    """Sync/read the "End of Graph Behavior" bar to/from the active graph."""

    _END_KEYS = [
        "repeat_graph",
        "solid_color",
        "stay_last",
        "return_first",
        "jump_to",
    ]

    def _sync_end_behavior_ui(self: "MonitorDisplaySubTabHostProtocol", graph: GraphData):
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
    def _on_end_behavior_changed(self: "MonitorDisplaySubTabHostProtocol", idx: int):
        is_color = idx == 1
        is_jump = idx == 4
        self._end_color_preview.setVisible(is_color)
        self._end_color_btn.setVisible(is_color)
        self._end_jump_combo.setVisible(is_jump)
        # Persist to graph
        graph = self._current_graph()
        if graph:
            self._read_end_behavior_to_graph(graph)

    def _read_end_behavior_to_graph(self: "MonitorDisplaySubTabHostProtocol", graph: GraphData):
        idx = self._end_combo.currentIndex()
        graph.end_behavior = self._END_KEYS[idx] if 0 <= idx < len(self._END_KEYS) else "repeat_graph"
        graph.end_color = self._end_color_current
        if graph.end_behavior == "jump_to":
            data = self._end_jump_combo.currentData()
            graph.end_jump_node_id = data if data else None

    def _pick_end_color(self: "MonitorDisplaySubTabHostProtocol"):
        initial = QColor(self._end_color_current)
        from PySide6.QtWidgets import QColorDialog
        col = QColorDialog.getColor(initial, cast(QWidget, self), "Pick End Color")
        if col.isValid():
            self._end_color_current = col.name().upper()
            self._refresh_end_color_preview()
            graph = self._current_graph()
            if graph:
                graph.end_color = self._end_color_current

    def _refresh_end_color_preview(self: "MonitorDisplaySubTabHostProtocol"):
        self._end_color_preview.setStyleSheet(
            f"background-color:{self._end_color_current}; border:1px solid #4f545c;"
        )

    def _update_end_jump_combo(self: "MonitorDisplaySubTabHostProtocol"):
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


__all__ = ["_EndBehaviorMixin"]
