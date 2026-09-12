"""``SystemDisplaySubTab`` -- composed TabBoundControllers + WallpaperCommonBase."""

from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import QTimer

from gui.src.helpers.worker_teardown import close_windows, stop_workers

from ..common.wallpaper_common_base import WallpaperCommonBase
from ._config import SystemDisplayConfigController
from ._daemon import SystemDisplayDaemonController
from ._lifecycle import SystemDisplayLifecycleController
from ._slideshow import SystemDisplaySlideshowController
from ._style_selectors import SystemDisplayStyleSelectorsController
from ._ui_builder import SystemDisplayUIBuilder
from ._wallpaper_worker import SystemDisplayWallpaperWorkerController


def _delegate(attr: str, name: str):
    def _fn(self, *args, **kwargs):
        return getattr(getattr(self, attr), name)(*args, **kwargs)

    _fn.__name__ = name
    _fn.__qualname__ = f"SystemDisplaySubTab.{name}"
    return _fn


class SystemDisplaySubTab(WallpaperCommonBase):
    """System wallpaper management subtab.

    Full-featured wallpaper setter with monitor layout, gallery,
    slideshow, daemon, and solid-color modes.
    """

    interval_container: Any
    interval_min_spinbox: Any
    interval_sec_spinbox: Any
    chk_video_runtime_interval: Any
    playback_order_combo: Any
    playback_order_label: Any
    style_combo: Any
    scan_directory_path: Any
    gallery_scroll_area: Any
    main_scroll_area: Any
    set_wallpaper_btn: Any
    background_type_combo: Any
    style_label: Any
    video_style_combo: Any
    video_style_label: Any
    style_layout_widget: Any
    status_timer: Any
    countdown_timer: Optional[QTimer]

    def __init__(self, database_service):
        super().__init__()
        self.database_service = database_service

        self.countdown_timer: Optional[QTimer] = None
        self.time_remaining_sec: int = 0
        self.interval_sec: int = 0

        self.ui_builder = SystemDisplayUIBuilder(self)
        self.daemon_controller = SystemDisplayDaemonController(self)
        self.style_selectors_controller = SystemDisplayStyleSelectorsController(self)
        self.slideshow_controller = SystemDisplaySlideshowController(self)
        self.lifecycle_controller = SystemDisplayLifecycleController(self)
        self.wallpaper_worker_controller = SystemDisplayWallpaperWorkerController(self)
        self.config_controller = SystemDisplayConfigController(self)

        # Session-recovery restart (main_window.py's do_restore()) calls
        # set_config() on this tab TWICE in immediate succession: once from
        # _apply_active_tab_configs()'s named-profile pass, once more from
        # the "All Tabs"/"Current Tab" session-recovery pass -- by design,
        # layering a saved profile then the last-live-session snapshot on
        # top. If the two configs' scan_directory differ (a real, common
        # case: whatever directory was active when the app last closed vs.
        # whatever the saved profile says), set_config()'s old
        # QTimer.singleShot(250, ...) scheduled a SEPARATE, independent
        # timer per call -- both landing within ~250ms of each other,
        # racing two full populate_scan_image_gallery() cycles back to
        # back. This is the actual, fully-automatic (no user interaction
        # needed) trigger for the deleteOrphaned/QSocketNotifier crash
        # class documented in
        # .agent/cache/gallery_crash_deleteorphaned_2026-07-27.md (see
        # Addendum 16) -- reproduced deterministically via plain `just
        # python` with zero manual browsing. A single, restartable timer
        # instead of fire-and-forget singleShot() ensures only the LATEST
        # set_config() call's directory ever actually restores, and only
        # once, no matter how many times set_config() fires in a burst.
        self._scan_dir_restore_timer = QTimer(self)
        self._scan_dir_restore_timer.setSingleShot(True)
        self._pending_restore_dir: Optional[str] = None
        self._scan_dir_restore_timer.timeout.connect(self._do_pending_scan_dir_restore)

        self.wallpaper_style: str = "Fill"
        self.video_style: str = "Scaled and Cropped"

        self._build_ui()

    def populate_monitor_layout(self):
        super().populate_monitor_layout()
        self.check_all_monitors_set()

    def cancel_loading(self):
        super().cancel_loading()

        stop_workers(
            getattr(self, "img_scanner_worker", None),
            getattr(self, "vid_scanner_worker", None),
            join=False,
        )

        if getattr(self, "_pagination_debounce_timer", None) is not None and self._pagination_debounce_timer.isActive():
            self._pagination_debounce_timer.stop()

        if self.slideshow_timer and self.slideshow_timer.isActive():
            self.slideshow_timer.stop()
        daemon_live = self._is_daemon_running_config()
        if self.countdown_timer and self.countdown_timer.isActive() and not daemon_live:
            self.countdown_timer.stop()

        close_windows(self, "open_queue_windows", "open_image_preview_windows")

        if daemon_live:
            self._start_daemon_countdown_if_active()
        else:
            self.monitor_current_index.clear()
            self.monitor_history.clear()
            self.time_remaining_sec = 0
            self.countdown_label.setText("Timer: --:--")

        self.unlock_ui_for_wallpaper()

    collect = _delegate("config_controller", "collect")
    get_default_config = _delegate("config_controller", "get_default_config")
    set_config = _delegate("config_controller", "set_config")
    _do_pending_scan_dir_restore = _delegate("config_controller", "_do_pending_scan_dir_restore")

    _start_daemon_countdown_if_active = _delegate("daemon_controller", "_start_daemon_countdown_if_active")
    _get_daemon_script_path = _delegate("daemon_controller", "_get_daemon_script_path")
    _daemon_config_running = _delegate("daemon_controller", "_daemon_config_running")
    _is_daemon_running_config = _delegate("daemon_controller", "_is_daemon_running_config")
    _is_background_daemon_process_alive = _delegate("daemon_controller", "_is_background_daemon_process_alive")
    _reconcile_daemon_liveness_on_startup = _delegate("daemon_controller", "_reconcile_daemon_liveness_on_startup")
    _record_daemon_pid = _delegate("daemon_controller", "_record_daemon_pid")
    _sync_daemon_config = _delegate("daemon_controller", "_sync_daemon_config")
    toggle_daemon = _delegate("daemon_controller", "toggle_daemon")
    view_daemon_logs = _delegate("daemon_controller", "view_daemon_logs")

    handle_set_wallpaper_click = _delegate("slideshow_controller", "handle_set_wallpaper_click")
    _compute_video_runtime_interval_sec = _delegate("slideshow_controller", "_compute_video_runtime_interval_sec")
    start_slideshow = _delegate("slideshow_controller", "start_slideshow")
    update_countdown = _delegate("slideshow_controller", "update_countdown")
    stop_slideshow = _delegate("slideshow_controller", "stop_slideshow")
    skip_current_wallpapers = _delegate("slideshow_controller", "skip_current_wallpapers")
    _cycle_slideshow_wallpaper = _delegate("slideshow_controller", "_cycle_slideshow_wallpaper")

    _get_relevant_styles = _delegate("style_selectors_controller", "_get_relevant_styles")
    _update_wallpaper_style = _delegate("style_selectors_controller", "_update_wallpaper_style")
    _update_video_style = _delegate("style_selectors_controller", "_update_video_style")
    _on_video_runtime_interval_toggled = _delegate("style_selectors_controller", "_on_video_runtime_interval_toggled")
    _update_background_type = _delegate("style_selectors_controller", "_update_background_type")
    select_solid_color = _delegate("style_selectors_controller", "select_solid_color")

    _build_ui = _delegate("ui_builder", "_build_ui")
    _build_background_type_row = _delegate("ui_builder", "_build_background_type_row")
    _build_slideshow_group = _delegate("ui_builder", "_build_slideshow_group")
    _build_solid_color_row = _delegate("ui_builder", "_build_solid_color_row")
    _build_style_selectors = _delegate("ui_builder", "_build_style_selectors")
    _build_scan_directory_row = _delegate("ui_builder", "_build_scan_directory_row")
    _build_gallery_section = _delegate("ui_builder", "_build_gallery_section")
    _build_action_row = _delegate("ui_builder", "_build_action_row")

    run_wallpaper_worker = _delegate("wallpaper_worker_controller", "run_wallpaper_worker")
    stop_wallpaper_worker = _delegate("wallpaper_worker_controller", "stop_wallpaper_worker")
    lock_ui_for_wallpaper = _delegate("wallpaper_worker_controller", "lock_ui_for_wallpaper")
    unlock_ui_for_wallpaper = _delegate("wallpaper_worker_controller", "unlock_ui_for_wallpaper")
    handle_wallpaper_status = _delegate("wallpaper_worker_controller", "handle_wallpaper_status")
    _handle_wallpaper_worker_finished = _delegate("wallpaper_worker_controller", "_handle_wallpaper_worker_finished")
    _process_wallpaper_finished = _delegate("wallpaper_worker_controller", "_process_wallpaper_finished")
    _apply_vault_slideshow_defaults = _delegate("wallpaper_worker_controller", "_apply_vault_slideshow_defaults")


__all__ = ["SystemDisplaySubTab"]
