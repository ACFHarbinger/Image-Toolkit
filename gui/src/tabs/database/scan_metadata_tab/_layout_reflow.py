"""Resize/show-event grid reflow for ``ScanMetadataTab``.

Extracted from ``scan_metadata_tab.py`` -- pure code motion, no logic
change (see ``_ui_builder.py``'s docstring).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import QGridLayout, QLabel, QScrollArea


class _LayoutReflowMixin:
    """Recompute gallery column counts on resize/show and repack widgets."""

    def resizeEvent(self, event: QResizeEvent):
        """Trigger grid reflow and lazy load check when window is resized."""
        self._resize_timer.start(150)  # existing debounce for layout repack
        self._lazy_load_timer.start(
            200
        )  # trigger visibility check slightly after layout repack
        super().resizeEvent(event)

    def showEvent(self, event):
        """Trigger grid reflow when tab is shown."""
        self._repack_galleries()
        super().showEvent(event)

    def _repack_galleries(self):
        """Re-calculates columns and moves widgets for all galleries."""
        self._repack_specific_layout(self.scan_thumbnail_layout, self.scan_scroll_area)
        self._repack_specific_layout(
            self.selected_grid_layout, self.selected_images_area
        )

    def _repack_specific_layout(self, layout: QGridLayout, scroll_area: QScrollArea):
        """Extracts all items and re-adds them based on new width."""
        width = scroll_area.viewport().width()
        if width <= 0:
            width = scroll_area.width()
        if width <= 0:
            return

        columns = max(1, width // self.approx_item_width)

        # 1. Extract all widgets from layout
        items = []
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                items.append(item.widget())

        # 2. Re-add them in the new grid configuration
        for idx, widget in enumerate(items):
            row = idx // columns
            col = idx % columns

            align = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
            if isinstance(widget, QLabel) and (
                "No supported images" in widget.text()
                or "No scanned images" in widget.text()
            ):
                align = Qt.AlignmentFlag.AlignCenter
                layout.addWidget(widget, 0, 0, 1, columns, align)
                return

            layout.addWidget(widget, row, col, align)  # pyrefly: ignore [bad-argument-type]


__all__ = ["_LayoutReflowMixin"]
