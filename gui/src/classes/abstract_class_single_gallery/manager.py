"""``AbstractClassSingleGallery`` -- composed from per-concern mixins."""

from __future__ import annotations

import os
from abc import abstractmethod
from typing import Dict, List, Optional

from backend.src.constants import LOCAL_SOURCE_PATH
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QGridLayout, QLabel, QScrollArea, QWidget

from ...utils.cache.lru_image_cache import LRUImageCache
from ..base.gallery_base import AbstractGalleryBase
from ._card_rendering import _CardRenderingMixin
from ._dir_history import _DirHistoryMixin
from ._disk_cache import _DiskCacheMixin
from ._geometry_events import _GeometryEventsMixin
from ._inline_actions import _InlineActionsMixin
from ._keyboard_nav import _KeyboardNavMixin
from ._lifecycle import _LifecycleMixin
from ._loading_pipeline import _LoadingPipelineMixin
from ._pagination import _PaginationMixin
from ._selection import _SelectionMixin
from ._sort_zoom import _SortZoomMixin


class AbstractClassSingleGallery(
    # Mixins MUST precede AbstractGalleryBase in MRO order (see
    # gui/src/tabs/core/merge_tab/manager.py for the bug this pattern
    # fixes): several mixin methods here (_on_layout_change) override a
    # same-named method AbstractGalleryBase itself defines, and closeEvent/
    # resizeEvent/showEvent/keyPressEvent override methods QWidget defines
    # (AbstractGalleryBase extends QWidget).
    _InlineActionsMixin,
    _DirHistoryMixin,
    _SortZoomMixin,
    _DiskCacheMixin,
    _KeyboardNavMixin,
    _SelectionMixin,
    _CardRenderingMixin,
    _PaginationMixin,
    _GeometryEventsMixin,
    _LoadingPipelineMixin,
    _LifecycleMixin,
    AbstractGalleryBase,
):
    """Abstract base class for a single gallery panel.

    Shared helpers (pagination, sort, dir history) are inherited from
    ``AbstractGalleryBase``.
    """

    def __init__(self):
        super().__init__()  # initialises shared state in AbstractGalleryBase

        # --- Data State ---
        self.gallery_image_paths: List[str] = []
        self.selected_files: List[str] = []
        self.path_to_card_widget: Dict[str, QWidget] = {}
        self._initial_pixmap_cache = LRUImageCache(maxsize=300)

        # --- Pagination State ---
        self.page_size = 100
        self.current_page = 0

        # --- Column count (single-gallery-specific) ---
        self._current_cols = 1

        # --- Population Timer ---
        self._populate_timer = QTimer()
        self._populate_timer.setSingleShot(True)
        self._populate_timer.timeout.connect(self._populate_step)
        self._paginated_paths: List[str] = []
        self._populating_index = 0

        # --- Keyboard Navigation (§2.3A) ---
        self._focused_idx: int = -1

        # --- UI References ---
        self.gallery_scroll_area: Optional[QScrollArea] = None
        self.gallery_layout: Optional[QGridLayout] = None

        # --- Lazy Loading State ---
        self._loading_paths = set()
        self._failed_paths = set()

        # Starting directory — restored from QSettings if available (GUI/UX §2.5)
        try:
            self.last_browsed_scan_dir = self._load_last_dir(LOCAL_SOURCE_PATH)
        except Exception:
            self.last_browsed_scan_dir = os.getcwd()

        # --- Search State ---
        self.master_image_paths: List[str] = []
        self.search_input = self.common_create_search_input()
        self.search_debounce_timer = QTimer()
        self.search_debounce_timer.setSingleShot(True)
        self.search_debounce_timer.setInterval(300)
        self.search_debounce_timer.timeout.connect(self._perform_search)
        self.search_input.textChanged.connect(self.search_debounce_timer.start)

        # Initialize Pagination Widgets using Shared Logic
        self.pagination_widget = self.create_pagination_controls()

        # Enable keyboard focus for shortcuts
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    # --- ABSTRACT METHODS ---

    @abstractmethod
    def create_gallery_label(self, path: str, size: int) -> QLabel:
        """Create the specific interactive label for a gallery item (subclass must implement)."""
        pass

    def on_selection_changed(self):
        """Optional hook for subclasses to react to selection changes."""
        pass


__all__ = ["AbstractClassSingleGallery"]
