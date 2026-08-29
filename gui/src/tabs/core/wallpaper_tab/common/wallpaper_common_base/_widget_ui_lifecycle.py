"""Monitor-widget UI refresh, close-event teardown, and daemon-config check.

Extracted from ``wallpaper_common_base.py`` -- pure code motion, no logic
change (see ``_monitor_selection.py``'s docstring).
"""

from __future__ import annotations

import contextlib
import json
import os
from typing import TYPE_CHECKING, Optional

from backend.src.constants import DAEMON_CONFIG_PATH
from PySide6.QtCore import QThread, QTimer
from PySide6.QtWidgets import QApplication
from shiboken6 import Shiboken as sip

from ......windows import SlideshowQueueWindow

if TYPE_CHECKING:
    from ....protos.wallpaper_common_base import WallpaperCommonBaseHostProtocol


class _WidgetUiLifecycleMixin:
    """Refresh monitor-drop widgets; tear down timers/threads/windows on close."""

    slideshow_timer: Optional[QTimer]
    countdown_timer: Optional[QTimer]
    img_scanner_thread: Optional[QThread]
    vid_scanner_thread: Optional[QThread]
    open_queue_windows: list
    open_image_preview_windows: list

    def update_monitor_widget_ui(self: "WallpaperCommonBaseHostProtocol", monitor_id: str):
        self._update_widget_ui_local(monitor_id)
        for peer in getattr(self, "linked_tabs", []):
            peer._update_widget_ui_local(monitor_id)

    def _update_widget_ui_local(self: "WallpaperCommonBaseHostProtocol", monitor_id: str):
        widget = self.monitor_widgets.get(monitor_id)
        if widget:
            path = self.monitor_image_paths.get(monitor_id)
            if path:
                thumb = self._get_or_generate_thumbnail(path)
                widget.set_image(path, thumb)
            else:
                widget.clear()

    def closeEvent(self: "WallpaperCommonBaseHostProtocol", event):  # noqa: C901
        # Drop the application-wide event filter this subtab may have
        # installed (see ``_ui_builder`` / ``_event_filter``). Leaving it
        # registered after teardown routes every app event through a dead
        # C++ wrapper and makes the whole app unclickable.
        app = QApplication.instance()
        if app is not None:
            with contextlib.suppress(Exception):
                app.removeEventFilter(self)

        # Stop slideshow and countdown timers
        if hasattr(self, "slideshow_timer") and self.slideshow_timer:
            try:
                self.slideshow_timer.stop()
                self.slideshow_timer.deleteLater()
            except Exception:
                pass
            self.slideshow_timer = None

        if hasattr(self, "countdown_timer") and self.countdown_timer:
            try:
                self.countdown_timer.stop()
                self.countdown_timer.deleteLater()
            except Exception:
                pass
            self.countdown_timer = None

        if hasattr(self, "_pagination_debounce_timer") and self._pagination_debounce_timer:
            try:
                self._pagination_debounce_timer.stop()
                self._pagination_debounce_timer.deleteLater()
            except Exception:
                pass
            self._pagination_debounce_timer = None  # pyrefly: ignore [bad-assignment]

        # Clean up image scanner thread
        if hasattr(self, "img_scanner_thread") and self.img_scanner_thread is not None:
            try:
                if self.img_scanner_thread.isRunning():
                    self.img_scanner_thread.requestInterruption()
                    self.img_scanner_thread.quit()
                    self.img_scanner_thread.wait()
                self.img_scanner_thread.deleteLater()
            except Exception:
                pass
            self.img_scanner_thread = None

        # Clean up video scanner thread
        if hasattr(self, "vid_scanner_thread") and self.vid_scanner_thread is not None:
            try:
                if self.vid_scanner_thread.isRunning():
                    self.vid_scanner_thread.requestInterruption()
                    self.vid_scanner_thread.quit()
                    self.vid_scanner_thread.wait()
                self.vid_scanner_thread.deleteLater()
            except Exception:
                pass
            self.vid_scanner_thread = None

        for win in list(self.open_queue_windows):
            try:
                if sip.isValid(win):
                    win.close()
            except RuntimeError:
                pass
        self.open_queue_windows: list = []

        for win in list(self.open_image_preview_windows):
            try:
                if sip.isValid(win):
                    win.close()
            except RuntimeError:
                pass
        self.open_image_preview_windows: list = []

        super().closeEvent(event)  # type: ignore[misc,safe-super]

    def _refresh_open_queue_window(self: "WallpaperCommonBaseHostProtocol", monitor_id: str):
        queue = self.monitor_slideshow_queues.get(monitor_id, [])
        for win in self.open_queue_windows:
            if (
                sip.isValid(win)
                and isinstance(win, SlideshowQueueWindow)
                and win.monitor_id == monitor_id
            ):
                win.populate_list(queue)

    def _is_daemon_running_config(self: "WallpaperCommonBaseHostProtocol") -> bool:
        if not os.path.exists(DAEMON_CONFIG_PATH):
            return False
        try:
            with open(DAEMON_CONFIG_PATH, "r") as f:
                config = json.load(f)
            return config.get("running", False)
        except Exception:
            return False


__all__ = ["_WidgetUiLifecycleMixin"]
