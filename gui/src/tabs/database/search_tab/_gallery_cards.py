"""Gallery card draggable label factory and selection slots for SearchTab.

Card creation, pixmap updating, and styling are promoted to AbstractClassTwoGalleries (§Issue 446).
"""

from __future__ import annotations

from PySide6.QtCore import Slot
from PySide6.QtWidgets import QLabel

from ....components import DraggableLabel


class _GalleryCardsMixin:
    """Provides DraggableLabel creation and select/deselect all slots for SearchTab."""

    def create_gallery_label(self, path: str, size: int) -> QLabel:
        return DraggableLabel(
            path, size, selection_provider=lambda: self.selected_files
        )

    @Slot()
    def select_all_results(self):
        self.select_all_items()

    @Slot()
    def deselect_all_results(self):
        self.deselect_all_items()


__all__ = ["_GalleryCardsMixin"]
