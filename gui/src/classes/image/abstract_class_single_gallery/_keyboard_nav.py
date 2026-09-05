"""Arrow-key gallery navigation and the registry-driven keyPressEvent (§2.3A / §2.29).

Extracted from ``abstract_class_single_gallery.py`` -- pure code motion, no
logic change.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtGui import QKeyEvent

if TYPE_CHECKING:
    from ..protos.abstract_class_single_gallery import AbstractClassSingleGalleryHostProtocol


class _KeyboardNavMixin:
    """Arrow-key focus movement and the top-level keyPressEvent dispatcher."""

    def _navigate_gallery(self: "AbstractClassSingleGalleryHostProtocol", key) -> None:
        """Move the gallery focus cursor with arrow keys (§2.3A)."""
        from PySide6.QtCore import Qt as _Qt
        page_paths = self.common_get_paginated_slice(
            self.gallery_image_paths, self.current_page, self.page_size
        )
        if not page_paths:
            return
        cols = max(1, self._current_cols)
        idx = self._focused_idx
        if key == _Qt.Key.Key_Right:
            idx = min(idx + 1, len(page_paths) - 1)
        elif key == _Qt.Key.Key_Left:
            idx = max(0, idx - 1)
        elif key == _Qt.Key.Key_Down:
            idx = min(idx + cols, len(page_paths) - 1)
        elif key == _Qt.Key.Key_Up:
            idx = max(0, idx - cols)
        if idx < 0:
            idx = 0
        self._focused_idx = idx
        self._highlight_focused(page_paths, idx)

    def _highlight_focused(self: "AbstractClassSingleGalleryHostProtocol", page_paths: list, idx: int) -> None:
        target_path = page_paths[idx] if 0 <= idx < len(page_paths) else None
        if target_path is None:
            return
        widget = self.path_to_card_widget.get(target_path)
        if widget:
            widget.setFocus()
            if self.gallery_scroll_area:
                self.gallery_scroll_area.ensureWidgetVisible(widget)

    def _preview_focused_item(self: "AbstractClassSingleGalleryHostProtocol") -> None:
        """Open a preview for the keyboard-focused gallery item."""
        page_paths = self.common_get_paginated_slice(
            self.gallery_image_paths, self.current_page, self.page_size
        )
        idx = self._focused_idx
        if 0 <= idx < len(page_paths):
            path = page_paths[idx]
            widget = self.path_to_card_widget.get(path)
            if widget and hasattr(widget, "path_double_clicked"):
                widget.path_double_clicked.emit(path)

    # --- KEYBOARD SHORTCUTS (GUI/UX §2.29 — registry-driven) ---
    def keyPressEvent(self: "AbstractClassSingleGalleryHostProtocol", event: QKeyEvent):
        from PySide6.QtCore import Qt as _Qt

        from ....utils.manager.shortcut_manager import get_registry

        reg = get_registry()
        if reg.matches(event, "gallery.select_all"): # pyrefly: ignore [bad-argument-type]
            self.select_all_items()
            event.accept()
        elif reg.matches(event, "gallery.deselect_all"): # pyrefly: ignore [bad-argument-type]
            self.deselect_all_items()
            event.accept()
        elif reg.matches(event, "gallery.export_paths"): # pyrefly: ignore [bad-argument-type]
            self._export_selection_as_paths()
            event.accept()
        elif reg.matches(event, "gallery.copy_to_folder"): # pyrefly: ignore [bad-argument-type]
            self._copy_selection_to_folder()
            event.accept()
        elif reg.matches(event, "gallery.nav_left"): # pyrefly: ignore [bad-argument-type]
            self._navigate_gallery(_Qt.Key.Key_Left)
            event.accept()
        elif reg.matches(event, "gallery.nav_right"): # pyrefly: ignore [bad-argument-type]
            self._navigate_gallery(_Qt.Key.Key_Right)
            event.accept()
        elif reg.matches(event, "gallery.nav_up"): # pyrefly: ignore [bad-argument-type]
            self._navigate_gallery(_Qt.Key.Key_Up)
            event.accept()
        elif reg.matches(event, "gallery.nav_down"): # pyrefly: ignore [bad-argument-type]
            self._navigate_gallery(_Qt.Key.Key_Down)
            event.accept()
        elif reg.matches(event, "gallery.open_preview") or event.key() == _Qt.Key.Key_Space: # pyrefly: ignore [bad-argument-type, missing-attribute]
            self._preview_focused_item()
            event.accept()
        elif reg.matches(event, "gallery.rename"): # pyrefly: ignore [bad-argument-type]
            self._rename_selected_file()
            event.accept()
        else:
            super().keyPressEvent(event)  # type: ignore[misc,safe-super] # pyrefly: ignore [bad-argument-type]


__all__ = ["_KeyboardNavMixin"]
