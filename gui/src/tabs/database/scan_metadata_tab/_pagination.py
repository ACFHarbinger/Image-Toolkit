"""Pagination handlers for ``ScanMetadataTab``.

Pagination is dropped (virtual gallery renders all rows); the handlers are kept
so the base's pagination plumbing can't touch removed widgets.
"""

from __future__ import annotations


class _PaginationMixin:
    """No-op pagination overrides (the virtual gallery has no page cap)."""

    def _update_pagination_ui(self, is_found: bool, mode="scan"):
        """Pagination dropped; nothing to update."""


__all__ = ["_PaginationMixin"]
