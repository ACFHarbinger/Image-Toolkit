"""Detecting system monitors and (re)populating the monitor-drop-widget layout.

Extracted from ``wallpaper_common_base.py`` -- pure code motion, no logic
change (see ``_monitor_selection.py``'s docstring).
"""

from __future__ import annotations

import platform
from pathlib import Path
from typing import Any, Dict, Optional, cast

from backend.src.core import WallpaperManager
from PySide6.QtWidgets import QLabel, QMessageBox
from screeninfo import get_monitors

from .....components import MonitorDropView


class _MonitorLayoutMixin:
    """Detect system monitors and rebuild the monitor-drop-widget layout."""

    def populate_monitor_layout(self):  # noqa: C901
        self.monitor_layout_container.clear_widgets()
        self.monitor_widgets.clear()
        system_monitors = []
        try:
            system_monitors = get_monitors()
            system_monitors = sorted(system_monitors, key=lambda m: m.x)
            self.monitors = system_monitors
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not get monitor info: {e}")
            self.monitors = []

        if not self.monitors or not self.monitors[0].name or "Mock" in self.monitors[0].name:
            cast(Any, self.monitor_layout_container).addWidget(
                QLabel("Could not detect any monitors.\nIs 'screeninfo' installed?")
            )
            self.monitors_updated.emit(self.monitors)
            return

        current_system_wallpaper_paths = {}
        system = platform.system()
        num_monitors_detected = len(self.monitors)
        if system == "Linux" and num_monitors_detected > 0:
            try:
                if self.qdbus:
                    current_system_wallpaper_paths = (
                        WallpaperManager.get_current_system_wallpaper_path_kde(
                            self.monitors, self.qdbus
                        )
                    )
            except Exception as e:
                print(f"KDE retrieval failed unexpectedly: {e}")

        monitor_info_list = []
        for i, m in enumerate(self.monitors):
            m_id = str(i)
            m_name = m.name if m.name else f"Display {m_id}"
            monitor_info_list.append((m_id, m_name))

        monitor_id_to_widget = {}
        for i, monitor in enumerate(self.monitors):
            monitor_id = str(i)
            drop_widget = MonitorDropView(monitor, monitor_id)

            real_name = drop_widget.get_real_monitor_name()
            if real_name:
                drop_widget.set_hardware_name(real_name)

            drop_widget.other_monitors = [
                (mid, name) for mid, name in monitor_info_list if mid != monitor_id
            ]

            drop_widget.images_dropped.connect(self.on_images_dropped)
            drop_widget.clicked.connect(self._select_monitor)
            drop_widget.double_clicked.connect(
                lambda m_id=monitor_id: self.handle_monitor_double_click(m_id)
            )
            drop_widget.clear_requested_id.connect(self.handle_clear_monitor_queue)
            drop_widget.swap_requested_id.connect(self.swap_monitors)
            drop_widget.swap_graph_requested_id.connect(self.swap_graphs)
            drop_widget.context_menu_requested.connect(self.on_monitor_context_menu)
            self.monitor_widgets[monitor_id] = drop_widget

            current_image = self.monitor_image_paths.get(monitor_id)
            image_path_to_display = current_image

            if not image_path_to_display:
                system_wallpaper_path = current_system_wallpaper_paths.get(monitor_id)
                if system_wallpaper_path and Path(system_wallpaper_path).exists():
                    image_path_to_display = system_wallpaper_path

            if image_path_to_display:
                if not self.monitor_image_paths.get(monitor_id):
                    self.monitor_image_paths[monitor_id] = image_path_to_display
                thumb = self._get_or_generate_thumbnail(image_path_to_display)
                drop_widget.set_image(image_path_to_display, thumb)
            else:
                drop_widget.clear()

            monitor_id_to_widget[monitor_id] = drop_widget
            self.monitor_widgets[monitor_id] = drop_widget

        for monitor in self.monitors:
            system_index = -1
            for i, sys_mon in enumerate(system_monitors):
                if (
                    sys_mon.x == monitor.x
                    and sys_mon.y == monitor.y
                    and sys_mon.width == monitor.width
                    and sys_mon.height == monitor.height
                ):
                    system_index = i
                    break
            if system_index != -1:
                monitor_id = str(system_index)
                if monitor_id in monitor_id_to_widget:
                    self.monitor_layout_container.addWidget(monitor_id_to_widget[monitor_id])  # pyrefly: ignore [bad-argument-type]

        self.monitors_updated.emit(self.monitors)

    def _get_rotated_map_for_ui(self, raw_paths: Dict[str, str | None]) -> Dict[str, str | None]:
        mapped = {}
        for idx, path in raw_paths.items():
            mapped[idx] = path
        return mapped

    def _get_current_system_image_paths_for_all(self) -> Dict[str, Optional[str]]:
        system = platform.system()
        num_monitors = len(self.monitors)
        current_paths: Dict[str, Optional[str]] = {}
        if num_monitors == 0:
            return current_paths
        if system == "Linux":
            try:
                if self.qdbus:
                    raw_paths = WallpaperManager.get_current_system_wallpaper_path_kde(
                        self.monitors, self.qdbus
                    )
                    current_paths = self._get_rotated_map_for_ui(raw_paths)
            except Exception:
                pass
        return current_paths


__all__ = ["_MonitorLayoutMixin"]
