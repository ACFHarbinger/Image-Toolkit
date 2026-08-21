"""Adding images to the per-monitor graph, and drag-drop onto monitors.

Extracted from ``wallpaper_common_base.py`` -- pure code motion, no logic
change (see ``_monitor_selection.py``'s docstring).
"""

from __future__ import annotations

import uuid

from backend.src.constants import SUPPORTED_VIDEO_FORMATS

from ...graph.data_schema import GraphData, NodeData

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ....protos.wallpaper_common_base import WallpaperCommonBaseHostProtocol


class _GraphDropMixin:
    """Add a wallpaper to the graph canvas, and handle files dropped on a monitor."""

    def add_image_to_graph(self: "WallpaperCommonBaseHostProtocol", monitor_id: str, path: str):
        monitor_subtab = None
        if hasattr(self, "_graphs"):
            monitor_subtab = self
        elif hasattr(self, "_monitor_display_ref"):
            monitor_subtab = self._monitor_display_ref

        if monitor_subtab:
            if monitor_id not in monitor_subtab._graphs:
                monitor_subtab._graphs[monitor_id] = GraphData()
            graph = monitor_subtab._graphs[monitor_id]

            if monitor_subtab._current_monitor_id == monitor_id:
                center = monitor_subtab._view.mapToScene(monitor_subtab._view.viewport().rect().center())
                monitor_subtab._scene.add_node(path, center)
            else:
                nid = str(uuid.uuid4())
                is_video = path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS))
                display_mode = "video_runtime" if is_video else "fixed"
                nd = NodeData(node_id=nid, file_path=path,
                              display_mode=display_mode, duration_sec=30.0,
                              pos_x=0.0, pos_y=0.0)
                graph.nodes[nid] = nd
                if graph.basis_node_id is None:
                     graph.basis_node_id = nid

    def on_images_dropped(self: "WallpaperCommonBaseHostProtocol", monitor_id: str, image_paths: list):
        if not image_paths:
            return

        for image_path in image_paths:
            self._process_single_drop(monitor_id, image_path)

        if image_paths:
            first_path = image_paths[0]
            self.monitor_image_paths[monitor_id] = first_path

            queue = self.monitor_slideshow_queues.get(monitor_id, [])
            batch_start = len(queue) - len(image_paths)
            self.monitor_current_index[monitor_id] = max(batch_start, 0)

            self.update_monitor_widget_ui(monitor_id)

        if hasattr(self, "toggle_daemon") and self._is_daemon_running_config():
            self.toggle_daemon(True)
        else:
            for peer in getattr(self, "linked_tabs", []):
                if hasattr(peer, "toggle_daemon") and peer._is_daemon_running_config():
                    peer.toggle_daemon(True)

        self.deselect_all_items()

    def _process_single_drop(self: "WallpaperCommonBaseHostProtocol", monitor_id: str, image_path: str):
        is_video = image_path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS))
        target = self if hasattr(self, "background_type_combo") else None
        if not target:
            for peer in getattr(self, "linked_tabs", []):
                if hasattr(peer, "background_type_combo"):
                    target = peer
                    break
        if target:
            combo = target.background_type_combo
            if combo is not None:
                bg_type = combo.currentText()
                if is_video and bg_type == "Image":
                    combo.setCurrentText("Smart Video")
                elif not is_video and bg_type in ["Smart Video", "Smart Video Slideshow"]:
                    combo.setCurrentText("Image")
                if bg_type == "Solid Color":
                    combo.setCurrentText("Image")

        if monitor_id not in self.monitor_slideshow_queues:
            self.monitor_slideshow_queues[monitor_id] = []
        self.monitor_slideshow_queues[monitor_id].append(image_path)

        self.monitor_image_paths[monitor_id] = image_path

        queue = self.monitor_slideshow_queues[monitor_id]
        self.monitor_current_index[monitor_id] = len(queue) - 1

        self.update_monitor_widget_ui(monitor_id)
        self.check_all_monitors_set()


__all__ = ["_GraphDropMixin"]
