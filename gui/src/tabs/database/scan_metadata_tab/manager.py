"""``ScanMetadataTab`` -- composed controllers over ``AbstractClassTwoGalleries`` (#544)."""

from __future__ import annotations

import contextlib
from typing import Any, Dict, List, Optional, Set, Tuple

from PySide6.QtCore import QPoint, Qt, QThreadPool, QTimer
from PySide6.QtGui import QImage, QResizeEvent
from PySide6.QtWidgets import QWidget

from gui.src.modules.events import DatabaseAvailabilityChanged, EventHub, ImportPathsIntent, TagCatalogChanged
from gui.src.modules.library_service import coerce_library_database_service

from ....classes import AbstractClassTwoGalleries
from ....helpers import UpsertWorker
from ._auto_listings import ScanAutoListingsController
from ._config import ScanConfigController
from ._context_menu_actions import ScanContextMenuController
from ._gallery_cards import ScanGalleryCardsController
from ._keyboard_selection import ScanKeyboardController
from ._layout_reflow import ScanLayoutController
from ._lazy_loading import ScanLazyLoadController
from ._pagination import ScanPaginationController
from ._scan_loading import ScanLoadingController
from ._selection_gallery import ScanSelectionController
from ._ui_builder import ScanUIBuilder
from ._upsert_ops import ScanUpsertController
from ._view_toggles import ScanViewTogglesController


class ScanMetadataTab(AbstractClassTwoGalleries):
    """Scan directory metadata, preview gallery, and batch database operations.

    Phase 2 (ui-arch-23/#544): mixins collapsed into composed controllers.
    Gallery inheritance stays.
    """

    def __init__(self, database_service=None, event_hub: EventHub | None = None, **legacy):
        super().__init__()
        self.database_service = coerce_library_database_service(
            database_service if database_service is not None else legacy.pop("db_tab_ref", None)
        )
        self.event_hub = event_hub or EventHub(self)

        self.scan_image_list: list[str] = []
        self.scan_filtered_list: list[str] = []
        self.selected_image_paths: Set[str] = set()
        self._selected_order: list[str] = []
        self.open_preview_windows: list[QWidget] = []
        self.view_new_only: bool = False
        self.view_in_db_only: bool = False
        self._db_was_connected: bool = False
        self._loading_cancelled = False
        self.thumbnail_size = 180
        self.padding_width = 10
        self.approx_item_width = self.thumbnail_size + self.padding_width + 20
        self.scan_page_size = 100
        self.scan_current_page = 0
        self.scan_total_pages = 1
        self.selected_page_size = 100
        self.selected_current_page = 0
        self.selected_total_pages = 1
        self.scan_thread = None
        self.scan_worker = None
        self.current_upsert_worker: Optional[UpsertWorker] = None
        self.thread_pool = QThreadPool()
        self._loaded_results_buffer: List[Tuple[str, QImage]] = []
        self._images_loaded_count = 0
        self._total_images_to_load = 0

        self.ui_builder = ScanUIBuilder(self)
        self.pagination = ScanPaginationController(self)
        self.keyboard = ScanKeyboardController(self)
        self.layout_reflow = ScanLayoutController(self)
        self.gallery_cards = ScanGalleryCardsController(self)
        self.selection = ScanSelectionController(self)
        self.scan_loading = ScanLoadingController(self)
        self.lazy_loading = ScanLazyLoadController(self)
        self.view_toggles = ScanViewTogglesController(self)
        self.context_menu = ScanContextMenuController(self)
        self.upsert = ScanUpsertController(self)
        self.auto_listings = ScanAutoListingsController(self)
        self.config_controller = ScanConfigController(self)

        self._resize_timer = QTimer()
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._repack_galleries)
        self.loaded_paths: Set[str] = set()
        self.loading_paths: Set[str] = set()
        self._lazy_load_timer = QTimer()
        self._lazy_load_timer.setSingleShot(True)
        self._lazy_load_timer.setInterval(150)
        self._lazy_load_timer.timeout.connect(self._process_visible_items)

        self.ui_builder._build_ui()
        self.event_hub.subscribe(ImportPathsIntent, self._on_import_paths, owner=self)
        self.event_hub.subscribe(TagCatalogChanged, self._on_tag_catalog_changed, owner=self)
        self.event_hub.subscribe(DatabaseAvailabilityChanged, self._on_database_availability_changed, owner=self)

    def _on_import_paths(self, intent: ImportPathsIntent) -> None:
        if intent.module_id != "library.scan":
            return
        self.process_scan_results(list(intent.paths))
        self.view_db_only_button.setChecked(False)

    def _on_tag_catalog_changed(self, _event: TagCatalogChanged) -> None:
        self._setup_tag_checkboxes()

    def _on_database_availability_changed(self, event: DatabaseAvailabilityChanged) -> None:
        self.update_button_states(event.connected)

    def keyPressEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_A:
            self._select_all_images()
            event.accept()
            return
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier and event.key() == Qt.Key.Key_D:
            self._deselect_all_images()
            event.accept()
            return
        super().keyPressEvent(event)

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)

    def showEvent(self, event):
        super().showEvent(event)

    def cancel_loading(self):
        with contextlib.suppress(Exception):
            super().cancel_loading()
        if hasattr(self, "dual"):
            self.dual.cancel_loading()
        self.scan_loading._stop_running_threads()
        self._loaded_results_buffer.clear()
        print("Loading cancelled by user.")

    def _update_pagination_ui(self, is_found: bool, mode="scan"):
        return self.pagination._update_pagination_ui(is_found, mode)

    def _select_all_images(self):
        return self.keyboard._select_all_images()

    def _deselect_all_images(self):
        return self.keyboard._deselect_all_images()

    def _repack_galleries(self):
        return self.layout_reflow._repack_galleries()

    def _repack_specific_layout(self, layout, scroll_area):
        return self.layout_reflow._repack_specific_layout(layout, scroll_area)

    def _setup_tag_checkboxes(self):
        return self.gallery_cards._setup_tag_checkboxes()

    def on_selection_changed(self) -> None:
        return self.selection.on_selection_changed()

    def toggle_selection(self, path):
        return self.selection.toggle_selection(path)

    def handle_marquee_selection(self, paths_from_marquee: set, is_ctrl_pressed: bool):
        return self.selection.handle_marquee_selection(paths_from_marquee, is_ctrl_pressed)

    def _sync_selection_from_dual(self):
        return self.selection._sync_selection_from_dual()

    def populate_selected_images_gallery(self):
        return self.selection.populate_selected_images_gallery()

    def reorder_selected(self, dragged_path: str, target_path: str) -> None:
        return self.selection.reorder_selected(dragged_path, target_path)

    def browse_scan_directory(self):
        return self.scan_loading.browse_scan_directory()

    def populate_scan_image_gallery(self, directory: str, is_refresh: bool = False):
        return self.scan_loading.populate_scan_image_gallery(directory, is_refresh)

    def process_scan_results(self, image_paths: list[str]):
        return self.scan_loading.process_scan_results(image_paths)

    def apply_scan_filters(self):
        return self.scan_loading.apply_scan_filters()

    def handle_scan_directory_return(self):
        return self.scan_loading.handle_scan_directory_return()

    def on_scan_thread_finished(self):
        return self.scan_loading.on_scan_thread_finished()

    def start_scan(self):
        return self.scan_loading.start_scan()

    def stop_scan(self):
        return self.scan_loading.stop_scan()

    def upsert_selected(self):
        return self.scan_loading.upsert_selected()

    def _process_visible_items(self):
        return self.lazy_loading._process_visible_items()

    def _on_scroll_event(self, value):
        return self.lazy_loading._on_scroll_event(value)

    def on_single_image_loaded(self, path: str, pixmap):
        return self.lazy_loading.on_single_image_loaded(path, pixmap)

    def handle_scan_error(self, message: str):
        return self.view_toggles.handle_scan_error(message)

    def toggle_new_only_view(self, checked: bool):
        return self.view_toggles.toggle_new_only_view(checked)

    def toggle_in_db_only_view(self, checked: bool):
        return self.view_toggles.toggle_in_db_only_view(checked)

    def update_button_states(self, connected: bool):
        return self.view_toggles.update_button_states(connected)

    def show_image_context_menu(self, global_pos: QPoint, path: str):
        return self.context_menu.show_image_context_menu(global_pos, path)

    def _view_single_image_preview(self, image_path: str):
        return self.context_menu._view_single_image_preview(image_path)

    def perform_upsert_operation(self):
        return self.upsert.perform_upsert_operation()

    def delete_selected_images(self):
        return self.upsert.delete_selected_images()

    def _execute_upsert(self, results: list):
        return self.upsert._execute_upsert(results)

    def _cleanup_upsert_worker(self):
        return self.upsert._cleanup_upsert_worker()

    def _on_upsert_progress(self, current: int, total: int):
        return self.upsert._on_upsert_progress(current, total)

    def _on_upsert_error(self, exc: Exception):
        return self.upsert._on_upsert_error(exc)

    def _on_upsert_prepared(self, prepared: list):
        return self.upsert._on_upsert_prepared(prepared)

    def _maybe_offer_auto_listings(self, touched_group_names: List[str]) -> None:
        return self.auto_listings._maybe_offer_auto_listings(touched_group_names)

    def collect(self) -> dict:
        return self.config_controller.collect()

    def get_default_config(self) -> Dict[str, Any]:
        return self.config_controller.get_default_config()

    def set_config(self, config: Dict[str, Any]):
        return self.config_controller.set_config(config)

    def refresh_image_directory(self):
        return self.config_controller.refresh_image_directory()


__all__ = ["ScanMetadataTab"]
