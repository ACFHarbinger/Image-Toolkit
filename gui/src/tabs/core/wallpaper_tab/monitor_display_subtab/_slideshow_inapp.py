"""In-app slideshow control (native scheduler, no background daemon).

Extracted from ``monitor_display_subtab.py`` -- pure code motion, no logic
change (see ``_ui_graph_canvas.py``'s docstring).

Delegated to base.run_monitor_slideshow (base/src/utils/monitor_slideshow.cpp)
via monitor_slideshow_daemon.start()/stop()/status(). That native
scheduler runs its own std::thread inside this GUI process and calls
WallpaperManager.apply_wallpaper back on each tick -- independent of
the Qt event loop and GIL, so it keeps advancing reliably even if
something on the Python/Qt side stalls.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, List, Optional, cast

from backend.src.utils.display import monitor_slideshow_daemon as _monitor_slideshow
from PySide6.QtCore import Slot
from PySide6.QtWidgets import QMessageBox, QWidget

if TYPE_CHECKING:
    from ...protos.monitor_display_subtab import MonitorDisplaySubTabHostProtocol


class _SlideshowInAppMixin:
    """Start/stop the in-app (foreground-process) wallpaper slideshow."""

    _inapp_active_monitor_id: Optional[str]
    _daemon_active_monitor_id: Optional[str]

    @Slot()
    def _toggle_inapp_slideshow(self: "MonitorDisplaySubTabHostProtocol"):
        monitor_id = self._current_monitor_id
        if monitor_id is None:
            return
        if self._inapp_active_monitor_id == monitor_id:
            self._stop_inapp_slideshow()
        else:
            self._start_inapp_slideshow(monitor_id)

    def _start_inapp_slideshow(self: "MonitorDisplaySubTabHostProtocol", monitor_id: str):
        queue = self.monitor_slideshow_queues.get(monitor_id, [])
        if not queue:
            QMessageBox.information(
                cast(QWidget, self), "Empty Queue",
                "This display's Wallpaper Queue is empty. Use 'Export to Queue' "
                "or drop files onto the monitor first.",
            )
            self._update_slideshow_buttons()
            return
        if self._daemon_active_monitor_id == monitor_id:
            QMessageBox.warning(
                cast(QWidget, self), "Slideshow Conflict",
                "The Slideshow Daemon is running for this display. "
                "Stop it before starting the in-app slideshow.",
            )
            self._update_slideshow_buttons()
            return
        if self._inapp_active_monitor_id and self._inapp_active_monitor_id != monitor_id:
            reply = QMessageBox.question(
                cast(QWidget, self), "Slideshow Already Running",
                "The in-app slideshow is already running for another display "
                f"(Monitor {self._inapp_active_monitor_id}). Only one display "
                "can run it at a time. Switch it to this display?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                self._update_slideshow_buttons()
                return
            self._stop_inapp_slideshow()

        durations = self._reconcile_queue_durations(monitor_id)

        style = "Fill"
        video_style = "Scaled and Cropped"
        if getattr(self, "_system_display_ref", None):
            style = getattr(self._system_display_ref, "wallpaper_style", style)
            video_style = getattr(self._system_display_ref, "video_style", video_style)

        other_paths = {
            mid: p for mid, p in self.monitor_image_paths.items()
            if mid != monitor_id and p
        }

        try:
            _monitor_slideshow.start(
                monitor_id,
                queue,
                cast(List[Optional[float]], durations),
                monitors=self.monitors,
                style=style,
                video_style=video_style,
                other_paths=other_paths,
            )
        except Exception as e:
            QMessageBox.critical(
                cast(QWidget, self), "Error", f"Failed to start in-app slideshow: {e}")
            self._update_slideshow_buttons()
            return

        self._inapp_active_monitor_id = monitor_id
        self._update_slideshow_buttons()
        self._update_queue_status_label()

    def _stop_inapp_slideshow(self: "MonitorDisplaySubTabHostProtocol"):
        if self._inapp_active_monitor_id is None:
            return
        with contextlib.suppress(Exception):
            _monitor_slideshow.stop()
        self._inapp_active_monitor_id = None
        self._update_slideshow_buttons()
        self._update_queue_status_label()

    def _sync_inapp_state_from_native(self: "MonitorDisplaySubTabHostProtocol", monitor_id: str, status: dict):
        """The native scheduler applies wallpapers directly via
        WallpaperManager (off the Qt thread), so it never touches this
        subtab's own bookkeeping. Reconcile monitor_image_paths / the
        current-index / the drop-widget thumbnail from the native status on
        each poll tick so the rest of the UI (queue window highlighting,
        "Set Active Wallpaper from Queue" checkmarks, etc.) stays in sync."""
        idx = status.get("current_index")
        if idx is None or idx < 0:
            return
        queue = self.monitor_slideshow_queues.get(monitor_id, [])
        if not (0 <= idx < len(queue)):
            return
        path = queue[idx]
        if self.monitor_image_paths.get(monitor_id) == path:
            return
        self.monitor_image_paths[monitor_id] = path
        self.monitor_current_index[monitor_id] = idx
        self.update_monitor_widget_ui(monitor_id)
        self.check_all_monitors_set()


__all__ = ["_SlideshowInAppMixin"]
