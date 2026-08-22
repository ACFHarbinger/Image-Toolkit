"""Gallery surface + selection hook for SearchTab.

The found/selected card grids are replaced by a ``VirtualDualGallery``
(GUI/UX §2.1 Option A); these overrides feed the base's ``found_files`` /
``selected_files`` lists into the dual and map selection changes back.
"""

from __future__ import annotations

from PySide6.QtCore import Slot
from PySide6.QtWidgets import QLabel

from ....components import DraggableLabel


class _GalleryCardsMixin:
    """Gallery refresh/selection mapping onto the virtual dual gallery."""

    def create_gallery_label(self, path: str, size: int) -> QLabel:
        return DraggableLabel(
            path, size, selection_provider=lambda: self.selected_files
        )

    def _sync_selection_from_dual(self):
        self.selected_files = list(self.dual.selected_paths())
        self.on_selection_changed()

    def refresh_found_gallery(self):
        self.dual.set_found_paths(self.found_files)

    def refresh_selected_panel(self):
        self.dual.set_selected_paths(self.selected_files)

    def toggle_selection(self, path: str):
        self.dual.toggle_selection(path)

    def clear_galleries(self, clear_data=True):
        if clear_data:
            self.found_files = []
            self.selected_files = []
        self.dual.clear()
        self.cancel_loading()
        self.on_selection_changed()

    @Slot()
    def select_all_results(self):
        self.select_all_items()

    @Slot()
    def deselect_all_results(self):
        self.deselect_all_items()


__all__ = ["_GalleryCardsMixin"]
