"""Local (in-app) slideshow start/stop/cycle/skip and countdown display.

Extracted from ``system_display_subtab.py`` -- pure code motion, no logic
change (see ``_ui_builder.py``'s docstring).
"""

from __future__ import annotations

import json
import logging
import os
import random
import time
from typing import TYPE_CHECKING, Dict, Optional, cast

from backend.src.constants import DAEMON_CONFIG_PATH
from PySide6.QtCore import QObject, QTimer, Slot
from PySide6.QtWidgets import QMessageBox, QWidget

from .....styles import STYLE_STOP_ACTION, set_button_role
from ._video_duration import _get_video_duration, _is_video

if TYPE_CHECKING:
    from ...protos.system_display_subtab import SystemDisplaySubTabHostProtocol


class _SlideshowMixin:
    """Start/stop/cycle the local slideshow timer and update its countdown label."""

    slideshow_timer: Optional[QTimer]
    countdown_timer: Optional[QTimer]

    @Slot()
    def handle_set_wallpaper_click(self: "SystemDisplaySubTabHostProtocol"):
        if self.background_type == "Solid Color":
            if self.current_wallpaper_worker:
                self.stop_wallpaper_worker()
            else:
                self.run_wallpaper_worker()
            return

        if self.slideshow_timer and self.slideshow_timer.isActive():
            self.stop_slideshow()
        elif self.background_type in ["Slideshow", "Smart Video Slideshow"]:
            self.start_slideshow()
        else:
            if self.current_wallpaper_worker:
                self.stop_wallpaper_worker()
            else:
                self.run_wallpaper_worker()

    def _compute_video_runtime_interval_sec(
        self: "SystemDisplaySubTabHostProtocol", monitor_paths: Optional[Dict[str, Optional[str]]] = None
    ) -> Optional[int]:
        """Longest duration among the currently displayed videos across
        monitors, so no monitor's video gets cut off early. Returns None
        when nothing currently showing is a video, or its duration
        can't be determined -- callers should fall back to the fixed
        interval spinboxes in that case."""
        if monitor_paths is None:
            monitor_paths = self.monitor_image_paths
        durations = []
        for path in monitor_paths.values():
            if path and _is_video(path):
                dur = _get_video_duration(path)
                if dur:
                    durations.append(dur)
        if not durations:
            return None
        return max(1, round(max(durations)))

    @Slot()
    def start_slideshow(self: "SystemDisplaySubTabHostProtocol"):
        if self._is_daemon_running_config():
            QMessageBox.warning(
                cast(QWidget, self),
                "Daemon Conflict",
                "The background slideshow daemon is currently running. "
                "Please stop it before starting a local slideshow to avoid double-transitions.",
            )
            return

        num_monitors = len(self.monitor_widgets)
        if self.background_type == "Solid Color":
            QMessageBox.warning(
                cast(QWidget, self),
                "Slideshow Error",
                "Slideshow is disabled when Solid Color mode is selected.",
            )
            return
        is_ready, total_images = self._is_slideshow_validation_ready()
        if num_monitors == 0:
            QMessageBox.warning(
                cast(QWidget, self), "Slideshow Error", "No monitors detected or configured."
            )
            return
        if not is_ready:
            QMessageBox.critical(
                cast(QWidget, self),
                "Slideshow Error",
                "To start the slideshow, at least one monitor must have images dropped on it.",
            )
            return
        self.stop_slideshow()
        for mid in self.monitor_widgets.keys():
            queue = self.monitor_slideshow_queues.get(mid, [])
            current_path = self.monitor_image_paths.get(mid)
            if current_path in queue:
                self.monitor_current_index[mid] = queue.index(current_path)  # pyrefly: ignore [bad-argument-type]
            else:
                self.monitor_current_index[mid] = -1

        interval_minutes = self.interval_min_spinbox.value()
        interval_seconds = self.interval_sec_spinbox.value()
        self.interval_sec = (interval_minutes * 60) + interval_seconds
        use_video_runtime = (
            self.background_type == "Smart Video Slideshow"
            and self.chk_video_runtime_interval.isChecked()
        )
        if not use_video_runtime and self.interval_sec <= 0:
            QMessageBox.critical(
                cast(QWidget, self),
                "Slideshow Error",
                "Slideshow interval must be greater than 0 seconds.",
            )
            return
        if use_video_runtime:
            # Placeholder until the first cycle below determines the actual
            # video's runtime and corrects the timer.
            self.interval_sec = max(self.interval_sec, 1)
        interval_ms = self.interval_sec * 1000
        self.time_remaining_sec = self.interval_sec
        slideshow_timer = QTimer(cast(QObject, self))
        self.slideshow_timer = slideshow_timer
        slideshow_timer.timeout.connect(self._cycle_slideshow_wallpaper)
        slideshow_timer.start(interval_ms)
        countdown_timer = QTimer(cast(QObject, self))
        self.countdown_timer = countdown_timer
        countdown_timer.timeout.connect(self.update_countdown)
        countdown_timer.start(1000)
        if use_video_runtime:
            QMessageBox.information(
                cast(QWidget, self),
                "Slideshow Started",
                f"Per-monitor slideshow started with {total_images} total items, "
                "cycling at each video's own runtime.",
            )
        else:
            QMessageBox.information(
                cast(QWidget, self),
                "Slideshow Started",
                f"Per-monitor slideshow started with {total_images} total items, cycling every {interval_minutes} minutes and {interval_seconds} seconds.",
            )
        self._cycle_slideshow_wallpaper(increment=False)
        self.set_wallpaper_btn.setText("Slideshow Running (Stop)")
        self.set_wallpaper_btn.setStyleSheet(STYLE_STOP_ACTION)
        self.set_wallpaper_btn.setEnabled(True)

    def update_countdown(self: "SystemDisplaySubTabHostProtocol"):
        if self.time_remaining_sec % 5 == 0 or self.time_remaining_sec <= 0:
            try:
                if self._is_daemon_running_config():
                    with open(DAEMON_CONFIG_PATH, "r") as f:
                        config = json.load(f)
                        last_change = config.get("last_change_timestamp", 0)
                        interval = config.get("interval_seconds", self.interval_sec)
                        last_error = config.get("last_error")

                        if last_error:
                            self.countdown_label.setText(f"Error: {last_error[:20]}...")
                            self.countdown_label.setToolTip(last_error)
                        elif last_change > 0:
                            elapsed = int(time.time()) - last_change
                            remaining = max(0, interval - elapsed)
                            self.time_remaining_sec = remaining
                            self.countdown_label.setToolTip("")
            except Exception:
                pass

        if self.time_remaining_sec > 0:
            self.time_remaining_sec -= 1
            m, s = divmod(self.time_remaining_sec, 60)
            if "Error" not in self.countdown_label.text():
                self.countdown_label.setText(f"Timer: {m:02}:{s:02}")
        else:
            if "Error" not in self.countdown_label.text():
                self.countdown_label.setText("Timer: 00:00")
            # Config's "running" flag can go stale if the daemon process died
            # without reaching its cleanup (crash, OOM, hard kill): reuses the
            # PID-liveness check to catch that, instead of trusting the flag
            # alone, so the countdown doesn't stay pinned at 00:00 forever.
            if not self._reconcile_daemon_liveness_on_startup():
                self.time_remaining_sec = self.interval_sec
                if hasattr(self, "countdown_timer") and self.countdown_timer:
                    self.countdown_timer.stop()
                if hasattr(self, "btn_daemon_toggle"):
                    self.btn_daemon_toggle.setChecked(False)
                    self.btn_daemon_toggle.setText("Start Background Daemon")
                    set_button_role(self.btn_daemon_toggle, "success")
                self.countdown_label.setText("Timer: --:--")

    @Slot()
    def stop_slideshow(self: "SystemDisplaySubTabHostProtocol"):
        if self.slideshow_timer and self.slideshow_timer.isActive():
            self.slideshow_timer.stop()
            self.slideshow_timer.deleteLater()
            self.slideshow_timer = None
            QMessageBox.information(
                cast(QWidget, self), "Slideshow Stopped", "Wallpaper slideshow stopped."
            )

        if self.countdown_timer and self.countdown_timer.isActive() and not self._is_daemon_running_config():
            self.countdown_timer.stop()
            self.countdown_timer.deleteLater()
            self.countdown_timer = None

        self.stop_wallpaper_worker()
        self.check_all_monitors_set()

    @Slot()
    def skip_current_wallpapers(self: "SystemDisplaySubTabHostProtocol"):
        if self.background_type == "Solid Color":
            return

        self._cycle_slideshow_wallpaper(increment=True)

        if self._is_daemon_running_config():
            self._sync_daemon_config()
            try:
                if os.path.exists(DAEMON_CONFIG_PATH):
                    with open(DAEMON_CONFIG_PATH, "r") as f:
                        config = json.load(f)
                    config["last_change_timestamp"] = int(time.time())
                    with open(DAEMON_CONFIG_PATH, "w") as f:
                        json.dump(config, f, indent=4)
                    self.time_remaining_sec = self.interval_sec
                    self.update_countdown()
            except Exception:
                pass
        elif self.slideshow_timer and self.slideshow_timer.isActive():
            self.slideshow_timer.start(self.interval_sec * 1000)
            self.time_remaining_sec = self.interval_sec
            if self.countdown_timer and self.countdown_timer.isActive():
                self.update_countdown()

    @Slot()
    def _cycle_slideshow_wallpaper(self: "SystemDisplaySubTabHostProtocol", increment: bool = True):  # noqa: C901
        monitor_ids = list(self.monitor_widgets.keys())
        if not monitor_ids:
            return
        if self.background_type == "Solid Color":
            self.stop_slideshow()
            return
        try:
            new_monitor_paths: Dict[str, Optional[str]] = {}
            has_valid_path_to_set = False
            for monitor_id in monitor_ids:
                current_index = self.monitor_current_index.get(monitor_id, -1)
                queue = self.monitor_slideshow_queues.get(monitor_id, [])
                current_queue_length = len(queue)
                if current_queue_length > 0:
                    if not increment:
                        next_index = max(0, current_index)
                        playback_order = self.playback_order_combo.currentText()
                        if playback_order == "Random" and 0 <= next_index < len(queue):
                            next_path = queue[next_index]
                            if monitor_id not in self.monitor_history:
                                self.monitor_history[monitor_id] = []
                            if next_path not in self.monitor_history[monitor_id]:
                                self.monitor_history[monitor_id].append(next_path)
                    else:
                        playback_order = self.playback_order_combo.currentText()
                        if playback_order == "Random":
                            history = self.monitor_history.get(monitor_id, [])
                            valid_indices = [
                                idx
                                for idx, path in enumerate(queue)
                                if path not in history
                            ]

                            if not valid_indices:
                                current_path = (
                                    queue[current_index]
                                    if 0 <= current_index < len(queue)
                                    else None
                                )
                                if current_path and current_queue_length > 1:
                                    self.monitor_history[monitor_id] = [current_path]
                                    valid_indices = [
                                        idx
                                        for idx, path in enumerate(queue)
                                        if path != current_path
                                    ]
                                else:
                                    self.monitor_history[monitor_id] = []
                                    valid_indices = list(range(current_queue_length))

                            next_index = random.choice(valid_indices)
                            next_path = queue[next_index]
                            if monitor_id not in self.monitor_history:
                                self.monitor_history[monitor_id] = []
                            self.monitor_history[monitor_id].append(next_path)
                        elif playback_order == "Reverse Sequential":
                            if current_index == -1:
                                next_index = current_queue_length - 1
                            else:
                                next_index = (current_index - 1) % current_queue_length
                        else:
                            next_index = (current_index + 1) % current_queue_length

                    logging.info(
                        f"[SystemDisplaySubTab] Monitor {monitor_id}: current_index={current_index}, "
                        f"playback_order={self.playback_order_combo.currentText()}, "
                        f"increment={increment}, queue_length={current_queue_length} -> next_index={next_index}"
                    )

                    next_path = queue[next_index]
                    new_monitor_paths[monitor_id] = next_path
                    self.monitor_current_index[monitor_id] = next_index
                    has_valid_path_to_set = True
                else:
                    new_monitor_paths[monitor_id] = self.monitor_image_paths.get(monitor_id)
                    self.monitor_current_index[monitor_id] = -1
            if not has_valid_path_to_set:
                self.stop_slideshow()
                return
            # Mutate in place rather than reassign: monitor_image_paths is
            # shared by reference with MonitorDisplaySubTab (see
            # WallpaperTab.__init__); reassigning here would silently break
            # that link and desync the two subtabs' view of "current path".
            self.monitor_image_paths.clear()
            self.monitor_image_paths.update(new_monitor_paths)
            self.run_wallpaper_worker(slideshow_mode=True)
            for monitor_id, path in new_monitor_paths.items():
                if monitor_id in self.monitor_widgets and path:
                    thumb = self._get_or_generate_thumbnail(path)
                    self.monitor_widgets[monitor_id].set_image(path, thumb)

            if (
                self.background_type == "Smart Video Slideshow"
                and self.chk_video_runtime_interval.isChecked()
            ):
                computed = self._compute_video_runtime_interval_sec(new_monitor_paths)
                if computed:
                    self.interval_sec = computed
                if self.slideshow_timer and self.slideshow_timer.isActive():
                    self.slideshow_timer.start(self.interval_sec * 1000)
            self.time_remaining_sec = self.interval_sec
        except Exception as e:
            QMessageBox.critical(
                cast(QWidget, self), "Slideshow Cycle Error", f"Failed to cycle wallpaper: {str(e)}"
            )
            self.stop_slideshow()


__all__ = ["_SlideshowMixin"]
