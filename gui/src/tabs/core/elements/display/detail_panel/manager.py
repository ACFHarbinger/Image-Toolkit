"""``_DetailPanel`` -- composed from per-concern mixins."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from gui.src.tabs.core.elements.display.common.base_detail_panel import BaseDetailPanel
from PySide6.QtCore import Signal

from ._associated_entities import _AssociatedEntitiesMixin
from ._entry_lifecycle import _EntryLifecycleMixin
from ._episode_list import _EpisodeListMixin
from ._file_link_actions import _FileLinkActionsMixin
from ._image_actions import _ImageActionsMixin
from ._mal_sync import _MalSyncMixin
from ._save_delete import _SaveDeleteMixin
from ._ui_builder import _UIBuilderMixin


class _DetailPanel(
    _UIBuilderMixin,
    _ImageActionsMixin,
    _AssociatedEntitiesMixin,
    _EntryLifecycleMixin,
    _FileLinkActionsMixin,
    _MalSyncMixin,
    _EpisodeListMixin,
    _SaveDeleteMixin,
    BaseDetailPanel,
):
    saved = Signal(dict)
    deleted = Signal(str)

    def __init__(self, parent=None, vault_manager=None):
        super().__init__(parent)
        self.vault_manager = vault_manager
        self._entry_id: Optional[str] = None
        self._episode_data: List[Dict[str, Any]] = []
        self._mal_worker = None

        self._build_ui()


__all__ = ["_DetailPanel"]
