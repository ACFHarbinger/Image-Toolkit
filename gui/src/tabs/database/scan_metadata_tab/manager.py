"""``ScanMetadataTab`` -- composed from per-concern mixins."""

from __future__ import annotations

from typing import List, Optional, Set, Tuple

from PySide6.QtCore import QThreadPool, QTimer
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QWidget

from ....classes import AbstractClassTwoGalleries
from ....helpers import UpsertWorker
from ._auto_listings import _AutoListingsMixin
from ._config import _ConfigMixin
from ._context_menu_actions import _ContextMenuActionsMixin
from ._gallery_cards import _GalleryCardsMixin
from ._keyboard_selection import _KeyboardSelectionMixin
from ._layout_reflow import _LayoutReflowMixin
from ._lazy_loading import _LazyLoadingMixin
from ._pagination import _PaginationMixin
from ._scan_loading import _ScanLoadingMixin
from ._selection_gallery import _SelectionGalleryMixin
from ._ui_builder import _UIBuilderMixin
from ._upsert_ops import _UpsertOpsMixin
from ._view_toggles import _ViewTogglesMixin


class ScanMetadataTab(
    # Mixins MUST precede AbstractClassTwoGalleries in MRO order (see
    # gui/src/tabs/core/merge_tab/manager.py for the bug this pattern fixes):
    # several mixin methods here (_update_pagination_ui, cancel_loading,
    # create_card_widget, handle_marquee_selection, keyPressEvent,
    # on_selection_changed, resizeEvent, toggle_selection, update_card_pixmap)
    # override same-named methods AbstractClassTwoGalleries itself defines.
    _UIBuilderMixin,
    _PaginationMixin,
    _KeyboardSelectionMixin,
    _LayoutReflowMixin,
    _GalleryCardsMixin,
    _SelectionGalleryMixin,
    _ScanLoadingMixin,
    _LazyLoadingMixin,
    _ViewTogglesMixin,
    _ContextMenuActionsMixin,
    _UpsertOpsMixin,
    _AutoListingsMixin,
    _ConfigMixin,
    AbstractClassTwoGalleries,
):
    """
    Manages file and directory metadata scanning, image preview gallery, and batch database operations.
    """

    def __init__(self, db_tab_ref):
        super().__init__()
        self.db_tab_ref = db_tab_ref

        self.scan_image_list: list[str] = []
        # Holds the list currently being viewed (filtered by "New Only" or "In DB Only" if active)
        self.scan_filtered_list: list[str] = []

        self.selected_image_paths: Set[str] = set()
        # Manual display/drag-reorder order for the Selected gallery, kept
        # separate from the set above since most of this tab's selection
        # code (context menu actions, keyboard select-all, marquee) mutates
        # `selected_image_paths` directly as a plain set. Self-healing: any
        # member missing from this list is appended in populate_selected_images_gallery.
        self._selected_order: list[str] = []
        self.open_preview_windows: list[QWidget] = []

        # Database view filter state
        self.view_new_only: bool = False
        self.view_in_db_only: bool = False
        self._db_was_connected: bool = False

        # Cancellation flag
        self._loading_cancelled = False

        # Gallery Constants
        self.thumbnail_size = 180
        self.padding_width = 10
        self.approx_item_width = self.thumbnail_size + self.padding_width + 20

        # Pagination State
        self.scan_page_size = 100
        self.scan_current_page = 0
        self.scan_total_pages = 1

        self.selected_page_size = 100
        self.selected_current_page = 0
        self.selected_total_pages = 1

        # Threading references
        self.scan_thread = None
        self.scan_worker = None
        self.current_upsert_worker: Optional[UpsertWorker] = None

        # ThreadPool for image loading
        self.thread_pool = QThreadPool()
        # accumulators for threading results
        self._loaded_results_buffer: List[Tuple[str, QImage]] = []
        self._images_loaded_count = 0
        self._total_images_to_load = 0

        # --- Resize Handling ---
        self._resize_timer = QTimer()
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._repack_galleries)

        # --- Lazy Loading State ---
        self.loaded_paths: Set[str] = set()
        self.loading_paths: Set[str] = set()
        self._lazy_load_timer = QTimer()
        self._lazy_load_timer.setSingleShot(True)
        self._lazy_load_timer.setInterval(150)  # Wait 150ms after scroll stops
        self._lazy_load_timer.timeout.connect(self._process_visible_items)

        self._build_ui()


__all__ = ["ScanMetadataTab"]
