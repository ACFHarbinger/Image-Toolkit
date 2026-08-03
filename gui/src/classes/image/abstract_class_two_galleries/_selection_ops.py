"""Select-all/deselect-all, click/marquee toggle, and selection queries.

Extracted from ``abstract_class_two_galleries.py`` -- pure code motion, no
logic change (see ``_navigation.py``'s docstring).
"""

from __future__ import annotations

import contextlib

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import QApplication

from ....utils.sort_utils import natural_sort_key
from ...mixins import compute_reordered

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..protos.abstract_class_two_galleries import AbstractClassTwoGalleriesHostProtocol


class _SelectionOpsMixin:
    """Select-all/deselect-all, single-click toggle, and marquee selection."""

    @Slot()
    def select_all_items(self: "AbstractClassTwoGalleriesHostProtocol"):
        """Selects all items currently visible on the current page."""
        # Calculate the slice for the current page using the common helper
        current_page_paths = self.common_get_paginated_slice(
            self.found_files, self.found_current_page, self.found_page_size
        )

        changed = False
        for path in current_page_paths:
            if path not in self.selected_files:
                self.selected_files.append(path)
                changed = True

        if changed:
            self.refresh_selected_panel()
            self._update_found_card_styles()
            self.on_selection_changed()

    @Slot()
    def deselect_all_items(self: "AbstractClassTwoGalleriesHostProtocol"):
        """Clears the selection."""
        if self.selected_files:
            self.selected_files.clear()
            self.refresh_selected_panel()
            self._update_found_card_styles()
            self.on_selection_changed()

    def _update_found_card_styles(self: "AbstractClassTwoGalleriesHostProtocol"):
        """Helper to re-evaluate and apply style to all currently loaded/visible found cards."""
        for path, widget in self.path_to_label_map.items():
            if widget:
                is_selected = path in self.selected_files
                self.update_card_style(widget, is_selected)

    @Slot(str)
    def toggle_selection(self: "AbstractClassTwoGalleriesHostProtocol", path: str):
        try:
            index = self.selected_files.index(path)
            self.selected_files.pop(index)
            selected = False
        except ValueError:
            # Insertion order, not natural_sort_key -- lets the user
            # drag-reorder the Selected panel afterward (see
            # reorder_selected below); a forced sort would fight the user's
            # manual order on every subsequent toggle.
            self.selected_files.append(path)
            selected = True

        label = self.path_to_label_map.get(path)
        if label:
            with contextlib.suppress(RuntimeError):
                self.update_card_style(label, selected)

        self.refresh_selected_panel()
        self.on_selection_changed()

    def reorder_selected(self: "AbstractClassTwoGalleriesHostProtocol", dragged_path: str, target_path: str) -> None:
        """Drag-and-drop callback: move ``dragged_path`` to sit before ``target_path``."""
        self.selected_files = compute_reordered(
            self.selected_files, dragged_path, target_path
        )
        self.refresh_selected_panel()
        self.on_selection_changed()

    def handle_marquee_selection(self: "AbstractClassTwoGalleriesHostProtocol", paths_from_marquee: set, is_ctrl_pressed: bool):
        # Check for Shift modifier explicitly
        modifiers = QApplication.keyboardModifiers()
        is_shift_pressed = bool(modifiers & Qt.KeyboardModifier.ShiftModifier)

        ordered_current = self.selected_files.copy()
        paths_to_update = set()
        if is_ctrl_pressed:
            # Subtractive selection (CTRL): Remove items in marquee from selection
            for path in paths_from_marquee:
                if path in self.selected_files:
                    self.selected_files.remove(path)
                    paths_to_update.add(path)
        elif is_shift_pressed:
            # Additive selection (SHIFT): Keep current selection, add new items from marquee
            newly_added = [p for p in paths_from_marquee if p not in ordered_current]
            self.selected_files = sorted(ordered_current + newly_added, key=natural_sort_key)
            paths_to_update = set(newly_added)
        else:
            # Standard selection (No Modifiers):
            # Replaces selection with what is currently in the marquee.
            paths_to_update = set(self.selected_files).union(paths_from_marquee)
            self.selected_files = sorted(list(paths_from_marquee), key=natural_sort_key)

        for path in paths_to_update:
            if path in self.path_to_label_map:
                widget = self.path_to_label_map[path]
                self.update_card_style(widget, path in self.selected_files)

        self.refresh_selected_panel()
        self.on_selection_changed()

    def is_path_selected(self: "AbstractClassTwoGalleriesHostProtocol", path: str) -> bool:
        """Returns True if the given path is currently selected."""
        return path in self.selected_files


__all__ = ["_SelectionOpsMixin"]
