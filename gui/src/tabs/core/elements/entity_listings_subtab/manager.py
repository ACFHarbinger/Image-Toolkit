"""``EntityListingsSubTab`` -- composed from per-concern mixins."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget

from ._backup_sync import _BackupSyncMixin
from ._card_actions import _CardActionsMixin
from ._directory_import import _DirectoryImportMixin
from ._filters import _FiltersMixin
from ._gallery import _GalleryMixin
from ._persistence import _PersistenceMixin
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

        self._build_ui()


__all__ = ["EntityListingsSubTab"]
