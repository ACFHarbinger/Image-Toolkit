"""``SeriesListingsSubTab`` -- composed from per-concern mixins."""

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
from ._semantic_search import _SemanticSearchMixin
from ._ui_builder import _UIBuilderMixin


class SeriesListingsSubTab(
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
    _SemanticSearchMixin,
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

        # Semantic (BGE-M3) search state (DB.7)
        self._semantic_search_results: Optional[List[Tuple[str, float]]] = None
        self._active_semantic_worker = None
        self._active_embed_worker = None

        self._build_ui()

    # DB.8a/8c cross-tab navigation: MainWindow assigns this post-construction
    # (mirrors the existing search_tab_ref/merge_tab_ref pattern in
    # gui/src/windows/main/_tab_registry.py), and it's forwarded straight
    # through to the detail panel, which is what actually needs it (the
    # "View Images" jump lives on the detail panel's Linked Image Groups row).
    @property
    def main_window_ref(self):
        return self._detail.main_window_ref

    @main_window_ref.setter
    def main_window_ref(self, value):
        self._detail.main_window_ref = value


__all__ = ["SeriesListingsSubTab"]
