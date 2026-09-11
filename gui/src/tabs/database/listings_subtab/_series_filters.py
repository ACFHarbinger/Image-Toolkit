"""Search/type/status/sort combo change handlers.

Extracted from ``series_listings_subtab.py`` -- pure code motion, no logic
change.
"""

from __future__ import annotations

from PySide6.QtCore import Slot

from ._tab_bound import TabBoundController


class SeriesListingsFiltersController(TabBoundController):
    """Wires the search box and filter/sort combos to gallery rebuilds."""

    @Slot(str)
    def _on_search(self, text: str):
        self._search_query = text
        self._listing_page = 0
        self._rebuild_gallery()

    @Slot(str)
    def _on_type_filter(self, text: str):
        self._filter_type = text
        self._listing_page = 0
        self._rebuild_gallery()

    @Slot(str)
    def _on_status_filter(self, text: str):
        self._filter_status = text
        self._listing_page = 0
        self._rebuild_gallery()

    @Slot(str)
    def _on_sort_changed(self, text: str):
        self._listing_page = 0
        self._rebuild_gallery()


_FiltersMixin = SeriesListingsFiltersController  # COMPAT(ui-arch-23): remove after callers drop mixin names

__all__ = ["SeriesListingsFiltersController", "_FiltersMixin"]
