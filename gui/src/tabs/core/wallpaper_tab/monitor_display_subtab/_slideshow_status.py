"""Slideshow button/status-label refresh for ``MonitorDisplaySubTab``.

Extracted from ``monitor_display_subtab.py`` -- pure code motion, no logic
change (see ``_ui_graph_canvas.py``'s docstring).
"""

from __future__ import annotations

import time
from typing import Optional

from backend.src.utils.display import monitor_slideshow_daemon as _monitor_slideshow
from .....styles import set_button_role

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...protos.monitor_display_subtab import MonitorDisplaySubTabHostProtocol


class _SlideshowStatusMixin:
    """Refresh the in-app/daemon toggle buttons and the queue position/timer labels."""

    def _update_slideshow_buttons(self: "MonitorDisplaySubTabHostProtocol"):
        monitor_id = self._current_monitor_id
        inapp_running = bool(monitor_id and self._inapp_active_monitor_id == monitor_id)
        daemon_running = bool(monitor_id and self._daemon_active_monitor_id == monitor_id)

        self._btn_inapp_slideshow.blockSignals(True)
        self._btn_inapp_slideshow.setChecked(inapp_running)
        self._btn_inapp_slideshow.setText(
            "⏹ Stop In-App Slideshow" if inapp_running else "▶ Start In-App Slideshow"
        )
        set_button_role(
            self._btn_inapp_slideshow, "danger" if inapp_running else "success"
        )
        self._btn_inapp_slideshow.blockSignals(False)

        self._btn_daemon_slideshow.blockSignals(True)
        self._btn_daemon_slideshow.setChecked(daemon_running)
        self._btn_daemon_slideshow.setText(
            "⏹ Stop Slideshow Daemon" if daemon_running else "⏱ Start Slideshow Daemon"
        )
        set_button_role(
            self._btn_daemon_slideshow, "danger" if daemon_running else "success"
        )
        self._btn_daemon_slideshow.blockSignals(False)

    def _update_queue_status_label(self: "MonitorDisplaySubTabHostProtocol"):
        monitor_id = self._current_monitor_id
        if monitor_id is None:
            self._queue_position_label.setText("-- / --")
            self._queue_timer_label.setText("Timer: --:--")
            return

        queue = self.monitor_slideshow_queues.get(monitor_id, [])
        total = len(queue)
        idx = self.monitor_current_index.get(monitor_id, -1)
        remaining: Optional[int] = None

        if self._inapp_active_monitor_id == monitor_id:
            status = _monitor_slideshow.status()
            if status and status.get("running"):
                self._sync_inapp_state_from_native(monitor_id, status)
                idx = status.get("current_index", idx)
                if idx is not None and idx < 0:
                    idx = -1
                last_change = status.get("last_change_timestamp", 0)
                dur = status.get("current_duration")
                if dur and last_change > 0:
                    remaining = max(0, int(round(dur - (time.time() - last_change))))
        elif self._daemon_active_monitor_id == monitor_id:
            status = self._read_daemon_status()
            if _monitor_slideshow.daemon_is_live(status):
                daemon_idx = status.get("current_index")
                if daemon_idx is not None:
                    idx = daemon_idx
                last_change = status.get("last_change_timestamp", 0)
                dur = status.get("current_duration")
                if dur and last_change > 0:
                    remaining = max(0, int(round(dur - (time.time() - last_change))))

        current_num = idx + 1 if 0 <= idx < total else 0  # pyrefly: ignore [unsupported-operation]
        self._queue_position_label.setText(f"{current_num} / {total}" if total else "-- / --")
        if remaining is not None:
            m, s = divmod(remaining, 60)
            self._queue_timer_label.setText(f"Timer: {m:02}:{s:02}")
        else:
            self._queue_timer_label.setText("Timer: --:--")


__all__ = ["_SlideshowStatusMixin"]
