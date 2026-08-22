"""Full-size preview, right-click context menu, and file deletion.

Extracted from ``format_subtab.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

import os
import platform
import subprocess

from backend.src.constants import SUPPORTED_VIDEO_FORMATS
from PySide6.QtCore import QPoint, Qt, Slot
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QMessageBox
from send2trash import send2trash  # pyrefly: ignore [untyped-import]

from ....utils.sort_utils import natural_sort_key
from ....windows import ImagePreviewWindow


class _PreviewContextMixin:
    """Full preview windows, the per-card context menu, and delete-file handling."""

    @Slot(str)
    def handle_full_image_preview(self, image_path: str):
        if not os.path.exists(image_path):
            return

        if image_path.lower().endswith(tuple(SUPPORTED_VIDEO_FORMATS)):
            try:
                if platform.system() == "Windows":
                    os.startfile(image_path) # pyrefly: ignore [missing-attribute]
                elif platform.system() == "Linux":
                    subprocess.Popen(
                        ["xdg-open", image_path],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                else:
                    subprocess.Popen(
                        ["open", image_path],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
            except Exception as e:
                QMessageBox.warning(
                    self, "Video Error", f"Could not launch video player: {e}"
                )
            return

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

        try:
            start_index = target_list.index(image_path)
        except ValueError:
            start_index = 0

        for win in list(self.open_preview_windows):
            try:
                if isinstance(win, ImagePreviewWindow) and win.image_path == image_path:
                    win.activateWindow()
                    return
            except RuntimeError:
                if win in self.open_preview_windows:
                    self.open_preview_windows.remove(win)

        preview = ImagePreviewWindow(
            image_path=image_path,
            db_tab_ref=None,
            parent=self,
            all_paths=target_list,
            start_index=start_index,
        )
        preview.path_changed.connect(self.update_preview_highlight)
        preview.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        preview.show()
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
                for win in list(self.open_preview_windows):
                    try:
                        if hasattr(win, "image_path") and win.image_path == path:
                            win.close()
                    except RuntimeError:
                        if win in self.open_preview_windows:
                            self.open_preview_windows.remove(win)

            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))


__all__ = ["_PreviewContextMixin"]
