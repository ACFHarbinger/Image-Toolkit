"""Resize/show-event handling for ``ScanMetadataTab``.

The virtual gallery re-lays-out itself (QListView wrapping), so the old grid
reflow is a no-op. Extracted from ``scan_metadata_tab.py``.
"""

from __future__ import annotations

from PySide6.QtGui import QResizeEvent


class _LayoutReflowMixin:
    """No-op reflow overrides (VirtualGallery handles its own layout)."""

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)

    def showEvent(self, event):
        super().showEvent(event)

    def _repack_galleries(self):
        """Virtual gallery re-lays-out itself on resize; nothing to repack."""

    def _repack_specific_layout(self, layout, scroll_area):
        """Kept for API compatibility; never called now that grids are gone."""


__all__ = ["_LayoutReflowMixin"]
