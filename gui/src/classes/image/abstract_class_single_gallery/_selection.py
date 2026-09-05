"""Selection toggling (select-all/deselect-all/toggle/is-selected).

Extracted from ``abstract_class_single_gallery.py`` -- pure code motion, no
logic change.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Slot
from PySide6.QtWidgets import QLabel

if TYPE_CHECKING:
    from ..protos.abstract_class_single_gallery import AbstractClassSingleGalleryHostProtocol


class _SelectionMixin:
    """Selects/deselects gallery items and reports selection state."""

    @Slot()
    def select_all_items(self: "AbstractClassSingleGalleryHostProtocol"):
        """Selects all items currently visible on the current page."""
        paginated_paths = self.common_get_paginated_slice(
            self.gallery_image_paths, self.current_page, self.page_size
        )

        changed = False
        for path in paginated_paths:
            if path not in self.selected_files:
                self.selected_files.append(path)
                changed = True

        if changed:
            # Update styles for all visible widgets
            for path in paginated_paths:
                widget = self.path_to_card_widget.get(path)
                if widget:
                    self.update_card_style(widget, True)
            self.on_selection_changed()

    @Slot()
    def deselect_all_items(self: "AbstractClassSingleGalleryHostProtocol"):
        """Clears the selection."""
        if self.selected_files:
            affected_paths = list(self.selected_files)
            self.selected_files.clear()
            # Update styles for visible widgets that were selected
            paginated_paths = self.common_get_paginated_slice(
                self.gallery_image_paths, self.current_page, self.page_size
            )
            for path in paginated_paths:
                if path in affected_paths:
                    widget = self.path_to_card_widget.get(path)
                    if widget:
                        self.update_card_style(widget, False)
            self.on_selection_changed()

    @Slot()
    def invert_selection(self: "AbstractClassSingleGalleryHostProtocol"):
        """Inverts the selection of currently visible items (§2.4E)."""
        if hasattr(self, "gallery") and hasattr(self.gallery, "invert_selection"):
            self.gallery.invert_selection()
            return

        paginated_paths = self.common_get_paginated_slice(
            self.gallery_image_paths, self.current_page, self.page_size
        )
        new_selected = [p for p in self.selected_files if p not in paginated_paths]
        for path in paginated_paths:
            if path not in self.selected_files:
                new_selected.append(path)
        self.selected_files = new_selected
        for path in paginated_paths:
            widget = self.path_to_card_widget.get(path)
            if widget:
                self.update_card_style(widget, path in self.selected_files)
        self.on_selection_changed()


    @Slot(str)
    def toggle_selection(self: "AbstractClassSingleGalleryHostProtocol", path: str):
        """Toggle the selection state of a gallery item."""
        if path in self.selected_files:
            self.selected_files.remove(path)
            selected = False
        else:
            self.selected_files.append(path)
            selected = True

        widget = self.path_to_card_widget.get(path)
        if widget:
            label = widget.findChild(QLabel)
            if label:
                self.update_card_style(widget, selected)

        self.on_selection_changed()

    def is_path_selected(self: "AbstractClassSingleGalleryHostProtocol", path: str) -> bool:
        """Returns True if the given path is currently selected."""
        return path in self.selected_files


__all__ = ["_SelectionMixin"]
