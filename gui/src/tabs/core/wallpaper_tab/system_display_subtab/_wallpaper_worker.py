"""Background ``WallpaperWorker`` dispatch, UI lock/unlock, and result handling.

Extracted from ``system_display_subtab.py`` -- pure code motion, no logic
change (see ``_ui_builder.py``'s docstring).
"""

from __future__ import annotations

import contextlib
import platform
from typing import TYPE_CHECKING, Dict, Optional, cast

from backend.src.core import WallpaperManager
from PySide6.QtCore import QEvent, QObject, QThreadPool, Signal, Slot
from PySide6.QtWidgets import QApplication, QMessageBox, QWidget

from .....helpers import ImageScannerWorker, WallpaperWorker
from .....styles import STYLE_START_ACTION, STYLE_STOP_ACTION

if TYPE_CHECKING:
    from ...protos.system_display_subtab import SystemDisplaySubTabHostProtocol


class _WallpaperWorkerCompletionRelay(QObject):
    completed = Signal(int, bool, bool, str)

    def __init__(self, worker_serial: int, ui_locked: bool, parent: QObject):
        super().__init__(parent)
        self._worker_serial = worker_serial
        self._ui_locked = ui_locked

    @Slot(bool, str)
    def forward(self, success: bool, message: str):
        self.completed.emit(
            self._worker_serial, self._ui_locked, success, message
        )


class _WallpaperWorkerMixin:
    """Run/stop the wallpaper-setting worker; lock/unlock UI; handle results."""

    current_wallpaper_worker: Optional[WallpaperWorker]

    def run_wallpaper_worker(self: "SystemDisplaySubTabHostProtocol", slideshow_mode=False):  # noqa: C901
        if self.current_wallpaper_worker:
            print("Wallpaper worker is already running.")
            return

        path_map: Dict[str, Optional[str]]
        final_path_map: Dict[str, Optional[str]]

        if self.background_type == "Solid Color":
            path_map = {
                str(mid): self.solid_color_hex for mid in range(len(self.monitors))
            }
            style_to_use = "SolidColor"
            final_path_map = path_map
        else:
            if not any(self.monitor_image_paths.values()):
                if not slideshow_mode:
                    QMessageBox.warning(
                        cast(QWidget, self),
                        "Incomplete",
                        "No images/videos have been dropped on the monitors.",
                    )
                return

            if ImageScannerWorker is None:
                QMessageBox.warning(
                        cast(QWidget, self),
                    "Missing Helpers",
                    "The ImageScannerWorker or ImageLoaderWorker could not be imported.",
                )
                return

            if not slideshow_mode:
                current_system_paths = self._get_current_system_image_paths_for_all()
                path_map = current_system_paths.copy()
                for monitor_id in [str(i) for i in range(len(self.monitors))]:
                    user_path = self.monitor_image_paths.get(monitor_id)
                    if user_path:
                        path_map[monitor_id] = user_path
                    elif monitor_id not in path_map:
                        widget = self.monitor_widgets.get(monitor_id)
                        if widget and widget.image_path:
                            path_map[monitor_id] = widget.image_path
                        else:
                            path_map[monitor_id] = None
            else:
                path_map = self.monitor_image_paths.copy()

            system = platform.system()
            if system == "Linux":
                try:
                    desktop = "KDE" if self.qdbus else "Gnome"
                except Exception:
                    desktop = None
            elif system == "Windows":
                desktop = "Windows"
            else:
                desktop = None

            if self.background_type in ["Smart Video", "Smart Video Slideshow"]:
                style_to_use = f"SmartVideoWallpaper::{self.video_style}"
            else:
                style_to_use = self.wallpaper_style

            if desktop == "Windows" and not WallpaperManager.COM_AVAILABLE:
                path_to_set = next((p for p in path_map.values() if p), None)
                final_path_map = {"0": path_to_set} if path_to_set else {}
            else:
                final_path_map = path_map

        ui_locked = not slideshow_mode
        if ui_locked:
            self.lock_ui_for_wallpaper()

        self._wallpaper_worker_serial += 1
        worker_serial = self._wallpaper_worker_serial
        self._active_wallpaper_worker_serial = worker_serial
        self._wallpaper_worker_ui_locked = ui_locked

        worker = None
        relay = None
        try:
            worker = WallpaperWorker(
                final_path_map,
                self.monitors,
                self.qdbus,
                wallpaper_style=style_to_use,
            )
            self.current_wallpaper_worker = worker
            relay = _WallpaperWorkerCompletionRelay(
                worker_serial, ui_locked, cast(QObject, self)
            )
            self._wallpaper_worker_completion_relay = relay
            worker.signals.status_update.connect(self.handle_wallpaper_status)
            worker.signals.work_finished.connect(relay.forward)
            relay.completed.connect(self._handle_wallpaper_worker_finished)
            QThreadPool.globalInstance().start(worker)
        except Exception as exc:
            if worker is not None and relay is not None:
                with contextlib.suppress(Exception):
                    worker.signals.work_finished.disconnect(relay.forward)
                relay.deleteLater()
            self.current_wallpaper_worker = None
            self._active_wallpaper_worker_serial = None
            self._wallpaper_worker_completion_relay = None
            self._wallpaper_worker_ui_locked = False
            if ui_locked:
                self.unlock_ui_for_wallpaper()
            QMessageBox.critical(
                cast(QWidget, self),
                "Wallpaper Error",
                f"Failed to start the wallpaper worker:\n{exc}",
            )

    def stop_wallpaper_worker(self: "SystemDisplaySubTabHostProtocol"):
        if self.current_wallpaper_worker:
            worker = self.current_wallpaper_worker
            ui_locked = self._wallpaper_worker_ui_locked
            relay = self._wallpaper_worker_completion_relay
            self.current_wallpaper_worker = None
            self._active_wallpaper_worker_serial = None
            self._wallpaper_worker_completion_relay = None
            self._wallpaper_worker_ui_locked = False
            try:
                if relay is not None:
                    with contextlib.suppress(Exception):
                        worker.signals.work_finished.disconnect(relay.forward)
                    relay.deleteLater()
                worker.stop()
                self.handle_wallpaper_status("Manual stop requested.")
            finally:
                if ui_locked:
                    self.unlock_ui_for_wallpaper()

    def lock_ui_for_wallpaper(self: "SystemDisplaySubTabHostProtocol"):
        self.set_wallpaper_btn.setText("Applying (Click to Stop)")
        self.set_wallpaper_btn.setStyleSheet(STYLE_STOP_ACTION)
        self.set_wallpaper_btn.setEnabled(True)
        self.slideshow_group.setEnabled(False)
        self.gallery_scroll_area.setEnabled(False)  # pyrefly: ignore [missing-attribute]
        self.scan_directory_path.setEnabled(False)
        self.style_combo.setEnabled(False)
        self.video_style_combo.setEnabled(False)
        self.background_type_combo.setEnabled(False)
        self.solid_color_widget.setEnabled(False)
        for widget in self.monitor_widgets.values():
            widget.setEnabled(False)
        QApplication.sendPostedEvents(None, QEvent.Type.Paint)

    def unlock_ui_for_wallpaper(self: "SystemDisplaySubTabHostProtocol"):
        self.slideshow_group.setEnabled(True)
        self.gallery_scroll_area.setEnabled(True)  # pyrefly: ignore [missing-attribute]
        self.scan_directory_path.setEnabled(True)
        self.style_combo.setEnabled(True)
        self.video_style_combo.setEnabled(True)
        self.background_type_combo.setEnabled(True)
        self.solid_color_widget.setEnabled(True)
        for widget in self.monitor_widgets.values():
            widget.setEnabled(True)
        self._update_background_type(self.background_type)
        slideshow_running = bool(
            self.slideshow_timer and self.slideshow_timer.isActive()
        )
        if slideshow_running:
            self.set_wallpaper_btn.setText("Slideshow Running (Stop)")
            self.set_wallpaper_btn.setStyleSheet(STYLE_STOP_ACTION)
            self.set_wallpaper_btn.setEnabled(True)
        else:
            self.set_wallpaper_btn.setStyleSheet(STYLE_START_ACTION)
            self.check_all_monitors_set()
        QApplication.sendPostedEvents(None, QEvent.Type.Paint)

    @Slot(str)
    def handle_wallpaper_status(self: "SystemDisplaySubTabHostProtocol", msg: str):
        print(f"[WallpaperWorker] {msg}")

    def _handle_wallpaper_worker_finished(
        self: "SystemDisplaySubTabHostProtocol",
        worker_serial: int,
        ui_locked: bool,
        success: bool,
        message: str,
    ):
        if worker_serial != self._active_wallpaper_worker_serial:
            return

        relay = self._wallpaper_worker_completion_relay
        self.current_wallpaper_worker = None
        self._active_wallpaper_worker_serial = None
        self._wallpaper_worker_completion_relay = None
        self._wallpaper_worker_ui_locked = False
        try:
            self._process_wallpaper_finished(success, message)
        finally:
            if ui_locked:
                self.unlock_ui_for_wallpaper()
            if relay is not None:
                relay.deleteLater()

    def _process_wallpaper_finished(
        self: "SystemDisplaySubTabHostProtocol", success: bool, message: str
    ):
        is_slideshow_active = self.slideshow_timer and self.slideshow_timer.isActive()
        if success:
            if not is_slideshow_active and self.background_type != "Solid Color":
                QMessageBox.information(
                        cast(QWidget, self), "Success", "Wallpaper has been updated!")
                for monitor_id, path in self.monitor_image_paths.items():
                    if path and monitor_id in self.monitor_widgets:
                        thumb = self._get_or_generate_thumbnail(path)
                        self.monitor_widgets[monitor_id].set_image(path, thumb)
            elif self.background_type == "Solid Color":
                QMessageBox.information(
                        cast(QWidget, self),
                    "Success",
                    f"Solid color background set to {self.solid_color_hex}!",
                )
        else:
            if "manually cancelled" not in message.lower():
                if is_slideshow_active:
                    print(f"Slideshow Error: Failed to set wallpaper: {message}")
                    self.stop_slideshow()
                else:
                    QMessageBox.critical(
                        cast(QWidget, self), "Error", f"Failed to set wallpaper:\n{message}"
                    )

    def _apply_vault_slideshow_defaults(self: "SystemDisplaySubTabHostProtocol"):
        main_win = self.window()
        if not (main_win and hasattr(main_win, "cached_creds")):
            return
        prefs = main_win.cached_creds.get("preferences", {})
        if self.interval_min_spinbox.value() == 5:
            vault_min = prefs.get("slideshow_interval_min", 5)
            self.interval_min_spinbox.setValue(vault_min)
        if self.interval_sec_spinbox.value() == 0:
            vault_sec = prefs.get("slideshow_interval_sec", 0)
            self.interval_sec_spinbox.setValue(vault_sec)
        if self.playback_order_combo.currentText() == "Sequential":
            vault_order = prefs.get("slideshow_order", "Sequential")
            self.playback_order_combo.setCurrentText(vault_order)


__all__ = ["_WallpaperWorkerMixin"]
