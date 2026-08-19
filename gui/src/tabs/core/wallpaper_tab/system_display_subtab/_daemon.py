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
from typing import TYPE_CHECKING, Optional, cast

from backend.src.constants import DAEMON_CONFIG_PATH, ROOT_DIR
from backend.src.constants.utils import PID_PATH
from PySide6.QtCore import QObject, QTimer
from PySide6.QtWidgets import QMessageBox, QWidget

from .....styles import set_button_role

if TYPE_CHECKING:
    from ...protos.system_display_subtab import SystemDisplaySubTabHostProtocol


class _DaemonMixin:
    """Countdown, config sync, process start/stop, and log viewer for the daemon."""

    countdown_timer: Optional[QTimer]

    def _start_daemon_countdown_if_active(self: "SystemDisplaySubTabHostProtocol"):
        # Countdown follows the config "running" flag, not the pid file.
        # The child writes the pid after import/startup; gating on that
        # left Timer: --:-- even on a successful Start click.
        if not self._is_daemon_running_config():
            return
        try:
            with open(DAEMON_CONFIG_PATH, "r") as f:
                data = json.load(f)
            self.interval_sec = int(data.get("interval_seconds", 300) or 300)
            last_change = int(data.get("last_change_timestamp", 0) or 0)
            if last_change > 0:
                elapsed = int(time.time()) - last_change
                self.time_remaining_sec = max(0, self.interval_sec - elapsed)
            else:
                self.time_remaining_sec = self.interval_sec

            timer = getattr(self, "countdown_timer", None)
            try:
                needs_start = timer is None or not timer.isActive()
            except RuntimeError:
                timer = None
                needs_start = True
            if timer is None:
                timer = QTimer(cast(QObject, self))
                self.countdown_timer = timer
                timer.timeout.connect(self.update_countdown)
                needs_start = True
            if needs_start:
                timer.start(1000)

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

    def _daemon_config_running(self: "SystemDisplaySubTabHostProtocol") -> bool:
        """True if the config file says the daemon should be running.

        Used for UI (button/timer). Do not require a pid file here — the
        child writes that after it starts, and the GUI must show a
        countdown immediately on Start.
        """
        if not DAEMON_CONFIG_PATH.exists():
            return False
        try:
            with open(DAEMON_CONFIG_PATH, "r") as f:
                data = json.load(f)
            return bool(data.get("running", False))
        except Exception:
            return False

    def _is_daemon_running_config(self: "SystemDisplaySubTabHostProtocol"):
        return self._daemon_config_running()

    def _is_background_daemon_process_alive(self: "SystemDisplaySubTabHostProtocol") -> bool:
        """Whether a slideshow_daemon.py process is actually alive (not just
        the config file's stale 'running' flag from a process that crashed
        without cleaning up). Used to avoid spawning a second daemon process
        that would race the first one on the shared config file."""
        try:
            pid = int(PID_PATH.read_text().strip())
            os.kill(pid, 0)
        except Exception:
            return False
        return True

    def _reconcile_daemon_liveness_on_startup(self: "SystemDisplaySubTabHostProtocol") -> bool:
        """Startup-only liveness check (tab construction / app reopen).

        Unlike `_is_daemon_running_config()`, which must stay liveness-blind
        (a fresh Start click's child may not have written its pid file yet —
        see test_countdown_starts_before_pid_file_exists), a config inherited
        from a *previous* app session has had plenty of time to write a pid if
        the daemon is genuinely still alive. So here, and only here, a
        `"running": true` flag with no live process behind it is stale (an
        ungraceful shutdown/reboot/kill that never reached
        slideshow_daemon.py's `finally` cleanup) and gets corrected on disk so
        the UI does not show a dead daemon as running with a stuck timer.
        Returns the *actual* running state after any correction.
        """
        if not self._is_daemon_running_config():
            return False
        if self._is_background_daemon_process_alive():
            return True
        try:
            with open(DAEMON_CONFIG_PATH, "r") as f:
                data = json.load(f)
            data["running"] = False
            with open(DAEMON_CONFIG_PATH, "w") as f:
                json.dump(data, f, indent=4)
        except Exception:
            pass
        return False

    def _record_daemon_pid(self, pid: int) -> None:
        try:
            PID_PATH.parent.mkdir(parents=True, exist_ok=True)
            PID_PATH.write_text(str(pid))
        except Exception:
            pass

    def _sync_daemon_config(self: "SystemDisplaySubTabHostProtocol"):
        if not self._is_daemon_running_config():
            return

        last_change_timestamp = 0
        monitor_history = getattr(self, "monitor_history", {})
        old_config: dict = {}
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

        # Queue is locked at daemon start. Profile reload / spinbox sync
        # must not replace the running process's start-time playlist.
        locked_queues = old_config.get("monitor_queues", self.monitor_slideshow_queues)

        config = {
            "running": True,
            "interval_seconds": (self.interval_min_spinbox.value() * 60)
            + self.interval_sec_spinbox.value(),
            "use_video_runtime_interval": (
                self.background_type == "Smart Video Slideshow"
                and self.chk_video_runtime_interval.isChecked()
            ),
            "style": style_to_use,
            "monitor_queues": locked_queues,
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

        if start and last_change_timestamp <= 0:
            last_change_timestamp = int(time.time())

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
            set_button_role(self.btn_daemon_toggle, "danger")
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
                    proc = subprocess.Popen(
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
                    proc = subprocess.Popen(
                        [sys.executable, script_path],
                        start_new_session=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        env=daemon_env,
                    )
                self._record_daemon_pid(proc.pid)
                self.btn_daemon_toggle.setText("Stop Background Daemon")
                set_button_role(self.btn_daemon_toggle, "danger")
                self._start_daemon_countdown_if_active()
            except Exception as e:
                QMessageBox.critical(cast(QWidget, self), "Error", f"Failed to start daemon: {e}")
        else:
            self.btn_daemon_toggle.setText("Start Background Daemon")
            set_button_role(self.btn_daemon_toggle, "success")
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
