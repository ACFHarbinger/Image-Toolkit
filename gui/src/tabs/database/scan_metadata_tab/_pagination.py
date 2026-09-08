"""Pagination handlers for ``ScanMetadataTab``.

Pagination is dropped (virtual gallery renders all rows); the handlers are kept
so the base's pagination plumbing can't touch removed widgets.
"""

from __future__ import annotations

from ._tab_bound import TabBoundController


class ScanPaginationController(TabBoundController):
    """No-op pagination overrides (the virtual gallery has no page cap)."""

    def _update_pagination_ui(self, is_found: bool, mode="scan"):
        """Pagination dropped; nothing to update."""


_PaginationMixin = ScanPaginationController  # COMPAT(ui-arch-23): remove after callers drop the mixin name

__all__ = ["ScanPaginationController", "_PaginationMixin"]
