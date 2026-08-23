"""Node-properties panel selection/apply/edges-list behavior.

Extracted from ``monitor_display_subtab.py`` -- pure code motion, no logic
change (see ``_ui_graph_canvas.py``'s docstring).
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, cast

from PySide6.QtCore import QPoint, Qt, QTimer, Slot
from PySide6.QtWidgets import QInputDialog, QListWidgetItem, QMenu, QWidget

from ..graph import NodeItem, is_video
from ..graph.data_schema import NodeData

if TYPE_CHECKING:
    from ...protos.monitor_display_subtab import MonitorDisplaySubTabHostProtocol


class _PropsBehaviorMixin:
    """Selection sync, Apply button, and the outgoing-edges list."""

    @Slot()
    def _on_selection_changed(self: "MonitorDisplaySubTabHostProtocol"):
        def do_selection_update():
            try:
                if not self._scene:
                    return
                items = self._scene.selectedItems()
                for item in items:
                    if isinstance(item, NodeItem):
                        # pyrefly: ignore [bad-argument-type]
                        self._show_node_in_props(item.node_data)
                        return
                # Nothing or only edge selected → hide props details
                self._props_hint.setVisible(True)
                self._props_file.setVisible(False)
                self._props_mode_grp.setVisible(False)
                self._props_apply.setVisible(False)
                self._props_edges_grp.setVisible(False)
                self._props_node_id = None
            except RuntimeError:
                pass
        QTimer.singleShot(0, do_selection_update)

    def _show_node_in_props(self: "MonitorDisplaySubTabHostProtocol", nd: NodeData):
        self._props_node_id = nd.node_id
        self._props_hint.setVisible(False)
        fname = os.path.basename(nd.file_path)
        self._props_file.setText(f"<b>{fname}</b><br><small style='color:#888'>{nd.file_path}</small>")
        self._props_file.setVisible(True)
        self._props_mode_grp.setVisible(True)
        self._props_apply.setVisible(True)
        self._props_dur.setVisible(True)
        self._props_edges_grp.setVisible(True)

        is_vid = is_video(nd.file_path)
        self._props_radio_runtime.setEnabled(is_vid)
        if nd.display_mode == "video_runtime" and is_vid:
            self._props_radio_runtime.setChecked(True)
        else:
            self._props_radio_fixed.setChecked(True)
        self._props_dur.setValue(nd.duration_sec)
        self._props_dur.setEnabled(nd.display_mode != "video_runtime")

        self._populate_props_edges_list(nd.node_id)

    def _apply_props(self: "MonitorDisplaySubTabHostProtocol"):
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

    # ---- Outgoing edges (props panel) --------------------------------------

    def _populate_props_edges_list(self: "MonitorDisplaySubTabHostProtocol", node_id: str):
        graph = self._current_graph()

        self._props_edges_list.blockSignals(True)
        self._props_edges_list.clear()
        if graph:
            src_edges = sorted(
                (e for e in graph.edges if e.source_id == node_id),
                key=lambda e: e.edge_id,
            )
            for e in src_edges:
                target_nd = graph.nodes.get(e.target_id)
                fname = os.path.basename(target_nd.file_path) if target_nd else "?"
                repeat_suffix = f"  ×{e.repeat_count}" if e.repeat_count > 1 else ""
                if e.target_id == node_id:
                    label = f"#{e.edge_id}  →  (self) {fname}{repeat_suffix}"
                else:
                    label = f"#{e.edge_id}  →  {fname}{repeat_suffix}"
                item = QListWidgetItem(label)
                item.setData(Qt.ItemDataRole.UserRole, e.edge_id)
                self._props_edges_list.addItem(item)
        self._props_edges_list.blockSignals(False)

        self._props_edge_target_combo.blockSignals(True)
        self._props_edge_target_combo.clear()
        if graph:
            for nid, lbl in self._scene.node_labels():
                display = f"(self) {lbl}" if nid == node_id else lbl
                self._props_edge_target_combo.addItem(display, nid)
        self._props_edge_target_combo.blockSignals(False)

    def _add_props_edge(self: "MonitorDisplaySubTabHostProtocol"):
        if self._props_node_id is None:
            return
        target_id = self._props_edge_target_combo.currentData()
        if not target_id:
            return
        repeat_count = self._props_edge_repeat_spin.value()
        self._scene.add_edge(self._props_node_id, target_id, repeat_count=repeat_count)
        self._props_edge_repeat_spin.setValue(1)
        # add_edge() already emits graph_changed, which refreshes this list,
        # but do it explicitly too in case a future refactor decouples them.
        self._populate_props_edges_list(self._props_node_id)

    def _props_edges_context_menu(self: "MonitorDisplaySubTabHostProtocol", pos: QPoint):
        item = self._props_edges_list.itemAt(pos)
        if not item or self._props_node_id is None:
            return
        edge_id = item.data(Qt.ItemDataRole.UserRole)
        graph = self._current_graph()
        current_repeat = 1
        if graph:
            for e in graph.edges:
                if e.source_id == self._props_node_id and e.edge_id == edge_id:
                    current_repeat = e.repeat_count
                    break
        menu = QMenu(cast(QWidget, self))
        act_repeat = menu.addAction(f"Set Repeat Count… (currently ×{current_repeat})")
        act_del = menu.addAction(f"🗑 Remove Edge #{edge_id}")
        chosen = menu.exec(self._props_edges_list.mapToGlobal(pos))
        if chosen == act_del:
            self._scene.remove_edge(self._props_node_id, edge_id)
            self._populate_props_edges_list(self._props_node_id)
        elif chosen == act_repeat:
            value, ok = QInputDialog.getInt(
                cast(QWidget, self), "Set Repeat Count",
                "Number of times the target wallpaper repeats\n"
                "back-to-back when this edge is taken:",
                current_repeat, 1, 999,
            )
            if ok:
                self._scene.set_edge_repeat_count(self._props_node_id, edge_id, value)
                self._populate_props_edges_list(self._props_node_id)

    def _on_props_edges_reordered(self: "MonitorDisplaySubTabHostProtocol", *args):
        if self._props_node_id is None:
            return
        ordered_edge_ids = [
            self._props_edges_list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self._props_edges_list.count())
        ]
        self._scene.reorder_source_edges(self._props_node_id, ordered_edge_ids)
        # Re-populate so the "#N" labels reflect the new edge_id order.
        self._populate_props_edges_list(self._props_node_id)


__all__ = ["_PropsBehaviorMixin"]
