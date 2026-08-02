"""Tab-config persistence (``collect``/``get_default_config``/``set_config``).

Extracted from ``system_display_subtab.py`` -- pure code motion, no logic
change (see ``_ui_builder.py``'s docstring). ``set_config``'s deferred
scan-directory restore (via a single restartable timer, not
QTimer.singleShot) guards the same automatic session-recovery trigger
for the deleteOrphaned crash class documented in
``.agent/cache/gallery_crash_deleteorphaned_2026-07-27.md`` (Addendum
16) -- preserved verbatim, comments included.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Dict

from PySide6.QtWidgets import QMessageBox

from backend.src.core import telemetry

from ....components import DraggableMonitorContainer, MonitorDropView


class _ConfigMixin:
    """Save/restore monitor layout, style/interval settings, and queue state."""

    def collect(self) -> dict:
        monitor_order = []
        monitor_layout = []
        if isinstance(self.monitor_layout_container, DraggableMonitorContainer):
            for row in self.monitor_layout_container.rows:
                for widget in row:
                    if isinstance(widget, MonitorDropView):
                        monitor_order.append(widget.monitor_id)
            monitor_layout = self.monitor_layout_container.get_layout_structure()

        return {
            "scan_directory": self.scan_directory_path.text(),
            "wallpaper_style": self.wallpaper_style,
            "video_style": self.video_style,
            "slideshow_enabled": (self.background_type == "Slideshow"),
            "interval_minutes": self.interval_min_spinbox.value(),
            "interval_seconds": self.interval_sec_spinbox.value(),
            "use_video_runtime_interval": self.chk_video_runtime_interval.isChecked(),
            "background_type": self.background_type,
            "solid_color_hex": self.solid_color_hex,
            "playback_order": self.playback_order_combo.currentText(),
            "monitor_order": monitor_order,
            "monitor_layout": monitor_layout,
            "monitor_queues": self.monitor_slideshow_queues,
            "monitor_image_paths": self.monitor_image_paths,
        }

    def get_default_config(self) -> Dict[str, Any]:
        default_style = (
            self.style_combo.itemText(0) if self.style_combo.count() > 0 else "Fill"
        )
        return {
            "scan_directory": "",
            "wallpaper_style": default_style,
            "video_style": "Scaled and Cropped",
            "slideshow_enabled": False,
            "interval_minutes": 5,
            "interval_seconds": 0,
            "use_video_runtime_interval": False,
            "background_type": "Image",
            "solid_color_hex": "#000000",
            "monitor_order": [],
            "monitor_layout": [],
        }

    def set_config(self, config: Dict[str, Any]):  # noqa: C901
        print(
            f"[thread-lifecycle] t={time.monotonic():.3f} panel={id(self):x} "
            f"set_config() called, scan_directory={config.get('scan_directory')!r}",
            flush=True,
        )
        telemetry.emit(
            "thread-lifecycle", "set_config.called",
            panel=id(self), scan_directory=config.get("scan_directory"),
        )
        try:
            if "scan_directory" in config:
                self.scan_directory_path.setText(config.get("scan_directory", ""))
                if os.path.isdir(config["scan_directory"]):
                    # Deferred, not called synchronously: this runs during
                    # MainWindow/tab construction, before the Qt event loop
                    # has started processing events. Starting a new QThread
                    # (img_scanner_thread, via populate_scan_image_gallery ->
                    # _stop_scanner_threads/ImageScannerWorker) this early
                    # can race Qt Multimedia's own PipeWire backend probe (also
                    # thread-based, triggered by QtMultimedia's module
                    # import elsewhere in the app) during this same fragile
                    # startup window -- the exact "QSocketNotifier: ...
                    # from another thread -> heap corruption -> SIGABRT"
                    # pattern already documented and fixed for
                    # ExtractorTab's QAudioOutput construction
                    # (extractor_tab.py). Deferred via a single restartable
                    # timer (see __init__), not QTimer.singleShot -- if
                    # set_config() fires again before this restore has run
                    # (main_window.py's session-recovery flow calls
                    # set_config() on this tab twice back to back, see
                    # Addendum 16 in
                    # .agent/cache/gallery_crash_deleteorphaned_2026-07-27.md),
                    # the second call must supersede the first's pending
                    # restore, not race it with a second independent timer.
                    self._pending_restore_dir = config["scan_directory"]
                    print(
                        f"[thread-lifecycle] t={time.monotonic():.3f} panel={id(self):x} "
                        f"(re)starting scan-dir restore timer for {self._pending_restore_dir!r} "
                        f"(was_active={self._scan_dir_restore_timer.isActive()})",
                        flush=True,
                    )
                    telemetry.emit(
                        "thread-lifecycle", "scan_dir_restore_timer.restart",
                        panel=id(self), directory=self._pending_restore_dir,
                        was_active=self._scan_dir_restore_timer.isActive(),
                    )
                    self._scan_dir_restore_timer.start(250)
            if "wallpaper_style" in config:
                self.style_combo.setCurrentText(config.get("wallpaper_style", "Fill"))
            if "video_style" in config:
                self.video_style_combo.setCurrentText(
                    config.get("video_style", "Scaled and Cropped")
                )
            if "slideshow_enabled" in config:
                enabled = config.get("slideshow_enabled", False)
                if enabled:
                    self.background_type_combo.setCurrentText("Slideshow")
            if "interval_minutes" in config:
                self.interval_min_spinbox.setValue(config.get("interval_minutes", 5))
            if "interval_seconds" in config:
                self.interval_sec_spinbox.setValue(config.get("interval_seconds", 0))
            if "use_video_runtime_interval" in config:
                self.chk_video_runtime_interval.setChecked(
                    config.get("use_video_runtime_interval", False)
                )
            if "solid_color_hex" in config:
                self.solid_color_hex = config.get("solid_color_hex", "#000000")
                self.solid_color_preview.setStyleSheet(
                    f"background-color: {self.solid_color_hex}; border: 1px solid #4f545c;"
                )
            if "background_type" in config:
                self.background_type_combo.setCurrentText(
                    config.get("background_type", "Image")
                )
            if "playback_order" in config:
                self.playback_order_combo.setCurrentText(
                    config.get("playback_order", "Sequential")
                )

            layout_restored = False
            if "monitor_layout" in config and config["monitor_layout"] and isinstance(self.monitor_layout_container, DraggableMonitorContainer):
                    self.monitor_layout_container.set_layout_structure(
                        config["monitor_layout"], self.monitor_widgets
                    )
                    layout_restored = True

            if (
                not layout_restored
                and "monitor_order" in config
                and config["monitor_order"]
            ):
                target_order = config["monitor_order"]
                present_monitor_ids = set(self.monitor_widgets.keys())
                valid_order = [
                    mid for mid in target_order if mid in present_monitor_ids
                ]

                if isinstance(self.monitor_layout_container, DraggableMonitorContainer):
                    self.monitor_layout_container.clear_widgets()
                    for mid in valid_order:
                        if mid in self.monitor_widgets:
                            self.monitor_layout_container.addWidget(self.monitor_widgets[mid])  # pyrefly: ignore [bad-argument-type]
                    for mid, w in self.monitor_widgets.items():
                        if mid not in valid_order:
                            self.monitor_layout_container.addWidget(w)  # pyrefly: ignore [bad-argument-type]

            # Both monitor_slideshow_queues and monitor_image_paths are
            # shared by reference with MonitorDisplaySubTab (see
            # WallpaperTab.__init__); mutate them in place instead of
            # reassigning, or session restore silently breaks that link and
            # the Monitor Display subtab's queue/current-path edits stop
            # being visible to this tab's run_wallpaper_worker().
            if "monitor_queues" in config:
                self.monitor_slideshow_queues.clear()
                self.monitor_slideshow_queues.update(config.get("monitor_queues", {}))
            if "monitor_image_paths" in config:
                saved_paths = config.get("monitor_image_paths", {})
                self.monitor_image_paths.clear()
                self.monitor_image_paths.update(saved_paths)
                for mid, path in saved_paths.items():
                    if mid in self.monitor_widgets and path:
                        if Path(path).exists():
                            thumb = self._get_or_generate_thumbnail(path)
                            self.monitor_widgets[mid].set_image(path, thumb)
                        else:
                            self.monitor_image_paths[mid] = None
                            self.monitor_widgets[mid].clear()
        except Exception as e:
            QMessageBox.critical(
                self, "Config Error", f"Failed to apply wallpaper configuration:\n{e}"
            )

        if self._is_daemon_running_config():
            self._start_daemon_countdown_if_active()
        self.wallpapers_changed.emit()

    def _do_pending_scan_dir_restore(self) -> None:
        """Fires the single restartable restore timer from set_config().

        Reads self._pending_restore_dir at fire time rather than a value
        captured in a per-call closure, so if set_config() restarted this
        timer with a newer directory before it fired, only that latest
        value is ever used -- see set_config()'s scan_directory handling
        and Addendum 16 in
        .agent/cache/gallery_crash_deleteorphaned_2026-07-27.md.
        """
        print(
            f"[thread-lifecycle] t={time.monotonic():.3f} panel={id(self):x} "
            f"scan-dir restore timer FIRED for {self._pending_restore_dir!r}",
            flush=True,
        )
        telemetry.emit(
            "thread-lifecycle", "scan_dir_restore_timer.fired",
            panel=id(self), directory=self._pending_restore_dir,
        )
        if self._pending_restore_dir and os.path.isdir(self._pending_restore_dir):
            self.populate_scan_image_gallery(self._pending_restore_dir)


__all__ = ["_ConfigMixin"]
