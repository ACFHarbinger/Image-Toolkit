"""``SystemDisplaySubTab`` -- composed from per-concern mixins."""

from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import QTimer

from ..common.wallpaper_common_base import WallpaperCommonBase
from ._config import _ConfigMixin
from ._daemon import _DaemonMixin
from ._lifecycle import _LifecycleMixin
from ._slideshow import _SlideshowMixin
from ._style_selectors import _StyleSelectorsMixin
from ._ui_builder import _UIBuilderMixin
from ._wallpaper_worker import _WallpaperWorkerMixin


class SystemDisplaySubTab(
    # Mixins MUST precede WallpaperCommonBase in MRO order (see
    # gui/src/tabs/core/merge_tab/manager.py for the bug this pattern
    # fixes): _LifecycleMixin's populate_monitor_layout/cancel_loading and
    # _DaemonMixin's _is_daemon_running_config override same-named methods
    # WallpaperCommonBase (or its own AbstractClassSingleGallery ancestor)
    # already defines.
    _UIBuilderMixin,
    _DaemonMixin,
    _StyleSelectorsMixin,
    _SlideshowMixin,
    _LifecycleMixin,
    _WallpaperWorkerMixin,
    _ConfigMixin,
    WallpaperCommonBase,
):
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


__all__ = ["SystemDisplaySubTab"]
