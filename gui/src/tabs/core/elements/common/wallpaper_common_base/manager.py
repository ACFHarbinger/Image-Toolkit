"""``WallpaperCommonBase`` -- composed from per-concern mixins."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.src.core.wallpaper import find_qdbus_binary
from PySide6.QtCore import QThread, QTimer, Signal
from screeninfo import Monitor

from ......classes import AbstractClassSingleGallery
from ......components import MonitorDropView
from ._event_filter import _EventFilterMixin
from ._gallery_label import _GalleryLabelMixin
from ._graph_drop import _GraphDropMixin
from ._image_preview_delete import _ImagePreviewDeleteMixin
from ._monitor_context import _MonitorContextMixin
from ._monitor_layout import _MonitorLayoutMixin
from ._monitor_selection import _MonitorSelectionMixin
from ._qml_handlers import _QmlHandlersMixin
from ._scan_actions import _ScanActionsMixin
from ._scan_pipeline import _ScanPipelineMixin
from ._scanner_lifecycle import _ScannerLifecycleMixin
from ._sync_overrides import _SyncOverridesMixin
from ._wallpaper_swap import _WallpaperSwapMixin
from ._widget_ui_lifecycle import _WidgetUiLifecycleMixin


class WallpaperCommonBase(
    # Mixins MUST precede AbstractClassSingleGallery in MRO order (see
    # gui/src/tabs/core/merge_tab/manager.py for the bug this pattern
    # fixes): several mixin methods here (_jump_to_page, _change_page,
    # _on_page_size_changed, _on_thumb_slider_changed, _on_sort_combo_changed,
    # _on_sort_dir_toggled, closeEvent, create_gallery_label,
    # update_card_style) override same-named methods AbstractClassSingle
    # Gallery itself defines. WallpaperCommonBase's own subclasses
    # (MonitorDisplaySubTab, SystemDisplaySubTab, etc.) are unaffected by
    # this internal composition -- Python's C3 linearization merges
    # WallpaperCommonBase's already-resolved MRO into theirs regardless of
    # how many pieces WallpaperCommonBase itself is built from.
    _MonitorSelectionMixin,
    _MonitorContextMixin,
    _ImagePreviewDeleteMixin,
    _GraphDropMixin,
    _WallpaperSwapMixin,
    _WidgetUiLifecycleMixin,
    _MonitorLayoutMixin,
    _GalleryLabelMixin,
    _ScannerLifecycleMixin,
    _ScanPipelineMixin,
    _EventFilterMixin,
    _ScanActionsMixin,
    _QmlHandlersMixin,
    _SyncOverridesMixin,
    AbstractClassSingleGallery,
):
    """Shared state and helpers for wallpaper subtabs.

    Holds monitor state, gallery helpers, and scanner methods.
    Subclasses build their own UI layouts using these facilities.
    """

    wallpapers_changed = Signal()
    monitors_updated = Signal(list)      # List[Monitor]
    qml_monitors_changed = Signal(list)  # List of dicts
    qml_status_changed = Signal(str)
    directory_scanned = Signal(str)

    # Sync signals
    sync_page_changed = Signal(int)
    sync_page_size_changed = Signal(str)
    sync_thumb_size_changed = Signal(int)
    sync_sort_combo_changed = Signal(str)
    sync_sort_dir_changed = Signal(bool)

    # Subclass-specific attributes used in shared methods
    slideshow_timer: Optional[QTimer]
    current_wallpaper_worker: Optional[Any]
    set_wallpaper_btn: Optional[Any]
    background_type_combo: Optional[Any]
    background_type: str
    solid_color_hex: str
    _graphs: Dict[str, Any]
    _monitor_display_ref: Optional[Any]
    _view: Any
    _scene: Any
    main_scroll_area: Optional[Any]
    scan_directory_path: Optional[Any]
    interval_min_spinbox: Optional[Any]
    style_combo: Optional[Any]

    def __init__(self):
        super().__init__()

        self.qdbus: Optional[str] = find_qdbus_binary()

        self.monitors: List[Monitor] = []
        self.monitor_widgets: Dict[str, MonitorDropView] = {}
        self.monitor_image_paths: Dict[str, Optional[str]] = {}
        self.monitor_slideshow_queues: Dict[str, List[str]] = {}
        self.monitor_current_index: Dict[str, int] = {}
        self.monitor_history: Dict[str, List[str]] = {}

        self.img_scanner_worker: Optional[Any] = None
        self.img_scanner_thread: Optional[QThread] = None

        self.scanned_dir = None
        self.path_to_label_map = {}
        self._filtering_event = False
        self._system_display_ref = None

        self._current_monitor_id = None
        self.linked_tabs = []
        self.open_image_preview_windows = []
        self.open_queue_windows = []

        # Common attributes used or overridden by subclasses
        self.slideshow_timer = None
        self.current_wallpaper_worker = None
        self.background_type = "Image"
        self.solid_color_hex = "#000000"

        self._pagination_debounce_timer = QTimer()
        self._pagination_debounce_timer.setSingleShot(True)
        self._pagination_debounce_timer.setInterval(200)
        self._pagination_debounce_timer.timeout.connect(self._update_pagination_ui)


__all__ = ["WallpaperCommonBase"]
