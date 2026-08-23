"""Monitor double-click (queue window) and right-click context menu handling.

Extracted from ``wallpaper_common_base.py`` -- pure code motion, no logic
change (see ``_monitor_selection.py``'s docstring).
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, cast

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import QMenu, QMessageBox, QWidget
from shiboken6 import Shiboken as sip

from ......windows import SlideshowQueueWindow
from ...graph.data_schema import GraphData

if TYPE_CHECKING:
    from ....protos.wallpaper_common_base import WallpaperCommonBaseHostProtocol


class _MonitorContextMixin:
    """Double-click Wallpaper Queue window; right-click monitor context menu."""

    def handle_monitor_double_click(self: "WallpaperCommonBaseHostProtocol", monitor_id: str):
        bg_type = getattr(self, "background_type", "Image")
        if bg_type == "Solid Color":
            return
        queue = self.monitor_slideshow_queues.get(monitor_id, [])
        monitor_name = self.monitor_widgets[monitor_id].monitor.name
        for win in list(self.open_queue_windows):
            try:
                if (
                    isinstance(win, SlideshowQueueWindow)
                    and win.monitor_id == monitor_id
                ):
                    win.activateWindow()
                    return
            except RuntimeError:
                if win in self.open_queue_windows:
                    self.open_queue_windows.remove(win)

        other_names = {
            mid: widget.monitor.name for mid, widget in self.monitor_widgets.items()
        }
        assert monitor_name is not None
        window = SlideshowQueueWindow(
            monitor_name,
            monitor_id,
            queue,
            pixmap_cache=self._initial_pixmap_cache,
            other_queues=self.monitor_slideshow_queues,
            other_names=other_names,
        )
        window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        window.queue_reordered.connect(self.on_queue_reordered)
        window.image_preview_requested.connect(self.handle_full_image_preview)
        window.item_swap_requested.connect(self.handle_item_swap_request)

        self.open_queue_windows = [
            w for w in self.open_queue_windows if not sip.isValid(w)
        ]

        def remove_closed_win(event: Any):
            self.open_queue_windows = [
                w for w in self.open_queue_windows if w != window and sip.isValid(w)
            ]
            event.accept()

        window.closeEvent = remove_closed_win  # type: ignore[method-assign]
        window.show()
        self.open_queue_windows.append(window)

    @Slot(str, QMenu)
    def on_monitor_context_menu(self: "WallpaperCommonBaseHostProtocol", monitor_id: str, menu: QMenu):
        if self._current_monitor_id == monitor_id:
            unselect_action = menu.addAction("Unselect Display")
            unselect_action.triggered.connect(lambda: self._select_monitor(monitor_id))
            menu.addSeparator()

        view_queue_action = menu.addAction("View Wallpaper Queue")
        view_queue_action.triggered.connect(lambda: self.handle_monitor_double_click(monitor_id))
        menu.addSeparator()

        queue = self.monitor_slideshow_queues.get(monitor_id, [])
        if queue:
            set_active_menu = menu.addMenu("Set Active Wallpaper from Queue...")

            current_active = self.monitor_image_paths.get(monitor_id)
            for i, path in enumerate(queue):
                filename = os.path.basename(path)
                action = set_active_menu.addAction(f"[{i}] {filename}")
                action.setCheckable(True)
                if path == current_active:
                    action.setChecked(True)
                action.triggered.connect(
                    lambda _, p=path, idx=i: self._set_specific_wallpaper(monitor_id, p, idx)
                )

            other_monitors = [
                (mid, widget)
                for mid, widget in self.monitor_widgets.items()
                if mid != monitor_id
            ]
            if other_monitors:
                menu.addSeparator()
                swap_menu = menu.addMenu("🔀 Swap Active Image with Monitor...")
                for t_mid, t_widget in other_monitors:
                    t_name = t_widget.monitor.name
                    t_active_path = self.monitor_image_paths.get(t_mid)
                    if t_active_path:
                        t_label = f"{t_name}  ←→  {os.path.basename(t_active_path)}"
                    else:
                        t_label = f"{t_name}  (empty)"
                    action = swap_menu.addAction(t_label)
                    action.setEnabled(bool(t_active_path and current_active))
                    action.triggered.connect(
                        lambda _, s=monitor_id, t=t_mid: self.handle_item_swap_request(
                            s, 0, t, 0
                        )
                    )

        menu.addSeparator()
        clear_graph_action = menu.addAction("Clear Monitor Graph")
        clear_graph_action.triggered.connect(
            lambda _, m=monitor_id: self.clear_monitor_graph(m)
        )

    def clear_monitor_graph(self: "WallpaperCommonBaseHostProtocol", monitor_id: str):
        reply = QMessageBox.question(
            cast(QWidget, self), "Clear Graph",
            f"Are you sure you want to clear the graph for Monitor {monitor_id}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        if hasattr(self, "_monitor_display_ref") and self._monitor_display_ref:
            self._monitor_display_ref.clear_monitor_graph_direct(monitor_id)
        else:
            self.clear_monitor_graph_direct(monitor_id)

    def clear_monitor_graph_direct(self: "WallpaperCommonBaseHostProtocol", monitor_id: str):
        if hasattr(self, "_graphs"):
            self._graphs[monitor_id] = GraphData()
            if self._current_monitor_id == monitor_id and hasattr(self, "_scene"):
                self._scene.load_graph(self._graphs[monitor_id])
                if hasattr(self, "_on_graph_changed"):
                    self._on_graph_changed()


__all__ = ["_MonitorContextMixin"]
