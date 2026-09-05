"""Right-click context menu, image properties, delete, and single-image preview.

Extracted from ``scan_metadata_tab.py`` -- pure code motion, no logic
change (see ``_ui_builder.py``'s docstring).
"""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QPoint, Qt, Slot
from PySide6.QtGui import QAction, QPixmap
from PySide6.QtWidgets import QMenu, QMessageBox
from send2trash import send2trash  # pyrefly: ignore [untyped-import]

from ....windows import ImagePreviewWindow


class _ContextMenuActionsMixin:
    """Right-click menu, DB/file properties dialog, delete, and preview window."""

    @Slot(QPoint, str)
    def show_image_context_menu(self, global_pos: QPoint, path: str):
        menu = QMenu(self)
        view_props_action = QAction("🖼️ View Properties (File/DB)", self)
        view_props_action.triggered.connect(lambda: self._view_image_properties(path))
        menu.addAction(view_props_action)
        menu.addSeparator()
        view_action = QAction("View Full Size Preview", self)
        view_action.triggered.connect(lambda: self._view_single_image_preview(path))
        menu.addAction(view_action)
        menu.addSeparator()
        is_selected = path in self.selected_image_paths
        toggle_text = "Deselect" if is_selected else "Select"
        toggle_action = QAction(toggle_text, self)
        toggle_action.triggered.connect(lambda: self.toggle_selection(path))
        menu.addAction(toggle_action)
        menu.addSeparator()

        # Remove from Database option
        db_connected = self.db_tab_ref.db is not None
        remove_db_action = QAction("🔌 Remove from Database", self)
        remove_db_action.setEnabled(db_connected)
        remove_db_action.triggered.connect(lambda: self.remove_image_from_db(path))
        menu.addAction(remove_db_action)
        menu.addSeparator()

        delete_action = QAction("🗑️ Delete Image File (Permanent)", self)
        delete_action.triggered.connect(lambda: self.handle_delete_image(path))
        menu.addAction(delete_action)
        menu.exec(global_pos)

    def remove_image_from_db(self, path: str):
        db = self.db_tab_ref.db
        if not db:
            return

        filename = Path(path).name
        if (
            QMessageBox.question(
                self,
                "Confirm Removal",
                f"Are you sure you want to remove '{filename}' from the database?\n\nThis will only delete the database metadata; the image file will remain on disk.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            == QMessageBox.StandardButton.Yes
        ):
            try:
                img = db.get_image_by_path(path)
                if img:
                    db.delete_image(img["id"])

                self.dual.found_gallery.model.mark_in_db(path, False)

                # Update selected list if path is present there
                if path in self.selected_image_paths:
                    self.populate_selected_images_gallery()

                # If view filters (like Show Only In DB) are active, update scan gallery
                if self.view_in_db_only or self.view_new_only:
                    self._load_current_scan_page()

                QMessageBox.information(self, "Success", f"Removed '{filename}' from the database.")

            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to remove image from database: {e}")

    def _view_image_properties(self, file_path: str):
        db = self.db_tab_ref.db
        path = Path(file_path)
        file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
        file_mtime = os.path.getmtime(file_path) if os.path.exists(file_path) else "N/A"
        width, height = "N/A", "N/A"
        try:
            pixmap = QPixmap(file_path)
            if not pixmap.isNull():
                width = pixmap.width()
                height = pixmap.height()
        except Exception:
            pass
        file_info = f"""
        --- **FILE SYSTEM PROPERTIES** ---
        **Filename:** {path.name}
        **Directory:** {path.parent}
        **Size:** {file_size / (1024 * 1024):.2f} MB ({file_size} bytes)
        **Dimensions:** {width} x {height} pixels
        **Modified:** {file_mtime}
        """
        db_info = "\n--- **DATABASE METADATA** ---"
        if db:
            try:
                db_record = db.get_image_by_path(file_path)
                if db_record:
                    db_info += f"""
        **DB ID:** {db_record.get("id")}
        **Group:** {db_record.get("group_name") or "N/A"}
        **Subgroup:** {db_record.get("subgroup_name") or "N/A"}
        **Tags:** {", ".join(db_record.get("tags", [])) or "None"}
        **DB Width:** {db_record.get("width") or "N/A"}
        **DB Height:** {db_record.get("height") or "N/A"}
        **Added:** {db_record.get("date_added")}
        """
                else:
                    db_info += "\nImage not found in database."
            except Exception as e:
                db_info += f"\nError querying database: {e}"
        else:
            db_info += "\nDatabase is not connected."
        QMessageBox.information(
            self, f"Image Properties: {path.name}", file_info + db_info
        )

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
                if path in self.scan_image_list:
                    self.scan_image_list.remove(path)
                if path in self.scan_filtered_list:
                    self.scan_filtered_list.remove(path)
                if path in self.selected_image_paths:
                    self.selected_image_paths.remove(path)

                # Refresh current pages to fill gaps
                self._refresh_scan_gallery()
                self.populate_selected_images_gallery()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _view_single_image_preview(self, image_path: str):
        if not os.path.exists(image_path):
            return
        # Pass the full filtered list so user can navigate next/prev in preview window even if paginated here
        preview = ImagePreviewWindow(
            image_path=image_path,
            db_tab_ref=self.db_tab_ref,
            parent=self,
            all_paths=self.scan_filtered_list,
            start_index=(
                self.scan_filtered_list.index(image_path)
                if image_path in self.scan_filtered_list
                else 0
            ),
        )
        preview.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        if hasattr(preview, "path_changed"):
            preview.path_changed.connect(self.update_preview_highlight)  # pyrefly: ignore [missing-attribute]
        preview.show()
        self.open_preview_windows.append(preview)


__all__ = ["_ContextMenuActionsMixin"]
