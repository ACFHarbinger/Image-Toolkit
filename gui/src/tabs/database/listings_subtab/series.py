"""Series listings subtab — one half of the unified listings package (#563)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtCore import Signal

from gui.src.elements.database.display.common.listing_gallery_base import (
    ListingGalleryBase,
)

from ._backup_sync import _BackupSyncMixin
from ._series_card_actions import _CardActionsMixin
from ._series_directory_import import _DirectoryImportMixin
from ._series_filters import _FiltersMixin
from ._series_gallery import _GalleryMixin
from ._series_persistence import _PersistenceMixin
from ._series_recommendation import _RecommendationMixin
from ._series_semantic_search import _SemanticSearchMixin
from ._series_ui_builder import _UIBuilderMixin
from .profile import SERIES_PROFILE


class SeriesListingsSubTab(
    _UIBuilderMixin,
    _PersistenceMixin,
    _GalleryMixin,
    _CardActionsMixin,
    _RecommendationMixin,
    _FiltersMixin,
    _SemanticSearchMixin,
    _BackupSyncMixin,
    _DirectoryImportMixin,
    ListingGalleryBase,
):
    entities_changed = Signal()

    def __init__(self, parent=None, vault_manager=None):
        super().__init__()
        if parent is not None:
            self.setParent(parent)
        self._listings_profile = SERIES_PROFILE
        self.vault_manager = vault_manager
        self._entries: List[Dict[str, Any]] = []
        self._selected_id: Optional[str] = None
        self._filter_type = "All"
        self._filter_status = "All"
        self._search_query = ""
        self._advanced_search_criteria = None
        self._listing_page = 0
        self._listing_page_size = 100
        self._recommendation_results: Optional[List[Tuple[str, float]]] = None
        self._active_rec_worker = None
        self._semantic_search_results: Optional[List[Tuple[str, float]]] = None
        self._active_semantic_worker = None
        self._active_embed_worker = None
        self._build_ui()


__all__ = ["SeriesListingsSubTab"]
