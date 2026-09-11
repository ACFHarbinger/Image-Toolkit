"""Monitor-layout refresh and worker/timer/window teardown overrides.

Extracted from ``system_display_subtab.py`` -- pure code motion, no logic
change (see ``_ui_builder.py``'s docstring).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from gui.src.helpers.worker_teardown import close_windows, stop_workers

if TYPE_CHECKING:
    from ...protos.system_display_subtab import SystemDisplaySubTabHostProtocol


class _LifecycleMixin:
    """Override WallpaperCommonBase hooks with SystemDisplaySubTab-specific cleanup."""

    def populate_monitor_layout(self: "SystemDisplaySubTabHostProtocol"):
        super().populate_monitor_layout()  # type: ignore[safe-super]
        self.check_all_monitors_set()

    def cancel_loading(self: "SystemDisplaySubTabHostProtocol"):
        super().cancel_loading()  # type: ignore[safe-super]

        # Fire-and-forget (as before): scanner threads die off on their own.
        stop_workers(
            getattr(self, "img_scanner_worker", None),
            getattr(self, "vid_scanner_worker", None),
            join=False,
        )

        if (
            getattr(self, "_pagination_debounce_timer", None) is not None
            and self._pagination_debounce_timer.isActive()
        ):
            self._pagination_debounce_timer.stop()

        if self.slideshow_timer and self.slideshow_timer.isActive():
            self.slideshow_timer.stop()
        daemon_live = self._is_daemon_running_config()
        if (
            self.countdown_timer
            and self.countdown_timer.isActive()
            and not daemon_live
        ):
            self.countdown_timer.stop()

        # (Was two passes per list — a plain close-all plus a guarded
        # isVisible re-close. One guarded pass closes everything once.)
        close_windows(
            self, "open_queue_windows", "open_image_preview_windows"
        )

        if daemon_live:
            self._start_daemon_countdown_if_active()
        else:
            self.monitor_current_index.clear()
            self.monitor_history.clear()
            self.time_remaining_sec = 0
            self.countdown_label.setText("Timer: --:--")

        self.unlock_ui_for_wallpaper()


__all__ = ["_LifecycleMixin"]
