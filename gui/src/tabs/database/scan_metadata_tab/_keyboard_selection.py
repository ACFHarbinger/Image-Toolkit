"""Keyboard shortcuts (Ctrl+A/Ctrl+D) for ``ScanMetadataTab``.

Extracted from ``scan_metadata_tab.py`` -- pure code motion, no logic
change (see ``_ui_builder.py``'s docstring).
"""

from __future__ import annotations

from PySide6.QtCore import Qt


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
        """Selects all images currently visible in the found gallery."""
        self.dual.select_all()
        self._sync_selection_from_dual()

    def _deselect_all_images(self):
        """Deselects all currently selected images."""
        self.dual.deselect_all()
        self._sync_selection_from_dual()


__all__ = ["_KeyboardSelectionMixin"]
