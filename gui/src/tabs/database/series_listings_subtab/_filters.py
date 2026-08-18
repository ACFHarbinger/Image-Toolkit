"""Search/type/status/sort combo change handlers.

Extracted from ``series_listings_subtab.py`` -- pure code motion, no logic
change.
"""

from __future__ import annotations

from PySide6.QtCore import Slot


class _FiltersMixin:
    """Wires the search box and filter/sort combos to gallery rebuilds."""

    @Slot(str)
    def _on_search(self, text: str):
        self._search_query = text
        self._rebuild_gallery()

    @Slot(str)
    def _on_type_filter(self, text: str):
        self._filter_type = text
        self._rebuild_gallery()

    @Slot(str)
    def _on_status_filter(self, text: str):
        self._filter_status = text
        self._rebuild_gallery()

    @Slot(str)
    def _on_sort_changed(self, text: str):
        self._rebuild_gallery()


__all__ = ["_FiltersMixin"]
