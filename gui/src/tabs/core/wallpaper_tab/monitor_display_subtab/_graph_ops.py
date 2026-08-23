"""Graph node/edge CRUD operations + thumbnail actions for ``MonitorDisplaySubTab``.

Extracted from ``monitor_display_subtab.py`` -- pure code motion, no logic
change (see ``_ui_graph_canvas.py``'s docstring).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, cast

from backend.src.constants import SUPPORTED_IMG_FORMATS, SUPPORTED_VIDEO_FORMATS
from PySide6.QtCore import QPoint, QPointF, Qt, Slot
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QDialog, QFileDialog, QMenu, QMessageBox, QWidget

from ..graph import NODE_W, NodeEditDialog, NodeItem
from ..graph.data_schema import GraphData

if TYPE_CHECKING:
    from ...protos.monitor_display_subtab import MonitorDisplaySubTabHostProtocol


class _GraphOpsMixin:
    """Node/edge add/delete/select operations and gallery-thumbnail actions."""

    def _current_graph(self: "MonitorDisplaySubTabHostProtocol") -> Optional[GraphData]:
        if self._current_monitor_id is None:
            return None
        return self._graphs.get(self._current_monitor_id)

    def _add_node(self: "MonitorDisplaySubTabHostProtocol"):
        if self._current_monitor_id is None:
            return
        all_exts = list(SUPPORTED_VIDEO_FORMATS) + [
            f".{e.lower().lstrip('.')}" for e in SUPPORTED_IMG_FORMATS
        ]
        ext_str = " ".join(f"*{e}" for e in all_exts)
        paths, _ = QFileDialog.getOpenFileNames(
            cast(QWidget, self), "Select Wallpaper File(s)", "",
            f"Media Files ({ext_str});;All Files (*)",
        )
        if not paths:
            return
        center = self._view.mapToScene(self._view.viewport().rect().center())
        spacing = NODE_W + 20
        for i, path in enumerate(paths):
            pos = QPointF(center.x() + i * spacing - len(paths) * spacing / 2, center.y())
            self._scene.add_node(path, pos)

    def _selected_node_id(self: "MonitorDisplaySubTabHostProtocol") -> Optional[str]:
        for item in self._scene.selectedItems():
            if isinstance(item, NodeItem):
                return item.node_data.node_id
        return None

    def _add_self_edge(self: "MonitorDisplaySubTabHostProtocol"):
        nid = self._selected_node_id()
        if nid is None:
            QMessageBox.information(cast(QWidget, self), "No Node Selected",
                                    "Select a node first, then click 'Self-Edge'.")
            return
        self._scene.add_edge(nid, nid)

    def _add_edge(self: "MonitorDisplaySubTabHostProtocol"):
        src_id = self._selected_node_id()
        if src_id is None:
            QMessageBox.information(cast(QWidget, self), "No Node Selected",
                                    "Select the SOURCE node first, then click 'Connect'.")
            return
        self._scene.start_connection_mode(src_id)

    def _delete_selected(self: "MonitorDisplaySubTabHostProtocol"):
        self._scene.remove_selected()

    def _set_start_node(self: "MonitorDisplaySubTabHostProtocol"):
        nid = self._selected_node_id()
        if nid is None:
            QMessageBox.information(cast(QWidget, self), "No Node Selected",
                                    "Select a node first, then click '★ Set Start'.")
            return
        self._scene.set_basis_node(nid)

    def _clear_canvas(self: "MonitorDisplaySubTabHostProtocol"):
        if self._current_monitor_id is None:
            return
        self.clear_monitor_graph(self._current_monitor_id)

    def _fit_view(self: "MonitorDisplaySubTabHostProtocol"):
        rect = self._scene.itemsBoundingRect()
        if rect.isEmpty():
            self._view.resetTransform()
        else:
            self._view.fitInView(rect.adjusted(-20, -20, 20, 20),
                                 Qt.AspectRatioMode.KeepAspectRatio)

    @Slot(str)
    def _edit_node(self: "MonitorDisplaySubTabHostProtocol", node_id: str):
        graph = self._current_graph()
        if graph is None:
            return
        nd = graph.nodes.get(node_id)
        if nd is None:
            return
        # pyrefly: ignore [bad-argument-type]
        dlg = NodeEditDialog(nd, parent=cast(QWidget, self))
        if dlg.exec() == QDialog.DialogCode.Accepted:
            # Update the visual
            item = self._scene._node_items.get(node_id)
            if item:
                item.refresh_thumbnail()
                item.update()
            self._on_graph_changed()

    @Slot()
    def _on_graph_changed(self: "MonitorDisplaySubTabHostProtocol"):
        self._scene._refresh_node_styles()
        self._update_seq_label()
        self._update_end_jump_combo()
        graph = self._current_graph()
        if graph:
            # Persist end-behavior selections back to graph
            self._read_end_behavior_to_graph(graph)
        # Keep the outgoing-edges list in sync no matter how the graph
        # changed (canvas edit, self-edge button, node deletion, etc.),
        # not just edits made through the props panel itself.
        if self._props_node_id is not None:
            self._populate_props_edges_list(self._props_node_id)

    # ---- Thumbnail Actions ------------------------------------------------

    @Slot(str)
    def handle_thumbnail_double_click(self: "MonitorDisplaySubTabHostProtocol", image_path: str):
        if self._current_monitor_id is None:
            return
        center = self._view.mapToScene(self._view.viewport().rect().center())
        self._scene.add_node(image_path, center)

    @Slot(QPoint, str)
    def show_image_context_menu(self: "MonitorDisplaySubTabHostProtocol", global_pos: QPoint, path: str):
        menu = QMenu(cast(QWidget, self))

        is_video = path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS))
        view_text = "Play Video" if is_video else "View Full Size Preview"
        view_action = QAction(view_text, cast(QWidget, self))
        if self._system_display_ref and hasattr(self._system_display_ref, "handle_full_image_preview"):
            view_action.triggered.connect(lambda: self._system_display_ref.handle_full_image_preview(path))
        else:
            view_action.setEnabled(False)
        menu.addAction(view_action)

        add_action = QAction("➕ Add to Graph Canvas", cast(QWidget, self))
        add_action.triggered.connect(lambda: self.handle_thumbnail_double_click(path))
        menu.addAction(add_action)

        menu.addSeparator()
        delete_action = QAction("🗑️ Delete File (Permanent)", cast(QWidget, self))
        if self._system_display_ref and hasattr(self._system_display_ref, "handle_delete_image"):
            delete_action.triggered.connect(lambda: self._system_display_ref.handle_delete_image(path))
        else:
            delete_action.setEnabled(False)
        menu.addAction(delete_action)

        menu.exec(global_pos)


__all__ = ["_GraphOpsMixin"]
