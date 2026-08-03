"""Resize/show events, column-reflow, and the debounced search filter.

Extracted from ``abstract_class_single_gallery.py`` -- pure code motion, no
logic change.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, cast

from PySide6.QtCore import Slot
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import QWidget

if TYPE_CHECKING:
    from ..protos.abstract_class_single_gallery import AbstractClassSingleGalleryHostProtocol


class _GeometryEventsMixin:
    """resizeEvent/showEvent/_on_layout_change and the search-debounce filter."""

    def resizeEvent(self: "AbstractClassSingleGalleryHostProtocol", event: QResizeEvent):
        QWidget.resizeEvent(cast(QWidget, self), event)
        self._resize_timer.start(100)

    def showEvent(self: "AbstractClassSingleGalleryHostProtocol", event):
        super().showEvent(event)  # type: ignore[safe-super]
        self._on_layout_change()

    @Slot()
    def _on_layout_change(self: "AbstractClassSingleGalleryHostProtocol"):
        self._connect_scroll_zoom()
        if self.gallery_scroll_area and self.gallery_layout:
            # Shared Calculation
            new_cols = self.common_calculate_columns(
                self.gallery_scroll_area, self.approx_item_width
            )

            if new_cols != self._current_cols:
                self._current_cols = new_cols
                # Shared Reflow
                self.common_reflow_layout(self.gallery_layout, new_cols)

    def _perform_search(self: "AbstractClassSingleGalleryHostProtocol"):
        query = self.search_input.text()
        filtered = self.common_filter_string_list(self.master_image_paths, query)
        self.gallery_image_paths = filtered
        self.current_page = 0
        self.refresh_gallery_view()

    def jump_to_path(self: "AbstractClassSingleGalleryHostProtocol", path: str) -> bool:
        """§2.28 global search: isolate *path* by filtering the search box
        down to its exact basename. Returns False if not loaded here."""
        if path not in self.master_image_paths:
            return False
        self.search_input.blockSignals(True)
        self.search_input.setText(os.path.basename(path))
        self.search_input.blockSignals(False)
        self._perform_search()
        return True


__all__ = ["_GeometryEventsMixin"]
