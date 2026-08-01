"""Registry-driven keyboard shortcuts and arrow-key gallery navigation.

Extracted from ``abstract_class_two_galleries.py`` -- pure code motion, no
logic change (see ``_navigation.py``'s docstring).
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt


class _KeyboardNavMixin:
    """§2.29 registry-driven shortcuts and arrow-key focus navigation/preview."""

    # --- KEYBOARD SHORTCUTS (GUI/UX §2.29 — registry-driven) ---
    def keyPressEvent(self, event: QEvent):
        from ...utils.manager.shortcut_manager import get_registry

        reg = get_registry()
        key = event.key()  # pyrefly: ignore [missing-attribute]
        if reg.matches(event, "gallery.select_all"):  # pyrefly: ignore [bad-argument-type]
            self.select_all_items()
            event.accept()
        elif reg.matches(event, "gallery.deselect_all"):  # pyrefly: ignore [bad-argument-type]
            self.deselect_all_items()
            event.accept()
        elif reg.matches(event, "gallery.nav_left"):  # pyrefly: ignore [bad-argument-type]
            self._navigate_gallery(Qt.Key.Key_Left)
            event.accept()
        elif reg.matches(event, "gallery.nav_right"):  # pyrefly: ignore [bad-argument-type]
            self._navigate_gallery(Qt.Key.Key_Right)
            event.accept()
        elif reg.matches(event, "gallery.nav_up"):  # pyrefly: ignore [bad-argument-type]
            self._navigate_gallery(Qt.Key.Key_Up)
            event.accept()
        elif reg.matches(event, "gallery.nav_down"):  # pyrefly: ignore [bad-argument-type]
            self._navigate_gallery(Qt.Key.Key_Down)
            event.accept()
        elif reg.matches(event, "gallery.open_preview") or key == Qt.Key.Key_Space:  # pyrefly: ignore [bad-argument-type]
            self._preview_focused_item()
            event.accept()
        elif reg.matches(event, "gallery.export_paths"):  # pyrefly: ignore [bad-argument-type]
            self._export_selection_as_paths()
            event.accept()
        elif reg.matches(event, "gallery.copy_to_folder"):  # pyrefly: ignore [bad-argument-type]
            self._copy_selection_to_folder()
            event.accept()
        elif reg.matches(event, "gallery.rename"):  # pyrefly: ignore [bad-argument-type]
            self._rename_focused_file()
            event.accept()
        elif reg.matches(event, "gallery.nav_back"):  # pyrefly: ignore [bad-argument-type]
            prev = self._dir_go_back()
            if prev:
                self._navigate_to_dir(prev)
            event.accept()
        elif reg.matches(event, "gallery.nav_forward"):  # pyrefly: ignore [bad-argument-type]
            nxt = self._dir_go_forward()
            if nxt:
                self._navigate_to_dir(nxt)
            event.accept()
        else:
            super().keyPressEvent(event)  # pyrefly: ignore [bad-argument-type]

    # --- GALLERY NAVIGATION (GUI/UX §2.3A) ---
    def _navigate_gallery(self, key) -> None:
        """Move the gallery focus cursor with arrow keys."""
        page_paths = self.common_get_paginated_slice(
            self.master_found_files, self.found_current_page, self.found_page_size
        )
        if not page_paths:
            return

        cols = max(1, self._current_found_cols)
        idx = getattr(self, "_focused_found_idx", -1)

        if key == Qt.Key.Key_Right:
            idx = min(idx + 1, len(page_paths) - 1)
        elif key == Qt.Key.Key_Left:
            idx = max(0, idx - 1)
        elif key == Qt.Key.Key_Down:
            idx = min(idx + cols, len(page_paths) - 1)
        elif key == Qt.Key.Key_Up:
            idx = max(0, idx - cols)

        # Bootstrap: if nothing focused yet, start at 0
        if idx < 0:
            idx = 0

        self._focused_found_idx = idx
        self._highlight_focused(page_paths, idx)

    def _highlight_focused(self, page_paths: list, idx: int) -> None:
        """Visually highlight the focused thumbnail and scroll it into view."""
        target_path = page_paths[idx] if 0 <= idx < len(page_paths) else None
        if target_path is None:
            return
        widget = self.path_to_label_map.get(target_path)
        if widget:
            widget.setFocus()
            if self.found_gallery_scroll:
                self.found_gallery_scroll.ensureWidgetVisible(widget)

    def _preview_focused_item(self) -> None:
        """Open a preview for the currently focused gallery item.

        Delegates to the concrete tab by emitting `path_double_clicked` on the
        focused label widget, which concrete tabs already connect to their preview handler.
        """
        idx = getattr(self, "_focused_found_idx", -1)
        page_paths = self.common_get_paginated_slice(
            self.master_found_files, self.found_current_page, self.found_page_size
        )
        if 0 <= idx < len(page_paths):
            path = page_paths[idx]
            widget = self.path_to_label_map.get(path)
            if widget and hasattr(widget, "path_double_clicked"):
                widget.path_double_clicked.emit(path)


__all__ = ["_KeyboardNavMixin"]
