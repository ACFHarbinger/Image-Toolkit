"""``WallpaperCommonBase`` -- composed from per-concern mixins."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.src.core.wallpaper import find_qdbus_binary
from backend.src.constants import SUPPORTED_VIDEO_FORMATS
from PySide6.QtCore import QPointF, QThread, QTimer, Signal
from PySide6.QtWidgets import QApplication
from screeninfo import Monitor

from ......classes import AbstractClassSingleGallery
from ......components import MonitorDropView, VirtualGallery
from ......helpers import ImageLoaderWorker, VideoLoaderWorker
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
        self.vid_scanner_worker: Optional[Any] = None
        self.vid_scanner_thread: Optional[QThread] = None

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

    # ------------------------------------------------------------------
    # Virtual-scroll gallery surface (GUI/UX §2.1 Option A)
    # ------------------------------------------------------------------

    def _build_virtual_gallery(self):
        """Create the virtual-scroll gallery with wallpaper wiring (click to
        toggle, double-click to preview, right-click context menu, Ctrl+wheel
        zoom, and the custom drag-to-monitor). The scan pipeline that feeds it
        (and its serialization) is untouched."""
        def _gallery_worker(path: str, target_size: int):
            if path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS)):
                return VideoLoaderWorker(path, target_size)
            return ImageLoaderWorker(path, target_size)

        gallery = VirtualGallery(self, worker_factory=_gallery_worker)
        gallery.setMinimumHeight(600)
        gallery.path_clicked.connect(self.toggle_selection)
        gallery.path_activated.connect(self.handle_thumbnail_double_click)
        gallery.path_right_clicked.connect(self.show_image_context_menu)
        gallery.ctrl_wheel.connect(self._on_ctrl_wheel_zoom)
        gallery.view.set_custom_drag_enabled(True, self._on_gallery_drag_drop)
        return gallery

    def _on_gallery_drag_drop(self, source_path: str, selected_paths: list, drop_pos) -> None:
        """Resolve a gallery drag-drop (mirrors DraggableLabel._try_drop_on_widget):
        drop the file(s) on a MonitorDropView (set wallpaper) or the graph view
        (add a node)."""
        files_to_drop = selected_paths if source_path in selected_paths else [source_path]
        widget = QApplication.widgetAt(drop_pos)
        current = widget
        while current:
            if isinstance(current, MonitorDropView):
                current.handle_custom_drop(files_to_drop)
                return
            if current.__class__.__name__ == "WallpaperGraphView" or (
                hasattr(current, "scene") and hasattr(current, "mapToScene")
            ):
                view = current
                sc = view.scene()
                if sc is not None and hasattr(sc, "add_node"):
                    local_pos = view.viewport().mapFromGlobal(drop_pos)
                    scene_pos = view.mapToScene(local_pos)
                    for file_path in files_to_drop:
                        sc.add_node(file_path, scene_pos)
                        scene_pos = QPointF(scene_pos.x() + 160, scene_pos.y())
                    return
            current = current.parentWidget()

    def refresh_gallery_view(self):
        """Feed the filtered path list to the virtual gallery (no page slice /
        per-card populate). Overrides the base grid refresh. Falls back to the
        base grid path for subclasses/harnesses that don't build ``self.gallery``."""
        if not hasattr(self, "gallery"):
            super().refresh_gallery_view()  # type: ignore[safe-super]
            return
        self.cancel_loading()
        self.clear_gallery_widgets()
        paths = self.gallery_image_paths
        if not paths:
            return
        self.gallery.set_paths(paths)

    def clear_gallery_widgets(self):
        """Clear the virtual gallery and cancel its in-flight loads."""
        if hasattr(self, "gallery"):
            self.gallery.clear()
            self.cancel_loading()
        else:
            super().clear_gallery_widgets()  # type: ignore[safe-super]

    def cancel_loading(self):
        super().cancel_loading()  # type: ignore[safe-super]
        if hasattr(self, "gallery"):
            self.gallery.cancel_loading()

    def _on_layout_change(self):
        """Virtual gallery re-lays-out itself; nothing to reflow."""

    def _on_ctrl_wheel_zoom(self, delta: int):
        """Ctrl+wheel thumbnail zoom (§2.2) over the virtual gallery."""
        step = 16 if delta > 0 else -16
        new_size = max(64, min(512, self.thumbnail_size + step))
        if new_size == self.thumbnail_size:
            return
        self.thumbnail_size = new_size
        self.approx_item_width = new_size + self.padding_width + 20
        self._save_thumbnail_size()
        if hasattr(self, "gallery"):
            self.gallery.set_thumbnail_size(new_size)


__all__ = ["WallpaperCommonBase"]
