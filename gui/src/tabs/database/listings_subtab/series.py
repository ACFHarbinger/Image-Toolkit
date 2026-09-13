"""Series listings subtab — composed controllers over ``ListingGalleryBase`` (#544)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtCore import Signal

from gui.src.elements.database.display.common.listing_gallery_base import (
    ListingGalleryBase,
)

from ._backup_sync import ListingsBackupSyncController
from ._series_card_actions import SeriesListingsCardActionsController
from ._series_directory_import import SeriesListingsDirectoryImportController
from ._series_filters import SeriesListingsFiltersController
from ._series_gallery import SeriesListingsGalleryController
from ._series_persistence import SeriesListingsPersistenceController
from ._series_recommendation import SeriesListingsRecommendationController
from ._series_semantic_search import SeriesListingsSemanticController
from ._series_ui_builder import SeriesListingsUIBuilder
from .profile import SERIES_PROFILE


class SeriesListingsSubTab(ListingGalleryBase):
    """Series/content record-card gallery.

    Phase 2 (ui-arch-23/#544): mixins collapsed into composed controllers.
    Gallery inheritance stays — this tab owns a listing card grid.
    """

    entities_changed = Signal()

    def __init__(self, parent=None, vault_manager=None):
        super().__init__()
        if parent is not None:
            self.setParent(parent)
        self._listings_profile = SERIES_PROFILE
        self.vault_manager = vault_manager
        self._entries: List[Dict[str, Any]] = []
        self._selected_id: Optional[str] = None
        self._filter_type = "All"
        self._filter_status = "All"
        self._search_query = ""
        self._advanced_search_criteria = None
        self._listing_page = 0
        self._listing_page_size = 100
        self._recommendation_results: Optional[List[Tuple[str, float]]] = None
        self._active_rec_worker = None
        self._semantic_search_results: Optional[List[Tuple[str, float]]] = None
        self._active_semantic_worker = None
        self._active_embed_worker = None

        self.ui_builder = SeriesListingsUIBuilder(self)
        self.persistence = SeriesListingsPersistenceController(self)
        self.gallery = SeriesListingsGalleryController(self)
        self.card_actions = SeriesListingsCardActionsController(self)
        self.recommendation = SeriesListingsRecommendationController(self)
        self.filters = SeriesListingsFiltersController(self)
        self.semantic = SeriesListingsSemanticController(self)
        self.backup_sync = ListingsBackupSyncController(self)
        self.directory_import = SeriesListingsDirectoryImportController(self)

        self.ui_builder._build_ui()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        timer = getattr(self, "_resize_timer", None)
        if timer is not None:
            timer.start()

    def _build_ui(self) -> None:
        return self.ui_builder._build_ui()

    def _load_data(self):
        return self.persistence._load_data()

    def _media_repo(self):
        return self.persistence._media_repo()

    def _search_repo(self):
        return self.persistence._search_repo()

    def _upsert_entry(self, entry: Dict[str, Any]) -> bool:
        return self.persistence._upsert_entry(entry)

    def _delete_entry_row(self, entry_id: str) -> bool:
        return self.persistence._delete_entry_row(entry_id)

    def _filtered_entries(self) -> List[Dict[str, Any]]:
        return self.gallery._filtered_entries()

    def _apply_listing_operator_search(self, entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return self.gallery._apply_listing_operator_search(entries)

    def _rebuild_gallery(self):
        return self.gallery._rebuild_gallery()

    def _change_listing_page(self, delta: int) -> None:
        return self.gallery._change_listing_page(delta)

    def _on_advanced_search(self):
        return self.card_actions._on_advanced_search()

    def _clear_advanced_search(self):
        return self.card_actions._clear_advanced_search()

    def _on_card_clicked(self, entry_id: str):
        return self.card_actions._on_card_clicked(entry_id)

    def _on_card_delete_requested(self, entry_id: str):
        return self.card_actions._on_card_delete_requested(entry_id)

    def _on_card_image_remove_requested(self, entry_id: str):
        return self.card_actions._on_card_image_remove_requested(entry_id)

    def _show_gallery_context_menu(self, pos):
        return self.card_actions._show_gallery_context_menu(pos)

    def _on_add_new(self):
        return self.card_actions._on_add_new()

    def _on_entry_saved(self, entry: Dict[str, Any]):
        return self.card_actions._on_entry_saved(entry)

    def _on_entry_deleted(self, entry_id: str):
        return self.card_actions._on_entry_deleted(entry_id)

    def _on_external_reload(self) -> None:
        return self.card_actions._on_external_reload()

    def _on_recommend_content(self) -> None:
        return self.recommendation._on_recommend_content()

    def _run_recommendation(self, inputs: dict) -> None:
        return self.recommendation._run_recommendation(inputs)

    def _on_recommendation_results(self, results: list) -> None:
        return self.recommendation._on_recommendation_results(results)

    def _clear_recommendations(self) -> None:
        return self.recommendation._clear_recommendations()

    def _on_search(self, text: str):
        return self.filters._on_search(text)

    def _on_type_filter(self, text: str):
        return self.filters._on_type_filter(text)

    def _on_status_filter(self, text: str):
        return self.filters._on_status_filter(text)

    def _on_sort_changed(self, text: str):
        return self.filters._on_sort_changed(text)

    def _on_semantic_search(self) -> None:
        return self.semantic._on_semantic_search()

    def _on_semantic_search_finished(self, hits: List[Tuple[str, float, str]]) -> None:
        return self.semantic._on_semantic_search_finished(hits)

    def _on_semantic_search_error(self, message: str) -> None:
        return self.semantic._on_semantic_search_error(message)

    def _clear_semantic_search(self) -> None:
        return self.semantic._clear_semantic_search()

    def _on_build_search_index(self) -> None:
        return self.semantic._on_build_search_index()

    def _on_build_search_index_finished(self, results: list) -> None:
        return self.semantic._on_build_search_index_finished(results)

    def _on_build_search_index_error(self, message: str) -> None:
        return self.semantic._on_build_search_index_error(message)

    def _local_entries(self) -> List[dict[str, Any]]:
        return self.backup_sync._local_entries()

    def _set_local_entries(self, entries: List[dict[str, Any]]) -> None:
        return self.backup_sync._set_local_entries(entries)

    def _synchronize_listings(self):
        return self.backup_sync._synchronize_listings()

    def _on_sync_progress(self, percent, text):
        return self.backup_sync._on_sync_progress(percent, text)

    def _on_sync_finished(self, success, message, result_data):
        return self.backup_sync._on_sync_finished(success, message, result_data)

    def _update_encrypted_backup(self):
        return self.backup_sync._update_encrypted_backup()

    def _on_backup_progress(self, percent, text):
        return self.backup_sync._on_backup_progress(percent, text)

    def _on_backup_finished(self, success, message, result_data):
        return self.backup_sync._on_backup_finished(success, message, result_data)

    def _on_import_from_directory(self):
        return self.directory_import._on_import_from_directory()


__all__ = ["SeriesListingsSubTab"]
