"""Image properties, context menu, comparison dialog, and full-size preview.

Extracted from ``similarity_tab.py`` -- pure code motion, no logic change
(see ``_ui_builder.py``'s docstring).
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from PIL import Image
from PySide6.QtCore import QPoint, Qt, Slot
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QMessageBox

from ....components import PropertyComparisonDialog
from ....windows import ImagePreviewWindow


class _PropertiesPreviewMixin:
    """File/DB properties, right-click context menu, comparison dialog, preview."""

    def _prefs(self) -> dict:
        main_win = self.window()
        if main_win and hasattr(main_win, "cached_creds"):
            return main_win.cached_creds.get("preferences", {})
        return {}

    def get_image_properties(self, file_path: str) -> Dict[str, Any]:
        if not Path(file_path).exists():
            return {"Error": "File not found."}
        props: Dict[str, Any] = {"Path": file_path, "File Name": os.path.basename(file_path)}
        try:
            stat = os.stat(file_path)
            props["File Size"] = f"{stat.st_size / (1024 * 1024):.2f} MB ({stat.st_size} bytes)"
            props["Last Modified"] = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        except OSError:
            props["File Size"] = "N/A"
        try:
            img = Image.open(file_path)
            props["Width"] = f"{img.width} px"
            props["Height"] = f"{img.height} px"
            props["Format"] = img.format
            img.close()
        except Exception:
            props["Width"] = "N/A"
        return props

    @Slot(QPoint, str)
    def show_image_context_menu(self, global_pos: QPoint, path: str):
        menu = QMenu(self)
        prop_action = QAction("🖼️ Show Image Properties", self)
        prop_action.triggered.connect(lambda: self.show_image_properties_dialog(path))
        menu.addAction(prop_action)
        if len(self.selected_files) > 1:
            cmp_action = QAction("📊 Compare Selected Properties", self)
            cmp_action.triggered.connect(self.show_comparison_dialog)
            menu.addAction(cmp_action)
        menu.addSeparator()
        view_action = QAction("🔍 View Full Size Preview", self)
        view_action.triggered.connect(lambda: self.open_full_preview(path))
        menu.addAction(view_action)
        is_selected = path in self.selected_files
        toggle_text = "Deselect (Keep)" if is_selected else "Select (Mark for Delete)"
        toggle_action = QAction(toggle_text, self)
        toggle_action.triggered.connect(lambda: self.toggle_selection(path))
        menu.addAction(toggle_action)
        menu.addSeparator()
        delete_action = QAction("🗑️ Delete This File", self)
        delete_action.triggered.connect(lambda: self.delete_single_file(path))
        menu.addAction(delete_action)
        menu.exec(global_pos)

    @Slot(str)
    def show_image_properties_dialog(self, path: str):
        properties = self.get_image_properties(path)
        if "Error" in properties:
            QMessageBox.critical(self, "Error Reading File", properties["Error"])
            return
        prop_text = f"**File:** {os.path.basename(path)}\n**Path:** {path}\n\n**Technical Details**\n"
        for key, value in properties.items():
            if key not in ["Path", "File Name"]:
                prop_text += f"  - **{key}:** {value}\n"
        msg = QMessageBox(self)
        msg.setWindowTitle("Image Properties")
        msg.setTextFormat(Qt.TextFormat.MarkdownText)
        msg.setText(prop_text)
        msg.setIcon(QMessageBox.Icon.Information)
        msg.exec()

    @Slot()
    def show_comparison_dialog(self):
        if not self.selected_files:
            QMessageBox.warning(self, "No Selection", "Please select at least one image to compare.")
            return
        selected_paths = list(self.selected_files)
        if len(selected_paths) > 10:
            reply = QMessageBox.question(
                self, "Large Selection",
                f"Selected {len(selected_paths)} images. Compare first 10?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes)
            if reply == QMessageBox.StandardButton.Yes:
                selected_paths = selected_paths[:10]
            else:
                return
        property_list = []
        for path in selected_paths:
            if Path(path).exists():
                property_list.append(self.get_image_properties(path))
            else:
                property_list.append({"File Name": os.path.basename(path), "Path": path,
                                      "Error": "File not found."})
        dialog = PropertyComparisonDialog(property_list, self)
        dialog.exec()

    def open_full_preview(self, image_path: str):
        full_list = self.found_files
        target_list = full_list if full_list else list(self.selected_files)
        if not target_list:
            target_list = [image_path]
        elif image_path not in target_list:
            target_list.append(image_path)
        try:
            start_index = target_list.index(image_path)
        except ValueError:
            start_index = 0
        preview = ImagePreviewWindow(image_path=image_path, db_tab_ref=None, parent=self,
                                     all_paths=target_list, start_index=start_index)
        preview.path_changed.connect(self.update_preview_highlight)
        preview.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        preview.show()
        self.open_preview_windows.append(preview)


__all__ = ["_PropertiesPreviewMixin"]
