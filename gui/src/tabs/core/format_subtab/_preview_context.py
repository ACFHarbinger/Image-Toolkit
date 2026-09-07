"""Full-size preview, right-click context menu, and file deletion.

Extracted from ``format_subtab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

import os

from PySide6.QtCore import QPoint, Slot
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QMessageBox
from send2trash import send2trash  # pyrefly: ignore [untyped-import]

from ....services import PreviewContext, get_preview_service
from ....utils.sort_utils import natural_sort_key


class _PreviewContextMixin:
    """Full preview windows, the per-card context menu, and delete-file handling."""

    @Slot(str)
    def handle_full_image_preview(self, image_path: str):
        target_list = (
            self.found_files
            if hasattr(self, "found_files") and self.found_files
            else []
        )

        if image_path not in target_list:
            if hasattr(self, "selected_files") and image_path in self.selected_files:
                target_list = sorted(list(self.selected_files), key=natural_sort_key)
            else:
                target_list = [image_path]

        context = PreviewContext(
            path=image_path,
            items=target_list,
            parent=self,
            on_path_changed=getattr(self, "update_preview_highlight", None),
        )
        preview = get_preview_service().open_preview(context)
        if preview and hasattr(self, "open_preview_windows") and preview not in self.open_preview_windows:
            self.open_preview_windows.append(preview)

    @Slot(QPoint, str)
    def show_image_context_menu(self, global_pos: QPoint, path: str):
        menu = QMenu(self)

        view_action = QAction("View Full Size Preview", self)
        view_action.triggered.connect(lambda: self.handle_full_image_preview(path))
        menu.addAction(view_action)

        menu.addSeparator()

        is_selected = path in self.selected_files
        toggle_text = (
            "Deselect image from conversion"
            if is_selected
            else "Select image to convert"
        )
        toggle_action = QAction(toggle_text, self)
        toggle_action.triggered.connect(lambda: self.toggle_selection(path))
        menu.addAction(toggle_action)

        menu.addSeparator()

        delete_action = QAction("🗑️ Delete Image File (Permanent)", self)
        delete_action.triggered.connect(lambda: self.handle_delete_image(path))
        menu.addAction(delete_action)

        menu.exec(global_pos)

    def handle_delete_image(self, path: str):
        prefs = {}
        main_win = self.window()
        if main_win and hasattr(main_win, "cached_creds"):
            prefs = main_win.cached_creds.get("preferences", {})
        send_to_trash_enabled = prefs.get("send_to_trash", True)
        action_name = "Trash" if send_to_trash_enabled else "Permanent Delete"

        if (
            QMessageBox.question(
                self,
                f"Confirm {action_name}",
                f"Move {os.path.basename(path)} to {action_name}?",
            )
            == QMessageBox.StandardButton.Yes
        ):
            try:
                if send_to_trash_enabled:
                    send2trash(path)
                else:
                    os.remove(path)

                if hasattr(self, "found_files") and path in self.found_files:
                    self.found_files.remove(path)
                if hasattr(self, "selected_files") and path in self.selected_files:
                    self.selected_files.remove(path)

                self.refresh_found_gallery()
                self.refresh_selected_panel()
                self.on_selection_changed()

                # Also close any open preview for this file
                get_preview_service().close_preview(path)
                if hasattr(self, "open_preview_windows"):
                    self.open_preview_windows = [
                        w for w in self.open_preview_windows
                        if getattr(w, "image_path", None) != path
                    ]

            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))


__all__ = ["_PreviewContextMixin"]
