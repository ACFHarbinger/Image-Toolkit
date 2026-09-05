"""``DatabaseTab`` -- composed from per-concern mixins."""

from __future__ import annotations

from typing import Optional

from backend.src.database.unified.facade import UnifiedImageDatabase as ImageDatabase
from PySide6.QtCore import Property, Signal
from PySide6.QtWidgets import QGroupBox, QScrollArea, QVBoxLayout, QWidget

from gui.src.modules.events import (
    DatabaseAvailabilityChanged,
    EventHub,
    GroupCatalogChanged,
    SubgroupCatalogChanged,
    TagCatalogChanged,
)
from gui.src.modules.library_service import LibraryDatabaseService

from ._auto_populate import _AutoPopulateMixin
from ._bulk_import import _BulkImportMixin
from ._config import _ConfigMixin
from ._connection_stats import _ConnectionStatsMixin
from ._context_menus import _ContextMenusMixin
from ._crud import _CrudMixin
from ._refresh_edit import _RefreshEditMixin
from ._ui_connection import _UIConnectionMixin
from ._ui_groups import _UIGroupsMixin
from ._ui_registry import _UIRegistryMixin
from ._ui_subgroups import _UISubgroupsMixin
from ._ui_tags import _UITagsMixin


class DatabaseTab(
    QWidget,
    _UIConnectionMixin,
    _UIGroupsMixin,
    _UISubgroupsMixin,
    _UITagsMixin,
    _UIRegistryMixin,
    _ConnectionStatsMixin,
    _BulkImportMixin,
    _CrudMixin,
    _RefreshEditMixin,
    _ContextMenusMixin,
    _ConfigMixin,
    _AutoPopulateMixin,
):
    """
    Library management: statistics display and tag/group population on the
    unified library database (Phase DB, DB.6 — the PostgreSQL connection is
    gone; the store opens with the vault session).
    """

    def __init__(
        self,
        vault_manager=None,
        *,
        database_service: LibraryDatabaseService | None = None,
        event_hub: EventHub | None = None,
    ):
        super().__init__()
        self.vault_manager = vault_manager
        self.database_service = database_service or LibraryDatabaseService(vault_manager)
        self.event_hub = event_hub
        self.db: Optional[ImageDatabase] = self.database_service.db
        self._stats_text = "Not Connected"
        self.embedding_worker = None

        self.old_edit_value = None

        main_layout = QVBoxLayout(self)

        self._build_connection_section(main_layout)

        self.populate_group = QGroupBox("Populate Database")
        populate_layout = QVBoxLayout(self.populate_group)

        self._build_groups_section(populate_layout)
        self._build_subgroups_section(populate_layout)
        self._build_tags_section(populate_layout)
        self._build_registry_section(populate_layout)

        populate_scroll_area = QScrollArea()
        populate_scroll_area.setWidgetResizable(True)
        populate_scroll_area.setWidget(self.populate_group)
        populate_scroll_area.setStyleSheet("QScrollArea { border: none; }")

        main_layout.addWidget(populate_scroll_area)

        self.update_button_states(connected=False)

        # Open automatically when the vault is already unlocked (it is, at
        # normal startup — the session was created at login/first use).
        if self.vault_manager is not None:
            self.connect_database(silent=True)

    # --- QML Integration ---
    qml_stats_changed = Signal()

    @Property(str, notify=qml_stats_changed)
    def statsText(self):
        return self._stats_text

    def _publish_database_availability(self, connected: bool) -> None:
        if self.event_hub is not None:
            self.event_hub.publish(
                DatabaseAvailabilityChanged(origin="library.management", connected=connected)
            )

    def _publish_tag_catalog_changed(self) -> None:
        if self.event_hub is not None:
            self.event_hub.publish(TagCatalogChanged(origin="library.management"))

    def _publish_group_catalog_changed(self, groups: list[str]) -> None:
        if self.event_hub is not None:
            self.event_hub.publish(
                GroupCatalogChanged(origin="library.management", groups=tuple(groups))
            )

    def _publish_subgroup_catalog_changed(self, subgroups: list[tuple[str, str]]) -> None:
        if self.event_hub is not None:
            self.event_hub.publish(
                SubgroupCatalogChanged(origin="library.management", subgroups=tuple(subgroups))
            )


__all__ = ["DatabaseTab"]
