"""Entity listings subtab — one half of the unified listings package (#563)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtCore import Signal

from gui.src.elements.database.display.common.listing_gallery_base import (
    ListingGalleryBase,
)

from ._backup_sync import _BackupSyncMixin
from ._entity_card_actions import _CardActionsMixin
from ._entity_directory_import import _DirectoryImportMixin
from ._entity_filters import _FiltersMixin
from ._entity_gallery import _GalleryMixin
from ._entity_persistence import _PersistenceMixin
from ._entity_semantic_search import _SemanticSearchMixin
from ._entity_ui_builder import _UIBuilderMixin
from .profile import ENTITY_PROFILE


class EntityListingsSubTab(
    _UIBuilderMixin,
    _PersistenceMixin,
    _GalleryMixin,
    _CardActionsMixin,
    _FiltersMixin,
    _SemanticSearchMixin,
    _BackupSyncMixin,
    _DirectoryImportMixin,
    ListingGalleryBase,
):
    listings_changed = Signal()

    def __init__(self, parent=None, vault_manager=None):
        super().__init__()
        if parent is not None:
            self.setParent(parent)
        self._listings_profile = ENTITY_PROFILE
        self.vault_manager = vault_manager
        self._entities: List[Dict[str, Any]] = []
        self._selected_id: Optional[str] = None
        self._filter_type = "All"
        self._filter_role = "All"
        self._search_query = ""
        self._listing_page = 0
        self._listing_page_size = 100
        self._semantic_search_results: Optional[List[Tuple[str, float]]] = None
        self._active_semantic_worker = None
        self._active_embed_worker = None
        self._build_ui()


__all__ = ["EntityListingsSubTab"]
