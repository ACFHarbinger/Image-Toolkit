"""``SearchTab`` -- composed from per-concern mixins."""

from __future__ import annotations

from typing import Dict, List, Optional

from PySide6.QtCore import Signal

from gui.src.helpers import SearchWorker
from gui.src.modules.events import (
    DatabaseAvailabilityChanged,
    EventHub,
    FilterByTagIntent,
    GroupCatalogChanged,
    SubgroupCatalogChanged,
    TagCatalogChanged,
)
from gui.src.modules.library_service import coerce_library_database_service

from ....classes import AbstractClassTwoGalleries
from ._config import _ConfigMixin
from ._file_actions import _FileActionsMixin
from ._format_filters import _FormatFiltersMixin
from ._gallery_cards import _GalleryCardsMixin
from ._group_filters import _GroupFiltersMixin
from ._lifecycle import _LifecycleMixin
from ._qml_wrappers import _QmlWrappersMixin
from ._search_worker import _SearchWorkerMixin
from ._semantic_search import _SemanticSearchMixin
from ._tab_communication import _TabCommunicationMixin
from ._tag_filters import _TagFiltersMixin
from ._ui_builder import _UIBuilderMixin


class SearchTab(
    # Mixins MUST precede AbstractClassTwoGalleries in MRO order (see
    # gui/src/tabs/core/merge_tab/manager.py for the bug this pattern
    # fixes): several mixin methods here (_update_found_card_styles,
    # cancel_loading, closeEvent, create_card_widget, get_default_config,
    # on_selection_changed, set_config, update_card_pixmap) override
    # same-named methods AbstractClassTwoGalleries itself defines.
    _UIBuilderMixin,
    _GalleryCardsMixin,
    _SearchWorkerMixin,
    _SemanticSearchMixin,
    _QmlWrappersMixin,
    _FormatFiltersMixin,
    _TagFiltersMixin,
    _GroupFiltersMixin,
    _TabCommunicationMixin,
    _FileActionsMixin,
    _ConfigMixin,
    _LifecycleMixin,
    AbstractClassTwoGalleries,
):
    # Signal to send image to another tab: (target_tab_name, image_path)
    send_to_tab_signal = Signal(str, str)

    def __init__(self, database_service=None, event_hub: EventHub | None = None, dropdown=True, **legacy):
        # Initialize Base Class (Two Galleries)
        super().__init__()

        self.database_service = coerce_library_database_service(
            database_service if database_service is not None else legacy.pop("db_tab_ref", None)
        )
        self.event_hub = event_hub or EventHub(self)
        self.dropdown = dropdown

        self.open_preview_windows = []
        self.selected_formats = None
        self._db_was_connected = False

        # Search specific worker
        self.current_search_worker: Optional[SearchWorker] = None
        # Tag cache (populated on DB connect)
        self._all_tags_cache: List[Dict] = []

        self._build_ui()
        self.event_hub.subscribe(FilterByTagIntent, self._on_filter_by_tag, owner=self)
        self.event_hub.subscribe(TagCatalogChanged, self._on_tag_catalog_changed, owner=self)
        self.event_hub.subscribe(GroupCatalogChanged, self._on_group_catalog_changed, owner=self)
        self.event_hub.subscribe(SubgroupCatalogChanged, self._on_subgroup_catalog_changed, owner=self)
        self.event_hub.subscribe(DatabaseAvailabilityChanged, self._on_database_availability_changed, owner=self)

    def _on_filter_by_tag(self, intent: FilterByTagIntent) -> None:
        if intent.module_id == "library.search":
            self.search_by_tag(intent.tag_name)

    def _on_tag_catalog_changed(self, _event: TagCatalogChanged) -> None:
        self._setup_tag_checkboxes()

    def _on_group_catalog_changed(self, event: GroupCatalogChanged) -> None:
        self.populate_groups_list(list(event.groups))

    def _on_subgroup_catalog_changed(self, event: SubgroupCatalogChanged) -> None:
        self.populate_subgroups_detailed(list(event.subgroups))

    def _on_database_availability_changed(self, event: DatabaseAvailabilityChanged) -> None:
        self.update_search_button_state(event.connected)


__all__ = ["SearchTab"]
