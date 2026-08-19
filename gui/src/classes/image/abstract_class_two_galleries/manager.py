"""``AbstractClassTwoGalleries`` -- composed from per-concern mixins."""

from __future__ import annotations

import os
from typing import Dict, List, Optional, Set

from backend.src.constants import LOCAL_SOURCE_PATH
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QGridLayout, QLabel, QWidget

from ....components import MarqueeScrollArea
from ....utils.cache.lru_image_cache import LRUImageCache
from ...base.gallery_base import AbstractGalleryBase
from ._card_rendering import _CardRenderingMixin
from ._color_labels import _ColorLabelsMixin
from ._context_menu import _ContextMenuMixin
from ._found_gallery_load import _FoundGalleryLoadMixin
from ._found_gallery_populate import _FoundGalleryPopulateMixin
from ._keyboard_nav import _KeyboardNavMixin
from ._lifecycle import _LifecycleMixin
from ._navigation import _NavigationMixin
from ._pagination import _PaginationMixin
from ._selected_panel import _SelectedPanelMixin
from ._selection_ops import _SelectionOpsMixin
from ._sort_zoom import _SortZoomMixin


class AbstractClassTwoGalleries(
    # Mixins MUST precede AbstractGalleryBase in MRO order (see
    # gui/src/tabs/core/merge_tab/manager.py for the bug this pattern
    # fixes): _SortZoomMixin's _on_layout_change overrides a same-named
    # method AbstractGalleryBase itself defines.
    _NavigationMixin,
    _SortZoomMixin,
    _KeyboardNavMixin,
    _SelectionOpsMixin,
    _PaginationMixin,
    _ContextMenuMixin,
    _ColorLabelsMixin,
    _SelectedPanelMixin,
    _FoundGalleryLoadMixin,
    _FoundGalleryPopulateMixin,
    _CardRenderingMixin,
    _LifecycleMixin,
    AbstractGalleryBase,
):
    """Abstract base class for tabs with Found/Selected galleries.

    Lazy loading replaced with Sequential Loading: Images appear one by one.
    Includes Select All / Deselect All logic.
    Shared helpers (pagination, sort, dir history) are inherited from
    ``AbstractGalleryBase``.
    """

    def __init__(self):
        super().__init__()  # initialises shared state in AbstractGalleryBase

        # --- Data State ---
        self.found_files: List[str] = []
        self.selected_files: List[str] = []

        self.path_to_label_map: Dict[str, QWidget] = {}
        self.selected_card_map: Dict[str, QWidget] = {}
        self._selected_pixmap_cache = LRUImageCache(maxsize=200)
        self._found_pixmap_cache = LRUImageCache(maxsize=300)
        self.found_loading_paths: Set[str] = set()
        self._loading_paths: Set[str] = set()

        # --- Pagination State ---
        self.found_page_size = 100
        self.found_current_page = 0
        self.selected_page_size = 100
        self.selected_current_page = 0

        # --- Column counts (two-gallery-specific) ---
        self._current_found_cols = 1
        self._current_selected_cols = 1

        # --- UI References ---
        self.found_gallery_scroll: Optional[MarqueeScrollArea] = None
        self.found_gallery_layout: Optional[QGridLayout] = None
        self.selected_gallery_scroll: Optional[MarqueeScrollArea] = None
        self.selected_gallery_layout: Optional[QGridLayout] = None
        self.status_label: Optional[QLabel] = None

        # --- Population Timer (Sequential Loading) ---
        self._populate_found_timer = QTimer()
        self._populate_found_timer.setSingleShot(True)
        self._populate_found_timer.timeout.connect(self._populate_found_step)
        self._populating_found_index = 0

        try:
            self.last_browsed_dir = self._load_last_dir(LOCAL_SOURCE_PATH)
        except Exception:
            self.last_browsed_dir = os.getcwd()

        # --- Search State ---
        self.master_found_files: List[str] = []
        self.found_search_input = self.common_create_search_input(
            "Search found images..."
        )
        self.found_search_timer = QTimer()
        self.found_search_timer.setSingleShot(True)
        self.found_search_timer.setInterval(300)
        self.found_search_timer.timeout.connect(self._perform_found_search)
        self.found_search_input.textChanged.connect(self.found_search_timer.start)

        # Initialize Pagination Widgets using Shared Logic
        self.found_pagination_widget = self.create_pagination_controls(
            is_found_gallery=True
        )
        self.selected_pagination_widget = self.create_pagination_controls(
            is_found_gallery=False
        )

        # Enable keyboard focus for shortcuts
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)


__all__ = ["AbstractClassTwoGalleries"]
