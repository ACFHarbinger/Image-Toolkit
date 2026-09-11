"""Search/type/role combo change handlers.

Extracted from ``entity_listings_subtab.py`` -- pure code motion, no logic
change.
"""

from __future__ import annotations

from PySide6.QtCore import Slot

from ._tab_bound import TabBoundController


class EntityListingsFiltersController(TabBoundController):
    """Wires the search box and filter combos to gallery rebuilds."""

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
    def _on_role_filter(self, text: str):
        self._filter_role = text
        self._listing_page = 0
        self._rebuild_gallery()


_FiltersMixin = EntityListingsFiltersController  # COMPAT(ui-arch-23): remove after callers drop mixin names

__all__ = ["EntityListingsFiltersController", "_FiltersMixin"]
