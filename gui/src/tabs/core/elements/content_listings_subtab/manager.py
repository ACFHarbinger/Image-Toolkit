"""``ContentListingsSubTab`` -- composed from per-concern mixins."""

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
from ._recommendation import _RecommendationMixin
from ._ui_builder import _UIBuilderMixin


class ContentListingsSubTab(
    # Mixins MUST precede QWidget in MRO order (see gui/src/tabs/core/
    # merge_tab/manager.py for the bug this pattern fixes): _GalleryMixin's
    # resizeEvent/showEvent override methods QWidget itself defines, and
    # would otherwise be silently shadowed.
    _UIBuilderMixin,
    _PersistenceMixin,
    _GalleryMixin,
    _CardActionsMixin,
    _FiltersMixin,
    _RecommendationMixin,
    _BackupSyncMixin,
    _DirectoryImportMixin,
    QWidget,
):
    entities_changed = Signal()  # emitted when entities.json is updated by cross-sync

    def __init__(self, parent=None, vault_manager=None):
        super().__init__(parent)
        self.vault_manager = vault_manager
        self._entries: List[Dict[str, Any]] = []
        self._selected_id: Optional[str] = None
        self._filter_type = "All"
        self._filter_status = "All"
        self._search_query = ""
        self._advanced_search_criteria = None

        # Vector search state
        self._recommendation_results: Optional[List[Tuple[str, float]]] = None
        self._active_rec_worker = None

        self._build_ui()


__all__ = ["ContentListingsSubTab"]
