"""Bottom "Selected" gallery: rebuild, batch/priority thumbnail loading.

Extracted from ``abstract_class_two_galleries.py`` -- pure code motion, no
logic change (see ``_navigation.py``'s docstring).
"""

from __future__ import annotations

import os
import weakref
from typing import Dict, List, Optional

from backend.src.constants import SUPPORTED_VIDEO_FORMATS
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QWidget
from shiboken6 import Shiboken

from ....components import ClickableLabel
from ....helpers import BatchImageLoaderWorker, ImageLoaderWorker
from ...mixins import install_drag_reorder

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..protos.abstract_class_two_galleries import AbstractClassTwoGalleriesHostProtocol


class _SelectedPanelMixin:
    """Rebuild the paginated "Selected" gallery and load its thumbnails."""

    def _cache_get_as_pixmap(self: "AbstractClassTwoGalleriesHostProtocol", path: str) -> Optional[QPixmap]:
        """Retrieve a cached thumbnail as QPixmap, converting from QImage if needed."""
        img = self._selected_pixmap_cache.get(path) or self._found_pixmap_cache.get(
            path
        )
        if img is None:
            return None
        return QPixmap.fromImage(img) if isinstance(img, QImage) else img

    def refresh_selected_panel(self: "AbstractClassTwoGalleriesHostProtocol"):  # noqa: C901
        if not self.selected_gallery_layout:
            return

        # 1. Harvest pixmaps from current widgets to refresh cache
        for path, widget in self.selected_card_map.items():
            try:
                if hasattr(widget, "get_pixmap"):
                    pixmap = widget.get_pixmap()
                    if pixmap and not pixmap.isNull():
                        self._selected_pixmap_cache[path] = pixmap
            except RuntimeError:
                continue

        # 2. Identify new paginated slice
        paginated_paths = self.common_get_paginated_slice(
            self.selected_files, self.selected_current_page, self.selected_page_size
        )
        new_paths_set = set(paginated_paths)

        # 3. Identify and remove widgets not in the new slice
        paths_to_remove = [p for p in self.selected_card_map if p not in new_paths_set]
        for path in paths_to_remove:
            widget = self.selected_card_map.pop(path)
            widget.deleteLater()

        # 4. Update pagination
        self._update_pagination_ui(is_found=False)

        if not self.selected_files:
            # If empty, clear whatever is left and show placeholder
            self._clear_layout(self.selected_gallery_layout)
            self.common_show_placeholder(
                self.selected_gallery_layout, "Selected files will appear here.", 1
            )
            return

        # 5. Arrange/Create widgets
        columns = self.common_calculate_columns(
            self.selected_gallery_scroll, self.approx_item_width
        )
        paths_to_load = []
        target_widgets = {}

        for i, path in enumerate(paginated_paths):
            row = i // columns
            col = i % columns

            if path in self.selected_card_map:
                # Reuse existing widget
                card = self.selected_card_map[path]
                self.selected_gallery_layout.addWidget(
                    card, row, col, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
                )
            else:
                # Create new widget
                pixmap = self._cache_get_as_pixmap(path)
                if pixmap is None:
                    top_widget = self.path_to_label_map.get(path)
                    if top_widget:
                        try:
                            if hasattr(top_widget, "get_pixmap"):
                                pixmap = top_widget.get_pixmap()
                        except RuntimeError:
                            pixmap = None

                card = self.create_card_widget(path, pixmap, is_selected=True)
                self._add_filename_label(card, path)  # §2.14A
                self.selected_card_map[path] = card
                self.selected_gallery_layout.addWidget(
                    card, row, col, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
                )
                install_drag_reorder(card, path, self, "reorder_selected")

                if pixmap is None:
                    paths_to_load.append(path)
                    target_widgets[path] = card

                if isinstance(card, ClickableLabel):
                    card.path_clicked.connect(
                        lambda checked, p=path: self.toggle_selection(p)
                    )

        if paths_to_load:
            self._trigger_batch_selected_load(paths_to_load, target_widgets)

    def _trigger_batch_selected_load(
        self: "AbstractClassTwoGalleriesHostProtocol", paths: List[str], widgets: Dict[str, QWidget]
    ):
        self.common_start_chunked_load(
            paths,
            worker_factory=lambda chunk: BatchImageLoaderWorker(
                chunk, self.thumbnail_size
            ),
            batch_slot=lambda results, paths_arg, w=widgets: self._on_batch_selected_loaded(
                results, w
            ),
        )

    def _on_batch_selected_loaded(
        self: "AbstractClassTwoGalleriesHostProtocol", results: List[tuple], widgets: Dict[str, QWidget]
    ):
        # self may already be a dead QObject by the time this queued
        # (cross-thread) signal is delivered (e.g. mid-teardown) --
        # self.sender() on a dead QObject segfaults rather than raising.
        if not Shiboken.isValid(self):
            return
        # Cleanup worker ref
        sender = self.sender()
        stale = False
        if sender:
            for worker in list(self._active_workers):
                if worker.signals == sender:
                    # This chunk was already dispatched before a newer
                    # directory switch bumped _load_generation -- its
                    # result still arrives here even though it's no longer
                    # current (see abstract_class_single_gallery.py's
                    # _on_batch_images_loaded for the full rationale).
                    if getattr(worker, "load_generation", self._load_generation) != self._load_generation:
                        stale = True
                    self._active_workers.remove(worker)
                    break
        if stale:
            return
        for path, image in results:
            if image and not image.isNull():
                self._selected_pixmap_cache[path] = image  # store QImage

                # Save to disk cache if it's a video
                if path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS)):
                    cache_path = self._get_disk_cache_path(path)
                    if not os.path.exists(cache_path):
                        image.save(cache_path, b"JPG")
            widget = widgets.get(path)
            if widget:
                try:
                    display_pixmap = (
                        QPixmap.fromImage(image) if isinstance(image, QImage) else image
                    )
                    self.update_card_pixmap(widget, display_pixmap)
                except RuntimeError:
                    pass

    def _trigger_priority_load(self: "AbstractClassTwoGalleriesHostProtocol", path: str, target_widget: QWidget):
        weak_widget = weakref.ref(target_widget)
        worker = ImageLoaderWorker(path, self.thumbnail_size)
        worker.load_generation = self._load_generation
        self._active_workers.add(worker)
        worker.signals.result.connect(
            lambda p, px: self._on_selected_image_loaded(p, px, weak_widget())
            if weak_widget() is not None
            else None
        )
        self.thread_pool.start(worker)

    def _on_selected_image_loaded(self: "AbstractClassTwoGalleriesHostProtocol", path: str, image, widget: Optional[QWidget]):
        # See _on_batch_selected_loaded above.
        if not Shiboken.isValid(self):
            return
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
            return
        if widget is None:
            return
        if image and not image.isNull():
            self._selected_pixmap_cache[path] = image  # store QImage

            # Save to disk cache if it's a video
            if path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS)):
                cache_path = self._get_disk_cache_path(path)
                if not os.path.exists(cache_path):
                    if isinstance(image, QImage):
                        image.save(cache_path, b"JPG")  # pyrefly: ignore[no-matching-overload]
                    else:
                        image.toImage().save(cache_path, b"JPG")
        display_pixmap = (
            QPixmap.fromImage(image) if isinstance(image, QImage) else image
        )
        self.update_card_pixmap(widget, display_pixmap)


__all__ = ["_SelectedPanelMixin"]
