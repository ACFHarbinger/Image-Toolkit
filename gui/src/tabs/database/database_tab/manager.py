"""``DatabaseTab`` -- composed from modular controllers and UI builders (§5.17, #544)."""

from __future__ import annotations

from typing import Optional

from backend.src.database.unified.facade import UnifiedImageDatabase as ImageDatabase
from PySide6.QtCore import Property, Signal
from PySide6.QtWidgets import QTableWidgetItem, QVBoxLayout, QWidget

from gui.src.modules.events import (
    DatabaseAvailabilityChanged,
    EventHub,
    GroupCatalogChanged,
    SubgroupCatalogChanged,
    TagCatalogChanged,
)
from gui.src.modules.library_service import LibraryDatabaseService

from ._auto_populate import DatabaseAutoPopulateController
from ._bulk_import import DatabaseBulkImportController
from ._config import DatabaseConfigController
from ._connection_stats import DatabaseConnectionController
from ._context_menus import DatabaseContextMenuController
from ._crud import DatabaseCrudController
from ._refresh_edit import DatabaseRefreshController
from ._ui_connection import build_connection_section
from ._ui_groups import build_groups_section
from ._ui_registry import build_registry_section
from ._ui_subgroups import build_subgroups_section
from ._ui_tags import build_tags_section
from .ui_builder import DatabaseUIBuilder


class DatabaseTab(QWidget):
    """
    Library management: statistics display and tag/group population on the
    unified library database (Phase DB, DB.6 — the PostgreSQL connection is
    gone; the store opens with the vault session).

    Phase 2 (ui-arch-23/#544): migrated off the 12-mixin inheritance cascade
    to composition over inheritance. DatabaseTab now inherits only from QWidget,
    eliminating MRO fragility and Qt virtual method shadowing hazards.
    """

    qml_stats_changed = Signal()

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

        # Composed Controllers (ui-arch-23, #544)
        self.connection_controller = DatabaseConnectionController(self)
        self.crud_controller = DatabaseCrudController(self)
        self.refresh_controller = DatabaseRefreshController(self)
        self.bulk_import_controller = DatabaseBulkImportController(self)
        self.auto_populate_controller = DatabaseAutoPopulateController(self)
        self.context_menu_controller = DatabaseContextMenuController(self)
        self.config_controller = DatabaseConfigController(self)

        # UI Section Construction via composed UI Builder
        self.ui_builder = DatabaseUIBuilder(self)
        main_layout = QVBoxLayout(self)
        self.ui_builder.build_ui(main_layout)

        self.update_button_states(connected=False)

        # Open automatically when the vault is already unlocked (it is, at
        # normal startup — the session was created at login/first use).
        if self.vault_manager is not None:
            self.connect_database(silent=True)

    # ------------------------------------------------------------------
    # QML Integration
    # ------------------------------------------------------------------

    @Property(str, notify=qml_stats_changed)
    def statsText(self):
        return self._stats_text

    # ------------------------------------------------------------------
    # EventHub Dispatch Helpers
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # UI Section Builder Adapters (Backwards-Compatibility)
    # ------------------------------------------------------------------

    def _build_connection_section(self, main_layout) -> None:
        build_connection_section(self, main_layout)

    def _build_groups_section(self, populate_layout) -> None:
        build_groups_section(self, populate_layout)

    def _build_subgroups_section(self, populate_layout) -> None:
        build_subgroups_section(self, populate_layout)

    def _build_tags_section(self, populate_layout) -> None:
        build_tags_section(self, populate_layout)

    def _build_registry_section(self, populate_layout) -> None:
        build_registry_section(self, populate_layout)

    # ------------------------------------------------------------------
    # Connection & Statistics Operations (delegated to connection_controller)
    # ------------------------------------------------------------------

    def connect_database(self, silent: bool = False) -> None:
        return self.connection_controller.connect_database(silent=silent)

    def reset_database(self) -> None:
        return self.connection_controller.reset_database()

    def update_statistics(self) -> None:
        return self.connection_controller.update_statistics()

    def run_vacuum(self) -> None:
        return self.connection_controller.run_vacuum()

    def run_reindex(self) -> None:
        return self.connection_controller.run_reindex()

    def run_embed_backfill(self) -> None:
        return self.connection_controller.run_embed_backfill()

    run_embedding_backfill = run_embed_backfill

    def update_button_states(self, connected: bool) -> None:
        return self.connection_controller.update_button_states(connected=connected)

    def _refresh_all_group_combos(self) -> None:
        return self.connection_controller._refresh_all_group_combos()

    def refresh_subgroup_autocomplete(self) -> None:
        return self.connection_controller.refresh_subgroup_autocomplete()

    def check_postgres_status(self) -> None:
        return self.connection_controller.check_postgres_status()

    def save_postgres_settings(self) -> None:
        return self.connection_controller.save_postgres_settings()

    def clear_postgres_password(self) -> None:
        return self.connection_controller.clear_postgres_password()

    # ------------------------------------------------------------------
    # CRUD Operations (delegated to crud_controller)
    # ------------------------------------------------------------------

    def create_new_group(self) -> None:
        return self.crud_controller.create_new_group()

    def create_new_subgroup(self) -> None:
        return self.crud_controller.create_new_subgroup()

    def create_new_tag(self) -> None:
        return self.crud_controller.create_new_tag()

    def remove_selected_group(self) -> None:
        return self.crud_controller.remove_selected_group()

    remove_selected_groups = remove_selected_group

    def remove_selected_subgroup(self) -> None:
        return self.crud_controller.remove_selected_subgroup()

    remove_selected_subgroups = remove_selected_subgroup

    def remove_selected_tag(self) -> None:
        return self.crud_controller.remove_selected_tag()

    remove_selected_tags = remove_selected_tag

    def merge_selected_tag(self) -> None:
        return self.crud_controller.merge_selected_tag()

    def search_images_with_selected_tag(self) -> None:
        return self.crud_controller.search_images_with_selected_tag()

    def search_listings_with_selected_tag(self) -> None:
        return self.crud_controller.search_listings_with_selected_tag()

    # ------------------------------------------------------------------
    # Refresh & Edit Handlers (delegated to refresh_controller)
    # ------------------------------------------------------------------

    def refresh_groups_list(self) -> None:
        return self.refresh_controller.refresh_groups_list()

    def refresh_subgroups_list(self) -> None:
        return self.refresh_controller.refresh_subgroups_list()

    def refresh_tags_list(self) -> None:
        return self.refresh_controller.refresh_tags_list()

    def refresh_image_registry(self) -> None:
        return self.refresh_controller.refresh_image_registry()

    def store_old_value(self, row: int, col: int) -> None:
        return self.refresh_controller.store_old_value(row, col)

    def handle_group_edited(self, item: QTableWidgetItem) -> None:
        return self.refresh_controller.handle_group_edited(item)

    def handle_subgroup_edited(self, item: QTableWidgetItem) -> None:
        return self.refresh_controller.handle_subgroup_edited(item)

    def handle_tag_edited(self, item: QTableWidgetItem) -> None:
        return self.refresh_controller.handle_tag_edited(item)

    def _apply_registry_filter(self, text: str) -> None:
        return self.refresh_controller._apply_registry_filter(text)

    def _show_registry_context_menu(self, pos) -> None:
        return self.refresh_controller._show_registry_context_menu(pos)

    # ------------------------------------------------------------------
    # Bulk Import Operations (delegated to bulk_import_controller)
    # ------------------------------------------------------------------

    def browse_json_file(self) -> None:
        return self.bulk_import_controller.browse_json_file()

    def import_tags_from_json(self) -> None:
        return self.bulk_import_controller.import_tags_from_json()

    # ------------------------------------------------------------------
    # Auto-Populate Operations (delegated to auto_populate_controller)
    # ------------------------------------------------------------------

    def auto_populate_from_source(self) -> None:
        return self.auto_populate_controller.auto_populate_from_source()

    # ------------------------------------------------------------------
    # Context Menu Operations (delegated to context_menu_controller)
    # ------------------------------------------------------------------

    def show_group_context_menu(self, pos) -> None:
        return self.context_menu_controller.show_group_context_menu(pos)

    def edit_selected_group_cell(self) -> None:
        return self.context_menu_controller.edit_selected_group_cell()

    def show_subgroup_context_menu(self, pos) -> None:
        return self.context_menu_controller.show_subgroup_context_menu(pos)

    def edit_selected_subgroup_cell(self) -> None:
        return self.context_menu_controller.edit_selected_subgroup_cell()

    def show_tag_context_menu(self, pos) -> None:
        return self.context_menu_controller.show_tag_context_menu(pos)

    def edit_selected_tag_cell(self) -> None:
        return self.context_menu_controller.edit_selected_tag_cell()

    # ------------------------------------------------------------------
    # Config Persistence (delegated to config_controller)
    # ------------------------------------------------------------------

    def collect(self) -> dict:
        return self.config_controller.collect()

    def get_default_config(self) -> dict:
        return self.config_controller.get_default_config()

    def set_config(self, config: dict) -> None:
        return self.config_controller.set_config(config)


__all__ = ["DatabaseTab"]
