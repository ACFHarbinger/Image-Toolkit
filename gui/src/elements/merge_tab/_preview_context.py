"""Full-image preview + right-click context menu for ``MergeTab``.

Extracted from ``merge_tab.py`` -- pure code motion, no logic change
(see ``_ui_config.py``'s docstring).
"""

from __future__ import annotations

import contextlib
import os

from PySide6.QtCore import QPoint, Qt, Slot
from PySide6.QtGui import QAction, QImage
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox
from send2trash import send2trash  # pyrefly: ignore [untyped-import]

from ...windows import ImagePreviewWindow


class _PreviewContextMixin:
    """Full-size preview window + right-click Copy/Toggle/Delete menu."""

    @Slot(str)
    def handle_full_image_preview(self, image_path: str):
        target_list = (
            list(self.gallery_image_paths) if self.gallery_image_paths else [image_path]
        )
        if image_path not in target_list:
            target_list.append(image_path)
        try:
            start_index = target_list.index(image_path)
        except ValueError:
            start_index = 0

        window = ImagePreviewWindow(
            image_path=image_path,
            db_tab_ref=None,
            parent=self,
            all_paths=target_list,
            start_index=start_index,
        )
        window.path_changed.connect(self.update_preview_highlight)
        window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        window.show()
        self.open_preview_windows.append(window)

    @Slot(QPoint, str)
    def show_image_context_menu(self, global_pos: QPoint, path: str):
        menu = QMenu(self)

        view_action = QAction("View Full Size Preview", self)
        view_action.triggered.connect(lambda: self.handle_full_image_preview(path))
        menu.addAction(view_action)
        menu.addSeparator()

        copy_action = QAction("Copy Image to Clipboard", self)
        copy_action.triggered.connect(lambda: self._copy_image_path_to_clipboard(path))
        menu.addAction(copy_action)
        menu.addSeparator()

        is_selected = path in self.selected_files
        toggle_text = (
            "Remove from Canvas (Deselect)" if is_selected else "Add to Canvas (Select)"
        )
        toggle_action = QAction(toggle_text, self)
        toggle_action.triggered.connect(lambda: self.toggle_selection(path))
        menu.addAction(toggle_action)
        menu.addSeparator()

        delete_action = QAction("Delete Image File (Permanent)", self)
        delete_action.triggered.connect(lambda: self.handle_delete_image(path))
        menu.addAction(delete_action)
        menu.exec(global_pos)

    def _copy_image_path_to_clipboard(self, path: str):
        if os.path.exists(path):
            try:
                img = QImage(path)
                if not img.isNull():
                    QApplication.clipboard().setImage(img)
                    self.status_label.setText(
                        f"Copied image to clipboard: {os.path.basename(path)}"
                    )
                else:
                    QMessageBox.warning(
                        self, "Copy Error", "Failed to load image for copying."
                    )
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Copy failed: {e}")

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

                for lst in (
                    self.gallery_image_paths,
                    self.master_image_paths,
                    self.selected_files,
                ):
                    with contextlib.suppress(ValueError, AttributeError):
                        lst.remove(path)

                self.canvas_widget.remove_item(path)
                if self.direction.currentText() != "canvas":
                    self._refresh_queue_gallery()

                widget = self.path_to_card_widget.pop(path, None)
                if widget:
                    widget.deleteLater()

                self.on_selection_changed()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))


__all__ = ["_PreviewContextMixin"]
