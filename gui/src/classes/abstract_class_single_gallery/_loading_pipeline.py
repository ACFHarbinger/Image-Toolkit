"""Async thumbnail loading pipeline: dispatch, batch results, and population.

Extracted from ``abstract_class_single_gallery.py`` -- pure code motion, no
logic change.

Video thumbnail loading (VideoLoaderWorker) was removed entirely
(2026-08-01) alongside the rest of the app's directory-video-scanning
functionality -- see Addendum 23 in
.agent/cache/gallery_crash_deleteorphaned_2026-07-27.md.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QImage, QPixmap

from ...helpers import BatchImageLoaderWorker, ImageLoaderWorker
from ...utils.cache.lru_image_cache import LRUImageCache
from ...utils.sort_utils import natural_sort_key


class _LoadingPipelineMixin:
    """Dispatches image/video thumbnail loads and populates the gallery grid."""

    @Slot(list, list)
    def _on_batch_images_loaded(self, results: List[tuple], requested_paths: List[str]):  # noqa: C901
        # Cleanup worker reference if called from signals
        sender = self.sender()
        stale = False
        if sender:
            # We need to find the worker that owns this signals object
            for worker in list(self._active_workers):
                if worker.signals == sender:
                    # See _on_single_image_loaded's comment: this chunk was
                    # already dispatched before a newer directory switch
                    # bumped _load_generation, so its result still arrives
                    # here even though it's no longer current -- drop it
                    # rather than touching a (possibly already-destroyed)
                    # widget from the superseded scan.
                    if getattr(worker, "load_generation", self._load_generation) != self._load_generation:
                        stale = True
                    self._active_workers.remove(worker)
                    break

        if stale:
            for path in requested_paths:
                self._loading_paths.discard(path)
            return

        # 1. Update Results
        for path, q_image in results:
            if path in self._loading_paths:
                self._loading_paths.remove(path)

            pixmap = QPixmap.fromImage(q_image)
            widget = self.path_to_card_widget.get(path)

            if not pixmap.isNull():
                if not q_image.isNull():
                    self._initial_pixmap_cache[path] = q_image  # store QImage
                if widget:
                    self.update_card_pixmap(widget, pixmap)
            else:
                # Mark as failed if the image is Null
                if not hasattr(self, "_failed_paths"):
                    self._failed_paths = set()
                self._failed_paths.add(path)
                if widget:
                    self.update_card_pixmap(widget, QPixmap())

        # 2. Cleanup Missing Results
        processed_paths = set(p for p, _ in results)
        for path in requested_paths:
            if path not in processed_paths:
                if path in self._loading_paths:
                    self._loading_paths.remove(path)

                if not hasattr(self, "_failed_paths"):
                    self._failed_paths = set()
                self._failed_paths.add(path)

                widget = self.path_to_card_widget.get(path)
                if widget:
                    self.update_card_pixmap(widget, QPixmap())

    def _trigger_batch_found_load(self, paths: List[str]):
        if not hasattr(self, "_loading_paths"):
            self._loading_paths = set()
        self._loading_paths.update(paths)
        self.common_start_chunked_load(
            paths,
            worker_factory=lambda chunk: BatchImageLoaderWorker(
                chunk, self.thumbnail_size
            ),
            per_result_slot=self._on_single_image_loaded,
            batch_slot=self._on_batch_images_loaded,
        )

    def start_loading_gallery(
        self,
        paths: List[str],
        show_progress: bool = True,
        append: bool = False,
        pixmap_cache: Optional[Dict[str, QPixmap]] = None,
    ):
        """
        Starts the loading process. Accepts an optional pixmap_cache for pre-generated thumbnails.
        """
        if not append:
            self.master_image_paths = self._apply_sort(list(paths))
            self._perform_search()

            self._initial_pixmap_cache = LRUImageCache(maxsize=300)
            if pixmap_cache:
                for k, v in pixmap_cache.items():
                    self._initial_pixmap_cache[k] = v
            self._loading_paths.clear()
            self._failed_paths.clear()
        else:
            self.master_image_paths.extend(paths)
            self.master_image_paths.sort(key=natural_sort_key)
            if pixmap_cache and pixmap_cache is not self._initial_pixmap_cache:
                for k, v in pixmap_cache.items():
                    self._initial_pixmap_cache[k] = v
            # Re-apply search to include new appended items
            self._perform_search()

        # self.refresh_gallery_view() # _perform_search calls this

    def refresh_gallery_view(self):
        self.cancel_loading()
        self.clear_gallery_widgets()
        self._update_pagination_ui()

        if not self.gallery_image_paths:
            self.common_show_placeholder(
                self.gallery_layout, "No images to display.", self.calculate_columns()
            )
            return

        # Prepare for sequential loading
        self._paginated_paths = self.common_get_paginated_slice(
            self.gallery_image_paths, self.current_page, self.page_size
        )
        self._populating_index = 0

        # Start population
        self._populate_step()

    def _populate_step(self):
        """Adds a small batch of widgets to the layout."""
        if not hasattr(self, "_paginated_paths") or self._populating_index >= len(
            self._paginated_paths
        ):
            self._load_all_page_images()
            return

        cols = self.calculate_columns()
        batch_size = 5
        limit = min(self._populating_index + batch_size, len(self._paginated_paths))

        for i in range(self._populating_index, limit):
            path = self._paginated_paths[i]
            _cached = self._initial_pixmap_cache.get(path)

            initial_pixmap = (
                QPixmap.fromImage(_cached) if isinstance(_cached, QImage) else _cached
            )

            # 3. Create Widget
            card = self.create_card_widget(path, initial_pixmap)
            self._add_filename_label(card, path)  # §2.14A
            self.path_to_card_widget[path] = card

            # 4. Add to Layout
            row = i // cols
            col = i % cols
            if self.gallery_layout:
                self.gallery_layout.addWidget(
                    card, row, col, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
                )

            # 5. DEFER Async Load (Visibility Check)
            # Images are loaded asynchronously via visibility check
            # if initial_pixmap is None:
            #     pass

        self._populating_index = limit

        if self._populating_index < len(self._paginated_paths):
            self._populate_timer.start(0)
        else:
            self._load_all_page_images()

    def _load_all_page_images(self):
        """Triggers loading for all images in the current paginated view."""
        if not self._paginated_paths:
            return

        paths_to_load = []
        for path in self._paginated_paths:
            if path in self._initial_pixmap_cache:
                continue
            if path in self._loading_paths:
                continue
            paths_to_load.append(path)

        if not paths_to_load:
            return

        self._trigger_batch_found_load(paths_to_load)

    def calculate_columns(self):
        return self.common_calculate_columns(
            self.gallery_scroll_area, self.approx_item_width
        )

    def _trigger_image_load(self, path: str):
        self._loading_paths.add(path)
        worker = ImageLoaderWorker(path, self.thumbnail_size)
        worker.load_generation = self._load_generation
        worker.signals.result.connect(self._on_single_image_loaded)

        self._active_workers.add(worker)
        self.thread_pool.start(worker)

    @Slot(str, QImage)
    def _on_single_image_loaded(self, path: str, q_image: QImage):
        # Cleanup worker ref if it is NOT a BatchImageLoaderWorker
        # BatchImageLoaderWorker is cleaned up in _on_batch_images_loaded
        sender = self.sender()
        stale = False
        if sender:
            # We need to find the worker that owns this signals object
            for worker in list(self._active_workers):
                if worker.signals == sender:
                    # This result was already in flight (chunk dispatched,
                    # or a single image/video load started) when a newer
                    # directory switch bumped _load_generation. Only *new*
                    # chunk dispatch is gated by that bump
                    # (common_start_chunked_load's start_next()) -- an
                    # already-running worker's own result still arrives
                    # here regardless, and path_to_card_widget/the gallery
                    # layout may already belong to the new directory (or be
                    # mid-teardown) by the time it does. Drop it instead of
                    # touching a widget that may no longer be what `path`
                    # thinks it is, or may already be destroyed.
                    if getattr(worker, "load_generation", self._load_generation) != self._load_generation:
                        stale = True
                    if not isinstance(worker, BatchImageLoaderWorker):
                        self._active_workers.remove(worker)
                    break

        if stale:
            self._loading_paths.discard(path)
            return

        if path in self._loading_paths:
            self._loading_paths.remove(path)

        pixmap = QPixmap.fromImage(q_image)

        # If loading failed, mark as failed instead of generating a red placeholder
        if pixmap.isNull():
            if not hasattr(self, "_failed_paths"):
                self._failed_paths = set()
            self._failed_paths.add(path)

            # Cache a null sentinel so _load_all_page_images stops requesting this path
            self._initial_pixmap_cache[path] = QImage()

            widget = self.path_to_card_widget.get(path)
            if widget:
                # This will trigger the "VIDEO" / "No Thumbnail" text style via update_card_pixmap
                self.update_card_pixmap(widget, QPixmap())
            return

        # Cache the raw QImage (half the RAM of QPixmap on X11)
        if not q_image.isNull():
            self._initial_pixmap_cache[path] = q_image

        widget = self.path_to_card_widget.get(path)
        if widget:
            self.update_card_pixmap(widget, pixmap)


__all__ = ["_LoadingPipelineMixin"]
