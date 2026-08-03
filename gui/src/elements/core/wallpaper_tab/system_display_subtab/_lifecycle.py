"""Monitor-layout refresh and worker/timer/window teardown overrides.

Extracted from ``system_display_subtab.py`` -- pure code motion, no logic
change (see ``_ui_builder.py``'s docstring).
"""

from __future__ import annotations

import contextlib

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...protos.system_display_subtab import SystemDisplaySubTabHostProtocol


class _LifecycleMixin:
    """Override WallpaperCommonBase hooks with SystemDisplaySubTab-specific cleanup."""

    def populate_monitor_layout(self: "SystemDisplaySubTabHostProtocol"):
        super().populate_monitor_layout()  # type: ignore[safe-super]
        self.check_all_monitors_set()

    def cancel_loading(self: "SystemDisplaySubTabHostProtocol"):
        super().cancel_loading()  # type: ignore[safe-super]

        if self.img_scanner_worker:
            with contextlib.suppress(Exception):
                self.img_scanner_worker.stop()

        if self.vid_scanner_worker:
            with contextlib.suppress(Exception):
                self.vid_scanner_worker.stop()

        if (
            getattr(self, "_pagination_debounce_timer", None) is not None
            and self._pagination_debounce_timer.isActive()
        ):
            self._pagination_debounce_timer.stop()

        if self.slideshow_timer and self.slideshow_timer.isActive():
            self.slideshow_timer.stop()
        if self.countdown_timer and self.countdown_timer.isActive():
            self.countdown_timer.stop()

        for win in list(self.open_queue_windows):
            with contextlib.suppress(Exception):
                win.close()
        self.open_queue_windows.clear()

        for win in list(self.open_image_preview_windows):
            with contextlib.suppress(Exception):
                win.close()
        self.open_image_preview_windows.clear()

        for win in list(self.open_queue_windows):
            try:
                if win.isVisible():
                    win.close()
            except RuntimeError:
                pass
        self.open_queue_windows.clear()

        for win in list(self.open_image_preview_windows):
            try:
                if win.isVisible():
                    win.close()
            except RuntimeError:
                pass
        self.open_image_preview_windows.clear()

        if not self._is_daemon_running_config():
            self.monitor_current_index.clear()
            self.monitor_history.clear()
            self.time_remaining_sec = 0
            self.countdown_label.setText("Timer: --:--")

        self.unlock_ui_for_wallpaper()


__all__ = ["_LifecycleMixin"]
