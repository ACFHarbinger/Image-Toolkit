"""DB removal, file deletion, properties, context menu, and preview windows.

Extracted from ``search_tab.py`` -- pure code motion, no logic change
(see ``_ui_builder.py``'s docstring).
"""

from __future__ import annotations

import os
import platform
import subprocess
import time

from PySide6.QtCore import QPoint
from PySide6.QtGui import QAction, QCursor, QPixmap
from PySide6.QtWidgets import QMenu, QMessageBox, QWidget
from send2trash import send2trash  # pyrefly: ignore [untyped-import]

from ...windows import ImagePreviewWindow


class _FileActionsMixin:
    """Remove-from-DB, delete-file, properties dialog, context menu, preview."""

    def handle_remove_from_db(self, file_path: str):
        db = self.db_tab_ref.db
        if not db:
            QMessageBox.warning(
                self, "Database Error", "Please connect to the database first."
            )
            return
        filename = os.path.basename(file_path)
        reply = QMessageBox.question(
            self,
            "Confirm Database Removal",
            f"Are you sure you want to remove the entry for **{filename}** from the database?\n\nThe physical image file WILL NOT be deleted.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.No:
            return
        try:
            image_data = db.get_image_by_path(file_path)
            image_id = image_data.get("id") if image_data else None
            if image_id is not None:
                db.delete_image(image_id)
                if file_path in self.found_files:
                    self.found_files.remove(file_path)
                if file_path in self.selected_files:
                    self.selected_files.remove(file_path)
                self.perform_search()
                QMessageBox.information(
                    self,
                    "Success",
                    f"Database entry for **{filename}** removed successfully.",
                )
            else:
                QMessageBox.warning(
                    self, "Warning", f"No database entry found for file: {filename}"
                )
        except Exception as e:
            QMessageBox.critical(
                self, "Removal Failed", f"Could not remove database entry:\n{e}"
            )

    def handle_delete_image(self, file_path: str):
        if not file_path or not os.path.exists(file_path):
            QMessageBox.warning(
                self, "Delete Error", "File not found or path is invalid."
            )
            return
        db = self.db_tab_ref.db
        if not db:
            QMessageBox.warning(
                self,
                "Delete Error",
                "Database connection required for file and DB deletion.",
            )
            return
        filename = os.path.basename(file_path)
        prefs = {}
        main_win = self.window()
        if main_win and hasattr(main_win, "cached_creds"):
            prefs = main_win.cached_creds.get("preferences", {})
        send_to_trash_enabled = prefs.get("send_to_trash", True)
        action_name = "Trash" if send_to_trash_enabled else "Permanent Delete"

        reply = QMessageBox.question(
            self,
            f"Confirm {action_name}",
            f"Are you sure you want to {action_name.lower()} the file:\n\n**{filename}**\n\nThis action cannot be undone!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.No:
            return
        try:
            image_data = db.get_image_by_path(file_path)
            image_id = image_data.get("id") if image_data else None
            for window in self.open_preview_windows[:]:
                if hasattr(window, "image_path") and window.image_path == file_path:
                    window.close()
                    break
            if send_to_trash_enabled:
                send2trash(file_path)
            else:
                os.remove(file_path)
            if image_id is not None:
                db.delete_image(image_id)

            if file_path in self.found_files:
                self.found_files.remove(file_path)
            if file_path in self.selected_files:
                self.selected_files.remove(file_path)

            self.perform_search()
            QMessageBox.information(
                self, f"Moved to {action_name}", f"Moved to {action_name}: {filename}"
            )
        except Exception as e:
            QMessageBox.critical(
                self, "Deletion Failed", f"Could not delete the file:\n{e}"
            )

    def show_image_properties(self, file_path: str):
        if not file_path or not os.path.exists(file_path):
            QMessageBox.warning(
                self, "Invalid Path", f"File not found at path:\n{file_path}"
            )
            return
        try:
            stats = os.stat(file_path)
            last_modified = time.strftime(
                "%Y-%m-%d %H:%M:%S", time.localtime(stats.st_mtime)
            )

            def format_size(size_bytes):
                for unit in ["B", "KB", "MB", "GB"]:
                    if size_bytes < 1024.0:
                        return f"{size_bytes:.2f} {unit}"
                    size_bytes /= 1024.0
                return f"{size_bytes:.2f} TB"

            pixmap = QPixmap(file_path)
            dimensions = (
                f"{pixmap.width()} x {pixmap.height()} pixels"
                if not pixmap.isNull()
                else "N/A"
            )
            properties_text = (
                f"**Filename:** {os.path.basename(file_path)}\n"
                f"**Full Path:** {file_path}\n"
                f"**Dimensions:** {dimensions}\n"
                f"**Size:** {format_size(stats.st_size)}\n"
                f"**Last Modified:** {last_modified}\n"
            )
            msg = QMessageBox(self)
            msg.setWindowTitle("Image Properties")
            msg.setText(properties_text)
            msg.setIcon(QMessageBox.Icon.Information)
            msg.setStyleSheet("QLabel{min-width: 400px;}")
            msg.exec()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to retrieve properties: {e}")

    def show_context_menu(self, pos: QPoint, file_path: str, widget: QWidget):
        menu = QMenu(self)
        properties_action = QAction("🖼️ Show Image Properties", self)
        properties_action.triggered.connect(
            lambda: self.show_image_properties(file_path)
        )
        menu.addAction(properties_action)
        preview_action = QAction("👁️ Open Full Preview", self)
        preview_action.triggered.connect(lambda: self.open_file_preview(file_path))
        menu.addAction(preview_action)
        dir_action = QAction("📂 Open File Location", self)
        dir_action.triggered.connect(lambda: self.open_file_directory(file_path))
        menu.addAction(dir_action)
        similar_action = QAction("🧠 Find Similar Images (semantic)", self)
        similar_action.triggered.connect(lambda: self.find_similar_images(file_path))
        menu.addAction(similar_action)
        menu.addSeparator()
        remove_db_action = QAction("❌ Remove from Database Only", self)
        remove_db_action.triggered.connect(
            lambda: self.handle_remove_from_db(file_path)
        )
        menu.addAction(remove_db_action)
        delete_action = QAction("🗑️ Delete Image File (Permanent)", self)
        delete_action.triggered.connect(lambda: self.handle_delete_image(file_path))
        menu.addAction(delete_action)
        menu.addSeparator()
        send_menu = menu.addMenu("Send To...")
        merge_action = QAction("Merge Tab", self)
        merge_action.triggered.connect(
            lambda: self.send_selection_to_merge_tab(file_path)
        )
        send_menu.addAction(merge_action)
        wallpaper_action = QAction("Wallpaper Tab", self)
        wallpaper_action.triggered.connect(
            lambda: self.send_selection_to_wallpaper_tab(file_path)
        )
        send_menu.addAction(wallpaper_action)
        scan_action = QAction("Scan Metadata Tab", self)
        scan_action.triggered.connect(lambda: self.send_selection_to_scan_tab())
        send_menu.addAction(scan_action)
        delete_tab_action = QAction("Similarity Tab", self)
        delete_tab_action.triggered.connect(
            lambda: self.send_selection_to_delete_tab(file_path)
        )
        send_menu.addAction(delete_tab_action)
        menu.addSeparator()

        is_selected = file_path in self.selected_files
        toggle_text = "Deselect" if is_selected else "Select"
        toggle_action = QAction(toggle_text, self)
        toggle_action.triggered.connect(lambda: self.toggle_selection(file_path))
        menu.addAction(toggle_action)
        menu.exec(QCursor.pos())

    def remove_preview_window(self, window_instance: ImagePreviewWindow):
        try:
            if window_instance in self.open_preview_windows:
                self.open_preview_windows.remove(window_instance)
        except (RuntimeError, ValueError):
            pass

    def open_file_preview(self, file_path: str):
        if not file_path or not os.path.exists(file_path):
            QMessageBox.warning(
                self, "Invalid Path", f"File not found at path:\n{file_path}"
            )
            return
        for window in self.open_preview_windows:
            if hasattr(window, "image_path") and window.image_path == file_path:
                window.activateWindow()
                return

        # Use self.found_files from Base class
        if self.found_files:
            try:
                start_index = self.found_files.index(file_path)
                all_paths = self.found_files
            except ValueError:
                start_index = 0
                all_paths = [file_path]
        else:
            start_index = 0
            all_paths = [file_path]

        preview = ImagePreviewWindow(
            image_path=file_path,
            db_tab_ref=self.db_tab_ref,
            parent=self,
            all_paths=all_paths,
            start_index=start_index,
        )
        preview.finished.connect(
            lambda result, p=preview: self.remove_preview_window(p)
        )
        preview.show()
        self.open_preview_windows.append(preview)

    def open_file_directory(self, file_path: str):
        if not file_path or not os.path.exists(file_path):
            QMessageBox.warning(
                self, "Invalid Path", f"File not found at path:\n{file_path}"
            )
            return
        directory = os.path.dirname(file_path)
        system = platform.system()
        try:
            if system == "Windows":
                os.startfile(directory)  # pyrefly: ignore [missing-attribute]
            elif system == "Darwin":
                subprocess.run(["open", directory])
            else:
                subprocess.run(["xdg-open", directory])
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open directory:\n{e}")


__all__ = ["_FileActionsMixin"]
