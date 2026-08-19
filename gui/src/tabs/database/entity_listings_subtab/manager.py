"""``EntityListingsSubTab`` -- composed from per-concern mixins."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget

from ._backup_sync import _BackupSyncMixin
from ._card_actions import _CardActionsMixin
from ._directory_import import _DirectoryImportMixin
from ._filters import _FiltersMixin
from ._gallery import _GalleryMixin
from ._persistence import _PersistenceMixin
from ._semantic_search import _SemanticSearchMixin
from ._ui_builder import _UIBuilderMixin


class EntityListingsSubTab(
    # Mixins MUST precede QWidget in MRO order (see gui/src/tabs/core/
    # merge_tab/manager.py for the bug this pattern fixes): _GalleryMixin's
    # resizeEvent/showEvent override methods QWidget itself defines.
    _UIBuilderMixin,
    _PersistenceMixin,
    _GalleryMixin,
    _CardActionsMixin,
    _FiltersMixin,
    _SemanticSearchMixin,
    _BackupSyncMixin,
    _DirectoryImportMixin,
    QWidget,
):
    listings_changed = Signal()  # emitted when listings.json is updated by cross-sync

    def __init__(self, parent=None, vault_manager=None):
        super().__init__(parent)
        self.vault_manager = vault_manager
        self._entities: List[Dict[str, Any]] = []
        self._selected_id: Optional[str] = None
        self._filter_type = "All"
        self._filter_role = "All"
        self._search_query = ""
        self._listing_page = 0
        self._listing_page_size = 100

        # Semantic (BGE-M3) search state (DB.7)
        self._semantic_search_results: Optional[List[Tuple[str, float]]] = None
        self._active_semantic_worker = None
        self._active_embed_worker = None

        self._build_ui()


__all__ = ["EntityListingsSubTab"]
