"""Background slideshow daemon control (detached process) for ``MonitorDisplaySubTab``.

Extracted from ``monitor_display_subtab.py`` -- pure code motion, no logic
change (see ``_ui_graph_canvas.py``'s docstring).
"""

from __future__ import annotations

import json
import platform
import subprocess
import sys
from typing import Optional, cast

from backend.src.constants import MONITOR_SLIDESHOW_DAEMON_CONFIG_PATH, ROOT_DIR
from backend.src.utils.display import monitor_slideshow_daemon as _monitor_slideshow
from PySide6.QtCore import Slot
from PySide6.QtWidgets import QMessageBox, QWidget

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...protos.monitor_display_subtab import MonitorDisplaySubTabHostProtocol


class _SlideshowDaemonMixin:
    """Start/stop the detached background wallpaper-slideshow daemon process."""

    _daemon_active_monitor_id: Optional[str]
    _inapp_active_monitor_id: Optional[str]

    def _read_daemon_status(self: "MonitorDisplaySubTabHostProtocol") -> Optional[dict]:
        try:
            with open(MONITOR_SLIDESHOW_DAEMON_CONFIG_PATH, "r") as f:
                return json.load(f)
        except Exception:
            return None

    def _check_daemon_status_on_startup(self: "MonitorDisplaySubTabHostProtocol"):
        status = self._read_daemon_status()
        if _monitor_slideshow.daemon_is_live(status):
            self._daemon_active_monitor_id = str(status.get("monitor_id"))
            self._update_slideshow_buttons()
            self._update_queue_status_label()
            return
        self._daemon_active_monitor_id = None
        if status and status.get("running"):
            _monitor_slideshow.mark_stopped(status)

    @Slot()
    def _toggle_daemon_slideshow(self: "MonitorDisplaySubTabHostProtocol"):
        monitor_id = self._current_monitor_id
        if monitor_id is None:
            return
        if self._daemon_active_monitor_id == monitor_id:
            self._stop_daemon_slideshow()
        else:
            self._start_daemon_slideshow(monitor_id)

    def _start_daemon_slideshow(self: "MonitorDisplaySubTabHostProtocol", monitor_id: str):
        # Profile reload / implicit callers must not restart a live daemon
        # or overwrite its start-time queue.
        status = self._read_daemon_status()
        if (
            _monitor_slideshow.daemon_is_live(status)
            and str(status.get("monitor_id")) == str(monitor_id)
        ):
            self._daemon_active_monitor_id = str(monitor_id)
            return
        queue = self.monitor_slideshow_queues.get(monitor_id, [])
        if not queue:
            QMessageBox.information(
                cast(QWidget, self), "Empty Queue",
                "This display's Wallpaper Queue is empty. Use 'Export to Queue' "
                "or drop files onto the monitor first.",
            )
            self._update_slideshow_buttons()
            return
        if self._inapp_active_monitor_id == monitor_id:
            QMessageBox.warning(
                cast(QWidget, self), "Slideshow Conflict",
                "The in-app slideshow is running for this display. "
                "Stop it before starting the Slideshow Daemon.",
            )
            self._update_slideshow_buttons()
            return
        if self._daemon_active_monitor_id and self._daemon_active_monitor_id != monitor_id:
            reply = QMessageBox.question(
                cast(QWidget, self), "Daemon Already Running",
                "The Slideshow Daemon is already running for another display "
                f"(Monitor {self._daemon_active_monitor_id}). Only one display "
                "can run the daemon at a time. Switch it to this display?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                self._update_slideshow_buttons()
                return
            self._stop_daemon_slideshow()

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
        geometries = {
            str(i): {"x": m.x, "y": m.y, "width": m.width, "height": m.height}
            for i, m in enumerate(self.monitors)
        }
        current_path = self.monitor_image_paths.get(monitor_id)
        current_index = queue.index(current_path) if current_path in queue else -1  # pyrefly: ignore [bad-argument-type]
        config = {
            "running": True,
            "monitor_id": monitor_id,
            "queue": list(queue),
            "durations": list(durations),
            "style": style,
            "video_style": video_style,
            "monitor_geometries": geometries,
            "other_current_paths": other_paths,
            "current_index": current_index,
            "last_change_timestamp": 0,
        }
        try:
            MONITOR_SLIDESHOW_DAEMON_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(MONITOR_SLIDESHOW_DAEMON_CONFIG_PATH, "w") as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            QMessageBox.critical(
                cast(QWidget, self), "Error", f"Failed to write daemon config: {e}")
            return

        script_path = ROOT_DIR / "backend" / "src" / "utils" / "display" / "monitor_slideshow_daemon.py"
        if not script_path.exists():
            QMessageBox.critical(
                cast(QWidget, self), "Error", f"Daemon script not found at:\n{script_path}")
            return
        try:
            if platform.system() == "Windows":
                creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
                proc = subprocess.Popen(
                    [sys.executable, str(script_path)],
                    creationflags=creationflags,
                )
            else:
                proc = subprocess.Popen(
                    [sys.executable, str(script_path)],
                    start_new_session=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
        except Exception as e:
            QMessageBox.critical(
                cast(QWidget, self), "Error", f"Failed to start daemon: {e}")
            return

        config["pid"] = proc.pid
        try:
            with open(MONITOR_SLIDESHOW_DAEMON_CONFIG_PATH, "w") as f:
                json.dump(config, f, indent=2)
        except Exception:
            pass

        self._daemon_active_monitor_id = monitor_id
        self._update_slideshow_buttons()
        self._update_queue_status_label()

    def _stop_daemon_slideshow(self: "MonitorDisplaySubTabHostProtocol"):
        try:
            if MONITOR_SLIDESHOW_DAEMON_CONFIG_PATH.exists():
                with open(MONITOR_SLIDESHOW_DAEMON_CONFIG_PATH, "r") as f:
                    config = json.load(f)
                config["running"] = False
                with open(MONITOR_SLIDESHOW_DAEMON_CONFIG_PATH, "w") as f:
                    json.dump(config, f, indent=2)
        except Exception:
            pass
        self._daemon_active_monitor_id = None
        self._update_slideshow_buttons()
        self._update_queue_status_label()


__all__ = ["_SlideshowDaemonMixin"]
