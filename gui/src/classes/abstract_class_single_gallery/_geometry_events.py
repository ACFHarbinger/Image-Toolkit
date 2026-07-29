"""Resize/show events, column-reflow, and the debounced search filter.

Extracted from ``abstract_class_single_gallery.py`` -- pure code motion, no
logic change.
"""

from __future__ import annotations

from PySide6.QtCore import Slot
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import QWidget


class _GeometryEventsMixin:
    """resizeEvent/showEvent/_on_layout_change and the search-debounce filter."""

    def resizeEvent(self, event: QResizeEvent):
        QWidget.resizeEvent(self, event)
        self._resize_timer.start(100)

    def showEvent(self, event):
        super().showEvent(event)
        self._on_layout_change()

    @Slot()
    def _on_layout_change(self):
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

    def _perform_search(self):
        query = self.search_input.text()
        filtered = self.common_filter_string_list(self.master_image_paths, query)
        self.gallery_image_paths = filtered
        self.current_page = 0
        self.refresh_gallery_view()


__all__ = ["_GeometryEventsMixin"]
