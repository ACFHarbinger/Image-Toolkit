"""Background slideshow daemon control (start/stop process, config sync, logs).

Extracted from ``system_display_subtab.py`` -- pure code motion, no logic
change (see ``_ui_builder.py``'s docstring).
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional, cast

from backend.src.constants import DAEMON_CONFIG_PATH, ROOT_DIR
from PySide6.QtCore import QObject, QTimer
from PySide6.QtWidgets import QMessageBox, QWidget

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...protos.system_display_subtab import SystemDisplaySubTabHostProtocol


class _DaemonMixin:
    """Countdown, config sync, process start/stop, and log viewer for the daemon."""

    countdown_timer: Optional[QTimer]

    def _start_daemon_countdown_if_active(self: "SystemDisplaySubTabHostProtocol"):
        if self._is_daemon_running_config():
            try:
                with open(DAEMON_CONFIG_PATH, "r") as f:
                    data = json.load(f)
                    self.interval_sec = data.get("interval_seconds", 300)
                    last_change = data.get("last_change_timestamp", 0)
                    if last_change > 0:
                        elapsed = int(time.time()) - last_change
                        self.time_remaining_sec = max(0, self.interval_sec - elapsed)
                    else:
                        self.time_remaining_sec = self.interval_sec

                    if not hasattr(self, "countdown_timer") or not self.countdown_timer:
                        countdown_timer = QTimer(cast(QObject, self))
                        self.countdown_timer = countdown_timer
                        countdown_timer.timeout.connect(self.update_countdown)

                    countdown_timer = self.countdown_timer
                    if countdown_timer is not None and not countdown_timer.isActive():
                        countdown_timer.start(1000)

                    self.update_countdown()

                    if not self.slideshow_group.isVisible():
                        self.slideshow_group.setVisible(True)
            except Exception:
                pass

    def _get_daemon_script_path(self: "SystemDisplaySubTabHostProtocol"):
        script_path = ROOT_DIR / "backend" / "src" / "utils" / "display" / "slideshow_daemon.py"
        if script_path.exists():
            return str(script_path)

        current_dir = Path(__file__).resolve().parent
        root = current_dir
        while not (root / "backend").exists() and root != root.parent:
            root = root.parent

        script_path = root / "backend" / "src" / "utils" / "display" / "slideshow_daemon.py"
        if not script_path.exists():
            script_path = root / "slideshow_daemon.py"

        return str(script_path)

    def _is_daemon_running_config(self: "SystemDisplaySubTabHostProtocol"):
        if not DAEMON_CONFIG_PATH.exists():
            return False
        try:
            with open(DAEMON_CONFIG_PATH, "r") as f:
                data = json.load(f)
                return data.get("running", False)
        except Exception:
            return False

    def _is_background_daemon_process_alive(self: "SystemDisplaySubTabHostProtocol") -> bool:
        """Whether a slideshow_daemon.py process is actually alive (not just
        the config file's stale 'running' flag from a process that crashed
        without cleaning up). Used to avoid spawning a second daemon process
        that would race the first one on the shared config file."""
        pid_path = Path.home() / ".image-toolkit" / ".slideshow_daemon.pid"
        try:
            pid = int(pid_path.read_text().strip())
            os.kill(pid, 0)
        except Exception:
            return False
        return True

    def _sync_daemon_config(self: "SystemDisplaySubTabHostProtocol"):
        if not self._is_daemon_running_config():
            return

        last_change_timestamp = 0
        monitor_history = getattr(self, "monitor_history", {})
        try:
            if os.path.exists(DAEMON_CONFIG_PATH):
                with open(DAEMON_CONFIG_PATH, "r") as f:
                    old_config = json.load(f)
                    last_change_timestamp = old_config.get("last_change_timestamp", 0)
                    file_history = old_config.get("monitor_history", {})
                    for k, v in file_history.items():
                        if k not in monitor_history:
                            monitor_history[k] = v
                    self.monitor_history = monitor_history
        except Exception:
            pass

        style_to_use = (
            f"SmartVideoWallpaper::{self.video_style}"
            if self.background_type in ["Smart Video", "Smart Video Slideshow"]
            else self.wallpaper_style
        )

        config = {
            "running": True,
            "interval_seconds": (self.interval_min_spinbox.value() * 60)
            + self.interval_sec_spinbox.value(),
            "use_video_runtime_interval": (
                self.background_type == "Smart Video Slideshow"
                and self.chk_video_runtime_interval.isChecked()
            ),
            "style": style_to_use,
            "monitor_queues": self.monitor_slideshow_queues,
            "current_paths": self.monitor_image_paths,
            "playback_order": self.playback_order_combo.currentText(),
            "filter_directories": [],
            "monitor_geometries": {
                str(i): {"x": m.x, "y": m.y, "width": m.width, "height": m.height}
                for i, m in enumerate(self.monitors)
            },
            "last_change_timestamp": last_change_timestamp,
            "monitor_history": self.monitor_history,
        }

        try:
            with open(DAEMON_CONFIG_PATH, "w") as f:
                json.dump(config, f, indent=4)
        except Exception:
            pass

    def toggle_daemon(self: "SystemDisplaySubTabHostProtocol", checked: bool):
        start = checked
        if start:
            self.stop_slideshow()

        last_change_timestamp = 0
        monitor_history = getattr(self, "monitor_history", {})
        try:
            if os.path.exists(DAEMON_CONFIG_PATH):
                with open(DAEMON_CONFIG_PATH, "r") as f:
                    old_config = json.load(f)
                    last_change_timestamp = old_config.get("last_change_timestamp", 0)
                    file_history = old_config.get("monitor_history", {})
                    for k, v in file_history.items():
                        if k not in monitor_history:
                            monitor_history[k] = v
                    self.monitor_history = monitor_history
        except Exception:
            pass

        style_to_use = (
            f"SmartVideoWallpaper::{self.video_style}"
            if self.background_type in ["Smart Video", "Smart Video Slideshow"]
            else self.wallpaper_style
        )

        config = {
            "running": start,
            "interval_seconds": (self.interval_min_spinbox.value() * 60)
            + self.interval_sec_spinbox.value(),
            "use_video_runtime_interval": (
                self.background_type == "Smart Video Slideshow"
                and self.chk_video_runtime_interval.isChecked()
            ),
            "style": style_to_use,
            "monitor_queues": self.monitor_slideshow_queues,
            "current_paths": self.monitor_image_paths,
            "playback_order": self.playback_order_combo.currentText(),
            "filter_directories": [],
            "monitor_geometries": {
                str(i): {"x": m.x, "y": m.y, "width": m.width, "height": m.height}
                for i, m in enumerate(self.monitors)
            },
            "last_change_timestamp": last_change_timestamp,
            "monitor_history": self.monitor_history,
        }

        try:
            with open(DAEMON_CONFIG_PATH, "w") as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            QMessageBox.critical(cast(QWidget, self), "Error", f"Failed to save daemon config: {e}")
            return

        if start and self._is_background_daemon_process_alive():
            # A daemon process is already alive and watching this same config
            # file for changes -- it will pick up the new settings (interval,
            # use_video_runtime_interval, queues, ...) on its own within a
            # second. Spawning a second process here would race the first on
            # the same config file and could clobber its settings mid-flight.
            self.btn_daemon_toggle.setText("Stop Background Daemon")
            self.btn_daemon_toggle.setStyleSheet(
                "background-color: #c0392b; color: white; padding: 5px;"
            )
            self._start_daemon_countdown_if_active()
            return

        if start:
            script_path = self._get_daemon_script_path()
            if not os.path.exists(script_path):
                QMessageBox.critical(
                    cast(QWidget, self), "Error", f"Daemon script not found at:\n{script_path}"
                )
                return
            try:
                if platform.system() == "Windows":
                    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
                    subprocess.Popen(
                        [sys.executable, script_path],
                        creationflags=creationflags,
                    )
                else:
                    # Inherit the full environment so the subprocess gets
                    # DBUS_SESSION_BUS_ADDRESS, DISPLAY, XAUTHORITY, etc.
                    # Without these, gsettings calls inside the detached
                    # session cannot reach the user's session bus and fail
                    # silently, causing wallpapers never to change.
                    daemon_env = os.environ.copy()
                    subprocess.Popen(
                        [sys.executable, script_path],
                        start_new_session=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        env=daemon_env,
                    )
                self.btn_daemon_toggle.setText("Stop Background Daemon")
                self.btn_daemon_toggle.setStyleSheet(
                    "background-color: #c0392b; color: white; padding: 5px;"
                )
                self._start_daemon_countdown_if_active()
            except Exception as e:
                QMessageBox.critical(cast(QWidget, self), "Error", f"Failed to start daemon: {e}")
        else:
            self.btn_daemon_toggle.setText("Start Background Daemon")
            self.btn_daemon_toggle.setStyleSheet(
                "background-color: #27ae60; color: white; padding: 5px;"
            )
            if hasattr(self, "countdown_timer") and self.countdown_timer:
                self.countdown_timer.stop()
            self.countdown_label.setText("Timer: --:--")

    def view_daemon_logs(self: "SystemDisplaySubTabHostProtocol"):
        log_path = Path.home() / ".image-toolkit" / "logs" / "slideshow_daemon.log"
        if not log_path.exists():
            QMessageBox.information(cast(QWidget, self), "No Logs", "No daemon log file found yet.")
            return
        try:
            if platform.system() == "Windows":
                start_fn = getattr(os, "startfile", None)
                if start_fn:
                    start_fn(str(log_path))
            elif platform.system() == "Darwin":
                subprocess.run(["open", str(log_path)])
            else:
                subprocess.run(["xdg-open", str(log_path)])
        except Exception as e:
            QMessageBox.critical(cast(QWidget, self), "Error", f"Could not open log file: {e}")


__all__ = ["_DaemonMixin"]
