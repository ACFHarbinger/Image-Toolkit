"""Inline rename, export-selection, and directory back/forward history.

Extracted from ``abstract_class_two_galleries.py`` -- pure code motion, no
logic change, to keep the file under the codebase's 500-code-line
convention (§5.17).
"""

from __future__ import annotations

import os
from typing import Optional, cast

from PySide6.QtWidgets import QFileDialog, QInputDialog, QMessageBox, QWidget

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..protos.abstract_class_two_galleries import AbstractClassTwoGalleriesHostProtocol


class _NavigationMixin:
    """F2 rename, Ctrl+E export, and §2.21A/D directory back/forward history."""

    # --- INLINE RENAME (GUI/UX §2.26B) ---
    def _rename_focused_file(self: "AbstractClassTwoGalleriesHostProtocol") -> None:
        """Rename the currently focused gallery item via F2 (GUI/UX §2.26B)."""
        idx = getattr(self, "_focused_found_idx", -1)
        page_paths = self.common_get_paginated_slice(
            self.master_found_files, self.found_current_page, self.found_page_size
        )
        if not (0 <= idx < len(page_paths)):
            return
        old_path = page_paths[idx]
        old_name = os.path.basename(old_path)
        stem, ext = os.path.splitext(old_name)

        new_stem, ok = QInputDialog.getText(
            cast(QWidget, self), "Rename File", "New name (no extension):", text=stem
        )
        if not ok or not new_stem.strip() or new_stem.strip() == stem:
            return

        new_stem = new_stem.strip()
        # Sanitise: remove characters illegal on common filesystems
        for ch in r'\/:*?"<>|':
            new_stem = new_stem.replace(ch, "_")

        new_path = os.path.join(os.path.dirname(old_path), new_stem + ext)
        if os.path.exists(new_path):
            QMessageBox.warning(
                cast(QWidget, self), "Rename", f"A file named '{new_stem + ext}' already exists."
            )
            return

        try:
            os.rename(old_path, new_path)
        except OSError as exc:
            QMessageBox.critical(cast(QWidget, self), "Rename Error", str(exc))
            return

        # Update all in-memory path lists and the label map
        self._replace_path_in_lists(old_path, new_path)

    def _replace_path_in_lists(self: "AbstractClassTwoGalleriesHostProtocol", old_path: str, new_path: str) -> None:
        """Swap *old_path* → *new_path* across found_files, master_found_files,
        selected_files, and path_to_label_map after a rename."""
        for lst in (self.found_files, self.master_found_files, self.selected_files):
            try:
                idx = lst.index(old_path)
                lst[idx] = new_path
            except ValueError:
                pass
        if old_path in self.path_to_label_map:
            widget = self.path_to_label_map.pop(old_path)
            self.path_to_label_map[new_path] = widget
            if hasattr(widget, "path"):
                widget.path = new_path  # pyrefly: ignore [missing-attribute]
            if hasattr(widget, "file_path"):
                widget.file_path = new_path  # pyrefly: ignore [missing-attribute]
            if hasattr(widget, "setToolTip"):
                widget.setToolTip(os.path.basename(new_path))

    # --- EXPORT SELECTION (GUI/UX §2.19A) ---
    def _export_selection_as_paths(self: "AbstractClassTwoGalleriesHostProtocol") -> None:
        """Write the currently selected file paths to a user-chosen TXT file (Ctrl+E)."""
        paths = self.selected_files or self.found_files
        if not paths:
            self._show_status("Nothing to export — gallery is empty.")
            return
        dest, _ = QFileDialog.getSaveFileName(
            cast(QWidget, self),
            "Export File Paths",
            "",
            "Text files (*.txt);;CSV files (*.csv);;All files (*.*)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if not dest:
            return
        try:
            with open(dest, "w", encoding="utf-8") as fh:
                fh.write("\n".join(paths))
            self._show_status(f"Exported {len(paths)} paths → {os.path.basename(dest)}")
        except OSError as exc:
            QMessageBox.critical(cast(QWidget, self), "Export Error", str(exc))

    # --- DIRECTORY NAVIGATION (GUI/UX §2.21A/D) ---
    def _navigate_to_dir(self: "AbstractClassTwoGalleriesHostProtocol", path: str) -> None:
        """Subclasses override to load *path* as the active gallery directory."""

    def _push_dir_history(self: "AbstractClassTwoGalleriesHostProtocol", path: str) -> None:
        """Call this before loading a new directory to push the current one to history."""
        if not path:
            return
        current = self.last_browsed_dir
        if current and (not self._dir_back_stack or self._dir_back_stack[-1] != current):
            self._dir_back_stack.append(current)
        self._dir_forward_stack.clear()

    def _dir_go_back(self: "AbstractClassTwoGalleriesHostProtocol") -> Optional[str]:
        """Return the previous directory, or None if no history."""
        if not self._dir_back_stack:
            return None
        prev = self._dir_back_stack.pop()
        self._dir_forward_stack.append(self.last_browsed_dir)
        return prev

    def _dir_go_forward(self: "AbstractClassTwoGalleriesHostProtocol") -> Optional[str]:
        """Return the next directory from the forward stack, or None."""
        if not self._dir_forward_stack:
            return None
        nxt = self._dir_forward_stack.pop()
        self._dir_back_stack.append(self.last_browsed_dir)
        return nxt


__all__ = ["_NavigationMixin"]
