"""Setting a specific queue entry active, swapping monitors/graphs, queue reorder.

Extracted from ``wallpaper_common_base.py`` -- pure code motion, no logic
change (see ``_monitor_selection.py``'s docstring).
"""

from __future__ import annotations

import os
import platform
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional, cast

from backend.src.core import WallpaperManager
from PySide6.QtCore import Slot
from PySide6.QtWidgets import QMessageBox, QWidget
from shiboken6 import Shiboken as sip

from ......windows import SlideshowQueueWindow
from ...graph.data_schema import GraphData

if TYPE_CHECKING:
    from ....protos.wallpaper_common_base import WallpaperCommonBaseHostProtocol


class _WallpaperSwapMixin:
    """Set-active-from-queue, monitor/graph swap, item swap, and queue reorder/clear."""

    def _set_specific_wallpaper(self: "WallpaperCommonBaseHostProtocol", monitor_id: str, path: str, index: Optional[int] = None):
        if not os.path.exists(path):
            QMessageBox.warning(cast(QWidget, self), "Error", f"File not found:\n{path}")
            return

        self.monitor_image_paths[monitor_id] = path

        queue = self.monitor_slideshow_queues.get(monitor_id, [])
        if index is not None and 0 <= index < len(queue) and queue[index] == path:
            self.monitor_current_index[monitor_id] = index
        elif path in queue:
            self.monitor_current_index[monitor_id] = queue.index(path)

        self.update_monitor_widget_ui(monitor_id)
        self.check_all_monitors_set()

        if hasattr(self, "run_wallpaper_worker"):
            self.run_wallpaper_worker()
        else:
            for peer in getattr(self, "linked_tabs", []):
                if hasattr(peer, "run_wallpaper_worker"):
                    peer.run_wallpaper_worker()

    def on_image_dropped(self: "WallpaperCommonBaseHostProtocol", monitor_id: str, image_path: str):
        self.on_images_dropped(monitor_id, [image_path])

    def swap_monitors(self: "WallpaperCommonBaseHostProtocol", m0: str, m1: str = ""):
        monitor_ids = list(self.monitor_widgets.keys())
        if len(monitor_ids) < 2:
            return

        if not m1:
            if len(monitor_ids) == 2:
                m1 = next(mid for mid in monitor_ids if mid != m0)
            else:
                return

        if m0 not in self.monitor_widgets or m1 not in self.monitor_widgets:
            return

        self.monitor_image_paths[m0], self.monitor_image_paths[m1] = (
            self.monitor_image_paths.get(m1),
            self.monitor_image_paths.get(m0),
        )
        self.monitor_slideshow_queues[m0], self.monitor_slideshow_queues[m1] = (
            self.monitor_slideshow_queues.get(m1, []).copy(),
            self.monitor_slideshow_queues.get(m0, []).copy(),
        )
        self.monitor_current_index[m0], self.monitor_current_index[m1] = (
            self.monitor_current_index.get(m1, -1),
            self.monitor_current_index.get(m0, -1),
        )

        for mid in [m0, m1]:
            self.update_monitor_widget_ui(mid)

        self.check_all_monitors_set()

        if hasattr(self, "toggle_daemon") and self._is_daemon_running_config():
            self.toggle_daemon(True)
        else:
            for peer in getattr(self, "linked_tabs", []):
                if hasattr(peer, "toggle_daemon") and peer._is_daemon_running_config():
                    peer.toggle_daemon(True)

    def swap_graphs(self: "WallpaperCommonBaseHostProtocol", m0: str, m1: str = ""):
        monitor_ids = list(self.monitor_widgets.keys())
        if len(monitor_ids) < 2:
            return
        if not m1:
            if len(monitor_ids) == 2:
                m1 = next(mid for mid in monitor_ids if mid != m0)
            else:
                return

        if hasattr(self, "_monitor_display_ref") and self._monitor_display_ref:
            self._monitor_display_ref.swap_graphs(m0, m1)
        elif hasattr(self, "_graphs") and (m0 in self._graphs or m1 in self._graphs):
            self._graphs[m0], self._graphs[m1] = (
                self._graphs.get(m1, GraphData()),
                self._graphs.get(m0, GraphData()),
            )
            if self._current_monitor_id in [m0, m1]:
                self._on_monitor_selected(self._current_monitor_id)

    def handle_item_swap_request(self: "WallpaperCommonBaseHostProtocol", s_mid: str, s_idx: int, t_mid: str, t_idx: int):
        src_queue = self.monitor_slideshow_queues.get(s_mid, [])
        target_queue = self.monitor_slideshow_queues.get(t_mid, [])

        if s_idx < len(src_queue) and t_idx < len(target_queue):
            src_queue[s_idx], target_queue[t_idx] = (
                target_queue[t_idx],
                src_queue[s_idx],
            )

            if s_idx == 0:
                self.on_queue_reordered(s_mid, src_queue)
            if t_mid != s_mid and t_idx == 0:
                self.on_queue_reordered(t_mid, target_queue)

            for win in self.open_queue_windows:
                if sip.isValid(win) and isinstance(win, SlideshowQueueWindow):
                    if win.monitor_id == s_mid:
                        win.populate_list(src_queue)
                    elif win.monitor_id == t_mid:
                        win.populate_list(target_queue)

            self.check_all_monitors_set()

            if hasattr(self, "toggle_daemon") and self._is_daemon_running_config():
                self.toggle_daemon(True)
            else:
                for peer in getattr(self, "linked_tabs", []):
                    if hasattr(peer, "toggle_daemon") and peer._is_daemon_running_config():
                        peer.toggle_daemon(True)

    @Slot(str, list)
    def on_queue_reordered(self: "WallpaperCommonBaseHostProtocol", monitor_id: str, new_queue: List[str]):
        self.monitor_slideshow_queues[monitor_id] = new_queue
        self.monitor_current_index[monitor_id] = -1
        new_first_image = new_queue[0] if new_queue else None
        self.monitor_image_paths[monitor_id] = new_first_image

        self.update_monitor_widget_ui(monitor_id)
        self.check_all_monitors_set()

    @Slot(str)
    def handle_clear_monitor_queue(self: "WallpaperCommonBaseHostProtocol", monitor_id: str):
        if monitor_id not in self.monitor_widgets:
            return
        monitor_name = self.monitor_widgets[monitor_id].monitor.name
        if monitor_id in self.monitor_slideshow_queues:
            self.monitor_slideshow_queues[monitor_id].clear()
        if monitor_id in self.monitor_image_paths:
            self.monitor_image_paths[monitor_id] = None
        if monitor_id in self.monitor_current_index:
            self.monitor_current_index[monitor_id] = -1

        system = platform.system()
        num_monitors_detected = len(self.monitors)
        current_system_wallpaper_paths = {}
        if system == "Linux" and num_monitors_detected > 0:
            try:
                if self.qdbus:
                    raw_paths = WallpaperManager.get_current_system_wallpaper_path_kde(
                        self.monitors, self.qdbus
                    )
                    current_system_wallpaper_paths = self._get_rotated_map_for_ui(
                        raw_paths
                    )
            except Exception as e:
                print(f"KDE retrieval failed unexpectedly: {e}")

        system_wallpaper_path = current_system_wallpaper_paths.get(monitor_id)
        if system_wallpaper_path and Path(system_wallpaper_path).exists():
            self.monitor_image_paths[monitor_id] = system_wallpaper_path

        self.update_monitor_widget_ui(monitor_id)
        self.check_all_monitors_set()

        QMessageBox.information(
            cast(QWidget, self),
            "Monitor Cleared",
            f"All pending items and the slideshow queue for **{monitor_name}** have been cleared.\n\nThe system's current background remains unchanged.",
        )


__all__ = ["_WallpaperSwapMixin"]
