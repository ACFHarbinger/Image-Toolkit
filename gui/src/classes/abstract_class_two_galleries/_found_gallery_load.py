"""Found-gallery search filtering and image/video thumbnail loading.

Extracted from ``abstract_class_two_galleries.py`` -- pure code motion, no
logic change (see ``_navigation.py``'s docstring).
"""

from __future__ import annotations

import contextlib
import os
from typing import List

from backend.src.constants import SUPPORTED_VIDEO_FORMATS
from PySide6.QtCore import Slot
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QLabel

from ...helpers import BatchImageLoaderWorker, BatchVideoLoaderWorker, VideoLoaderWorker


class _FoundGalleryLoadMixin:
    """Search filtering plus image/video batch and single-shot thumbnail loading."""

    def _perform_found_search(self):
        query = self.found_search_input.text()
        filtered = self.common_filter_string_list(self.master_found_files, query)
        self.found_files = filtered
        self.found_current_page = 0
        self.refresh_found_gallery()

    def start_loading_thumbnails(self, paths: list[str]):
        self.cancel_loading()
        self.master_found_files = self._apply_sort(list(paths))
        # Clear cache when starting fresh with new content
        self._found_pixmap_cache.clear()
        # Apply search immediately
        self._perform_found_search()
        # self.refresh_found_gallery() # Called by search

    def _trigger_batch_video_found_load(self, paths: List[str]):
        """Trigger batch workers for all visible videos, chunked for parallel loading."""
        if not hasattr(self, "found_loading_paths"):
            self.found_loading_paths = set()

        self.found_loading_paths.update(paths)
        self.common_start_chunked_load(
            paths,
            worker_factory=lambda chunk: BatchVideoLoaderWorker(
                chunk, self.thumbnail_size
            ),
            per_result_slot=self._on_found_image_loaded,
            batch_slot=self._on_batch_found_loaded,
        )

    def _trigger_video_found_load(self, path: str):
        """Fallback for single video load (rarely used by batch logic but kept for consistency)."""
        if not hasattr(self, "found_loading_paths"):
            self.found_loading_paths = set()

        self.found_loading_paths.add(path)
        worker = VideoLoaderWorker(path, self.thumbnail_size)
        worker.load_generation = self._load_generation
        worker.signals.result.connect(self._on_found_image_loaded)
        self._active_workers.add(worker)
        self.thread_pool.start(worker)

    @Slot(str, object)
    def _on_found_image_loaded(self, path: str, image):  # noqa: C901
        # Cleanup worker ref if it is NOT a batch worker
        sender = self.sender()
        stale = False
        if sender:
            # We need to find the worker that owns this signals object
            for worker in list(self._active_workers):
                if worker.signals == sender:
                    if getattr(worker, "load_generation", self._load_generation) != self._load_generation:
                        stale = True
                    if not isinstance(worker, (BatchImageLoaderWorker, BatchVideoLoaderWorker)):
                        self._active_workers.remove(worker)
                    break
        if stale:
            if hasattr(self, "found_loading_paths"):
                self.found_loading_paths.discard(path)
            return

        if hasattr(self, "found_loading_paths") and path in self.found_loading_paths:
            self.found_loading_paths.remove(path)

        # Cache QImage (half the memory of QPixmap on X11)
        if isinstance(image, QImage) and not image.isNull():
            self._found_pixmap_cache[path] = image
            # Save to disk cache if it's a video
            if path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS)):
                cache_path = self._get_disk_cache_path(path)
                if not os.path.exists(cache_path):
                    image.save(cache_path, "JPG")  # pyrefly: ignore[no-matching-overload]
        elif not isinstance(image, QImage) and image and not image.isNull():
            q_image = image.toImage()
            self._found_pixmap_cache[path] = q_image
            # Save to disk cache if it's a video
            if path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS)):
                cache_path = self._get_disk_cache_path(path)
                if not os.path.exists(cache_path):
                    q_image.save(cache_path, "JPG")

        widget = self.path_to_label_map.get(path)
        if widget:
            try:
                pixmap = QPixmap.fromImage(image) if isinstance(image, QImage) else image

                if pixmap.isNull():
                    # Explicitly handle failure instead of resetting to "Loading..."
                    img_label = widget.findChild(QLabel)
                    if img_label:
                        img_label.clear()
                        img_label.setText("No Thumbnail")
                        img_label.setStyleSheet("border: 1px dashed #666; color: #999;")
                else:
                    self.update_card_pixmap(widget, pixmap)
            except RuntimeError:
                pass

    def _trigger_batch_found_load(self, paths: List[str]):
        if not hasattr(self, "found_loading_paths"):
            self.found_loading_paths = set()
        self.found_loading_paths.update(paths)
        self.common_start_chunked_load(
            paths,
            worker_factory=lambda chunk: BatchImageLoaderWorker(
                chunk, self.thumbnail_size
            ),
            per_result_slot=self._on_found_image_loaded,
            batch_slot=self._on_batch_found_loaded,
        )

    @Slot(list, list)
    def _on_batch_found_loaded(self, results: List[tuple], requested_paths: List[str]):  # noqa: C901
        # Cleanup worker ref
        sender = self.sender()
        stale = False
        if sender:
            for worker in list(self._active_workers):
                if worker.signals == sender:
                    if getattr(worker, "load_generation", self._load_generation) != self._load_generation:
                        stale = True
                    self._active_workers.remove(worker)
                    break
        if stale:
            for path in requested_paths:
                if hasattr(self, "found_loading_paths"):
                    self.found_loading_paths.discard(path)
                elif path in getattr(self, "_loading_paths", set()):
                    self._loading_paths.discard(path)
            return

        for path, pixmap in results:
            if (
                hasattr(self, "found_loading_paths")
                and path in self.found_loading_paths
            ):
                self.found_loading_paths.remove(path)
            elif path in getattr(self, "_loading_paths", set()):
                self._loading_paths.remove(path)

            # Cache QImage, convert to QPixmap for display only
            if isinstance(pixmap, QImage) and not pixmap.isNull():
                self._found_pixmap_cache[path] = pixmap  # store QImage
                final_pixmap = QPixmap.fromImage(pixmap)
                # Save to disk cache if it's a video
                if path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS)):
                    cache_path = self._get_disk_cache_path(path)
                    if not os.path.exists(cache_path):
                        pixmap.save(cache_path, "JPG")  # pyrefly: ignore[no-matching-overload]
            elif not isinstance(pixmap, QImage) and pixmap and not pixmap.isNull():
                q_image = pixmap.toImage()
                self._found_pixmap_cache[path] = q_image
                final_pixmap = pixmap
                # Save to disk cache if it's a video
                if path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS)):
                    cache_path = self._get_disk_cache_path(path)
                    if not os.path.exists(cache_path):
                        q_image.save(cache_path, "JPG")
            else:
                final_pixmap = QPixmap()

            widget = self.path_to_label_map.get(path)
            if widget:
                with contextlib.suppress(RuntimeError):
                    self.update_card_pixmap(widget, final_pixmap)


__all__ = ["_FoundGalleryLoadMixin"]
