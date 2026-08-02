"""QML-facing slots for ``WallpaperCommonBase``.

Extracted from ``wallpaper_common_base.py`` -- pure code motion, no logic
change (see ``_monitor_selection.py``'s docstring).
"""

from __future__ import annotations

from PySide6.QtCore import Slot


class _QmlHandlersMixin:
    """Bridge slots consumed by the QML wallpaper UI."""

    @Slot()
    def request_monitors_qml(self):
        monitor_data = []
        for m in self.monitors:
            monitor_data.append(
                {
                    "name": m.name,
                    "x": m.x,
                    "y": m.y,
                    "width": m.width,
                    "height": m.height,
                    "is_primary": m.is_primary,
                }
            )
        self.qml_monitors_changed.emit(monitor_data)

    @Slot(str, str)
    def set_wallpaper_qml(self, path, monitor_name="All"):
        if monitor_name == "All":
            for mid in self.monitor_widgets.keys():
                self.monitor_image_paths[mid] = path
        else:
            if monitor_name in self.monitor_widgets:
                self.monitor_image_paths[monitor_name] = path
        if hasattr(self, "handle_set_wallpaper_click"):
            self.handle_set_wallpaper_click()

    @Slot(int, int, str, bool, bool)
    def update_slideshow_settings_qml(
        self, interval_min, style, random_order, include_subdirs
    ):
        if hasattr(self, "interval_min_spinbox") and self.interval_min_spinbox is not None:
            self.interval_min_spinbox.setValue(interval_min)
        if hasattr(self, "style_combo") and self.style_combo is not None:
            self.style_combo.setCurrentText(style)
        self.request_monitors_qml()

    @Slot(str)
    def drop_image_qml(self, path):
        self.set_wallpaper_qml(path, "All")


__all__ = ["_QmlHandlersMixin"]
