"""``SearchTab`` -- composed controllers over ``AbstractClassTwoGalleries`` (#544)."""

from __future__ import annotations

import contextlib
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QPoint, Signal
from PySide6.QtWidgets import QLabel, QWidget

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
from ._config import SearchConfigController
from ._file_actions import SearchFileActionsController
from ._format_filters import SearchFormatFiltersController
from ._gallery_cards import SearchGalleryCardsController
from ._group_filters import SearchGroupFiltersController
from ._qml_wrappers import SearchQmlController
from ._search_worker import SearchWorkerController
from ._semantic_search import SearchSemanticController
from ._tab_communication import SearchTabCommunicationController
from ._tag_filters import SearchTagFiltersController
from ._ui_builder import SearchUIBuilder


class SearchTab(AbstractClassTwoGalleries):
    """Library search: structured filters plus semantic search.

    Phase 2 (ui-arch-23/#544): mixins collapsed into composed controllers.
    Gallery inheritance stays -- this tab owns two virtual galleries.
    """

    send_to_tab_signal = Signal(str, str)

    def __init__(self, database_service=None, event_hub: EventHub | None = None, dropdown=True, **legacy):
        super().__init__()

        self.database_service = coerce_library_database_service(
            database_service if database_service is not None else legacy.pop("db_tab_ref", None)
        )
        self.event_hub = event_hub or EventHub(self)
        self.dropdown = dropdown

        self.open_preview_windows = []
        self.selected_formats = None
        self._db_was_connected = False
        self.current_search_worker: Optional[SearchWorker] = None
        self._all_tags_cache: List[Dict] = []

        self.ui_builder = SearchUIBuilder(self)
        self.gallery_cards = SearchGalleryCardsController(self)
        self.search_worker = SearchWorkerController(self)
        self.semantic = SearchSemanticController(self)
        self.qml = SearchQmlController(self)
        self.format_filters = SearchFormatFiltersController(self)
        self.tag_filters = SearchTagFiltersController(self)
        self.group_filters = SearchGroupFiltersController(self)
        self.tab_communication = SearchTabCommunicationController(self)
        self.file_actions = SearchFileActionsController(self)
        self.config_controller = SearchConfigController(self)

        self.ui_builder._build_ui()
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

    def cancel_loading(self):
        super().cancel_loading()
        if hasattr(self, "dual"):
            self.dual.cancel_loading()
        if self.current_search_worker:
            self.current_search_worker.cancel()
        for win in list(self.open_preview_windows):
            with contextlib.suppress(Exception):
                win.close()
        self.open_preview_windows.clear()

    def closeEvent(self, event):
        self.cancel_loading()
        super().closeEvent(event)

    def create_gallery_label(self, path: str, size: int) -> QLabel:
        return self.gallery_cards.create_gallery_label(path, size)

    def _sync_selection_from_dual(self):
        return self.gallery_cards._sync_selection_from_dual()

    def refresh_found_gallery(self):
        return self.gallery_cards.refresh_found_gallery()

    def refresh_selected_panel(self):
        return self.gallery_cards.refresh_selected_panel()

    def toggle_selection(self, path: str):
        return self.gallery_cards.toggle_selection(path)

    def clear_galleries(self, clear_data=True):
        return self.gallery_cards.clear_galleries(clear_data=clear_data)

    def select_all_results(self):
        return self.gallery_cards.select_all_results()

    def deselect_all_results(self):
        return self.gallery_cards.deselect_all_results()

    def toggle_search(self):
        return self.search_worker.toggle_search()

    def perform_search(self):
        return self.search_worker.perform_search()

    def on_search_finished(self, matching_files: list):
        return self.search_worker.on_search_finished(matching_files)

    def on_search_error(self, error_msg: str):
        return self.search_worker.on_search_error(error_msg)

    def on_search_cancelled(self):
        return self.search_worker.on_search_cancelled()

    def cancel_search(self):
        return self.search_worker.cancel_search()

    def _reset_search_ui(self, message: str):
        return self.search_worker._reset_search_ui(message)

    def _build_semantic_search_section(self, layout) -> None:
        return self.semantic._build_semantic_search_section(layout)

    def perform_semantic_search(self):
        return self.semantic.perform_semantic_search()

    def find_similar_images(self, file_path: str) -> None:
        return self.semantic.find_similar_images(file_path)

    def execute_search(self):
        return self.qml.execute_search()

    def clear_filters(self):
        return self.qml.clear_filters()

    def display_results(self, results: List[Dict[str, Any]]):
        return self.qml.display_results(results)

    def clear_search_data(self):
        return self.qml.clear_search_data()

    def toggle_format(self, fmt, checked):
        return self.format_filters.toggle_format(fmt, checked)

    def add_all_formats(self):
        return self.format_filters.add_all_formats()

    def remove_all_formats(self):
        return self.format_filters.remove_all_formats()

    def get_selected_formats(self) -> Optional[List[str]]:
        return self.format_filters.get_selected_formats()

    def _setup_tag_checkboxes(self):
        return self.tag_filters._setup_tag_checkboxes()

    def get_selected_tags(self) -> List[str]:
        return self.tag_filters.get_selected_tags()

    def search_by_tag(self, tag_name: str) -> None:
        return self.tag_filters.search_by_tag(tag_name)

    def _on_group_selection_changed(self):
        return self.group_filters._on_group_selection_changed()

    def _on_tag_type_changed(self):
        return self.tag_filters._on_tag_type_changed()

    def _on_semantic_search_finished(self, hits: list) -> None:
        return self.semantic._on_semantic_search_finished(hits)

    def _on_semantic_search_error(self, message: str) -> None:
        return self.semantic._on_semantic_search_error(message)

    def _on_semantic_search_cancelled(self) -> None:
        return self.semantic._on_semantic_search_cancelled()

    def _refresh_groups_from_db(self):
        return self.group_filters._refresh_groups_from_db()

    def populate_groups_list(self, group_list: List[str]):
        return self.group_filters.populate_groups_list(group_list)

    def populate_subgroups_detailed(self, detailed: List[tuple]):
        return self.group_filters.populate_subgroups_detailed(detailed)

    def get_selected_groups(self) -> List[str]:
        return self.group_filters.get_selected_groups()

    def get_selected_subgroups(self) -> List[str]:
        return self.group_filters.get_selected_subgroups()

    def filter_by_group(self, group_name: str) -> None:
        return self.group_filters.filter_by_group(group_name)

    def update_search_button_state(self, connected: Optional[bool] = None):
        return self.group_filters.update_search_button_state(connected=connected)

    def send_selection_to_scan_tab(self):
        return self.tab_communication.send_selection_to_scan_tab()

    def send_selection_to_merge_tab(self, single_path=None):
        return self.tab_communication.send_selection_to_merge_tab(single_path)

    def send_selection_to_delete_tab(self, single_path=None):
        return self.tab_communication.send_selection_to_delete_tab(single_path)

    def send_selection_to_wallpaper_tab(self, single_path=None):
        return self.tab_communication.send_selection_to_wallpaper_tab(single_path)

    def handle_remove_from_db(self, file_path: str):
        return self.file_actions.handle_remove_from_db(file_path)

    def handle_delete_image(self, file_path: str):
        return self.file_actions.handle_delete_image(file_path)

    def show_image_properties(self, file_path: str):
        return self.file_actions.show_image_properties(file_path)

    def show_context_menu(self, pos: QPoint, file_path: str, widget: QWidget):
        return self.file_actions.show_context_menu(pos, file_path, widget)

    def open_file_preview(self, file_path: str):
        return self.file_actions.open_file_preview(file_path)

    def open_file_directory(self, file_path: str):
        return self.file_actions.open_file_directory(file_path)

    def collect(self) -> Dict[str, Any]:
        return self.config_controller.collect()

    def get_default_config(self) -> Dict[str, Any]:
        return self.config_controller.get_default_config()

    def set_config(self, config: Dict[str, Any]):
        return self.config_controller.set_config(config)


__all__ = ["SearchTab"]
