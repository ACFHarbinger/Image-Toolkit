"""Keyboard shortcuts (Ctrl+A/Ctrl+D) for ``ScanMetadataTab``.

Extracted from ``scan_metadata_tab.py`` -- pure code motion, no logic
change (see ``_ui_builder.py``'s docstring).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel


class _KeyboardSelectionMixin:
    """Ctrl+A (select all visible) / Ctrl+D (deselect all) handling."""

    def keyPressEvent(self, event):
        """Handle keyboard shortcuts for selection."""
        # CTRL + A: Select All (Visible on Page)
        if (
            event.modifiers() & Qt.KeyboardModifier.ControlModifier
            and event.key() == Qt.Key.Key_A
        ):
            self._select_all_images()
            event.accept()
            return

        # CTRL + D: Deselect All
        if (
            event.modifiers() & Qt.KeyboardModifier.ControlModifier
            and event.key() == Qt.Key.Key_D
        ):
            self._deselect_all_images()
            event.accept()
            return

        super().keyPressEvent(event)

    def _select_all_images(self):
        """Selects all images currently visible in the scan gallery page."""
        visible_paths = list(self.path_to_wrapper_map.keys())

        if not visible_paths:
            return

        self.scan_thumbnail_widget.setUpdatesEnabled(False)
        self.selected_image_paths.update(visible_paths)

        for path in visible_paths:
            if path in self.path_to_wrapper_map:
                wrapper = self.path_to_wrapper_map[path]
                inner_label = wrapper.findChild(QLabel)
                is_in_db = wrapper.property("in_db")
                if inner_label:
                    self._update_card_style(
                        inner_label, is_selected=True, is_in_db=is_in_db
                    )

        self.scan_thumbnail_widget.setUpdatesEnabled(True)
        self.populate_selected_images_gallery()
        self.update_button_states(connected=(self.db_tab_ref.db is not None))

    def _deselect_all_images(self):
        """Deselects all currently selected images."""
        if not self.selected_image_paths:
            return

        self.scan_thumbnail_widget.setUpdatesEnabled(False)

        # Update visual style in Top Gallery (Reset to unselected)
        for path in self.selected_image_paths:
            if path in self.path_to_wrapper_map:
                wrapper = self.path_to_wrapper_map[path]
                inner_label = wrapper.findChild(QLabel)
                is_in_db = wrapper.property("in_db")
                if inner_label:
                    self._update_card_style(
                        inner_label, is_selected=False, is_in_db=is_in_db
                    )

        self.selected_image_paths.clear()

        self.scan_thumbnail_widget.setUpdatesEnabled(True)
        self.populate_selected_images_gallery()
        self.update_button_states(connected=(self.db_tab_ref.db is not None))


__all__ = ["_KeyboardSelectionMixin"]
