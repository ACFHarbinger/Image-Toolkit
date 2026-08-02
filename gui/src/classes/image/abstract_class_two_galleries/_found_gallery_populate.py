"""Sequential (batched) population of the top "Found" gallery.

Extracted from ``abstract_class_two_galleries.py`` -- pure code motion, no
logic change (see ``_navigation.py``'s docstring).
"""

from __future__ import annotations

import os

from backend.src.constants import SUPPORTED_VIDEO_FORMATS
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap

from ....components import ClickableLabel
from ....helpers import ImageLoaderWorker


class _FoundGalleryPopulateMixin:
    """Batch-populate found-gallery cards, then trigger their thumbnail loads."""

    def refresh_found_gallery(self):
        self.cancel_loading()

        if not hasattr(self, "found_loading_paths"):
            self.found_loading_paths = set()
        self.found_loading_paths.clear()

        # 1. Identify new paginated slice
        self._paginated_found_paths = self.common_get_paginated_slice(
            self.found_files, self.found_current_page, self.found_page_size
        )
        new_paths_set = set(self._paginated_found_paths)

        # 2. Identify which currently displayed widgets to REMOVE
        paths_to_remove = []
        for path in list(self.path_to_label_map.keys()):
            if path not in new_paths_set:
                paths_to_remove.append(path)

        for path in paths_to_remove:
            widget = self.path_to_label_map.pop(path)
            widget.deleteLater()

        # 3. Reflow and Pagination update
        self._update_pagination_ui(is_found=True)

        if not self.found_files:
            self.common_show_placeholder(
                self.found_gallery_layout, "No images found.", 1
            )
            if self.status_label:
                self.status_label.setText("Found 0 files.")
            return

        # Setup batch population
        self._paginated_found_paths = self.common_get_paginated_slice(
            self.found_files, self.found_current_page, self.found_page_size
        )
        self._populating_found_index = 0

        if self.status_label:
            self.status_label.setText(
                f"Found {len(self.found_files)} files. Showing page {self.found_current_page + 1}."
            )

        # Start population loop
        self._populate_found_step()

    def _populate_found_step(self):
        if not hasattr(
            self, "_paginated_found_paths"
        ) or self._populating_found_index >= len(self._paginated_found_paths):
            self._load_all_found_page_images()
            return

        cols = self.common_calculate_columns(
            self.found_gallery_scroll, self.approx_item_width
        )
        batch_size = 5
        limit = min(
            self._populating_found_index + batch_size, len(self._paginated_found_paths)
        )

        for i in range(self._populating_found_index, limit):
            path = self._paginated_found_paths[i]

            # If widget already exists (was kept during refresh), just update its position
            if path in self.path_to_label_map:
                card = self.path_to_label_map[path]
                row = i // cols
                col = i % cols
                if self.found_gallery_layout:
                    # addWidget will move it if it's already in the layout
                    self.found_gallery_layout.addWidget(
                        card, row, col, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
                    )
                continue

            # Otherwise create new widget
            is_selected = path in self.selected_files

            # Check cache for instant thumbnail (stored as QImage, convert for widget)
            _cached = self._found_pixmap_cache.get(path)

            if _cached is None and path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS)):
                cache_path = self._get_disk_cache_path(path)
                if os.path.exists(cache_path):
                    _cached = QImage(cache_path)
                    if not _cached.isNull():
                        self._found_pixmap_cache[path] = _cached

            initial_pixmap = (
                QPixmap.fromImage(_cached) if isinstance(_cached, QImage) else _cached
            )

            # Create widget
            card = self.create_card_widget(path, initial_pixmap, is_selected)
            card.setProperty("gallery_path", path)  # used by update_card_style for color labels (§2.18C)

            if isinstance(card, ClickableLabel):
                card.path_clicked.connect(self._on_found_card_clicked)  # §2.4B
                if hasattr(card, "path_right_clicked"):
                    card.path_right_clicked.connect(self._on_found_card_right_clicked)  # §2.4C

            self._add_filename_label(card, path)  # §2.14A

            row = i // cols
            col = i % cols
            if self.found_gallery_layout:
                self.found_gallery_layout.addWidget(
                    card, row, col, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
                )

            self.path_to_label_map[path] = card

            # DEFER Trigger load
            # self._trigger_found_load(path)

        self._populating_found_index = limit

        # Schedule next batch
        if self._populating_found_index < len(self._paginated_found_paths):
            self._populate_found_timer.start(0)
        else:
            self._load_all_found_page_images()

    def _load_all_found_page_images(self):
        """Triggers loading for all images in the current found gallery paginated view."""
        if (
            not hasattr(self, "_paginated_found_paths")
            or not self._paginated_found_paths
        ):
            return

        paths_to_load = []
        for path in self._paginated_found_paths:
            if path in self._found_pixmap_cache:
                continue
            if (
                hasattr(self, "found_loading_paths")
                and path in self.found_loading_paths
            ):
                continue
            paths_to_load.append(path)

        if not paths_to_load:
            return

        # Separate images and videos
        image_paths = [
            p
            for p in paths_to_load
            if not p.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS))
        ]
        video_paths = [
            p
            for p in paths_to_load
            if p.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS))
        ]

        if video_paths:
            for p in video_paths:
                self._trigger_video_found_load(p)

        if image_paths:
            self._trigger_batch_found_load(image_paths)

    def _trigger_found_load(self, path: str):
        if not hasattr(self, "found_loading_paths"):
            self.found_loading_paths = set()

        self.found_loading_paths.add(path)
        worker = ImageLoaderWorker(path, self.thumbnail_size)
        worker.load_generation = self._load_generation
        worker.signals.result.connect(self._on_found_image_loaded)

        self._active_workers.add(worker)
        self.thread_pool.start(worker)

    # _on_found_image_loaded is defined earlier to handle QImage/QPixmap types


__all__ = ["_FoundGalleryPopulateMixin"]
