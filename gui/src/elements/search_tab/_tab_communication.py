"""Sending the current selection to other tabs (Scan/Merge/Delete/Wallpaper).

Extracted from ``search_tab.py`` -- pure code motion, no logic change
(see ``_ui_builder.py``'s docstring).
"""

from __future__ import annotations

from PySide6.QtWidgets import QMessageBox

from ...utils.sort_utils import natural_sort_key


class _TabCommunicationMixin:
    """Hand off the current selection to another tab's own gallery/state."""

    def _get_target_selection(self, single_path=None):
        # Use self.selected_files instead of self.selected_paths
        paths = list(self.selected_files)
        if single_path:
            if single_path in paths:
                return sorted(paths, key=natural_sort_key)
            else:
                return [single_path]
        return sorted(paths, key=natural_sort_key)

    def send_selection_to_scan_tab(self):
        if not self.selected_files:
            QMessageBox.information(
                self,
                "No Selection",
                "Please select at least one image to open in the Scan Tab.",
            )
            return
        if (
            not self.db_tab_ref
            or not hasattr(self.db_tab_ref, "scan_tab_ref")
            or not self.db_tab_ref.scan_tab_ref
        ):
            QMessageBox.warning(
                self, "Configuration Error", "Scan Metadata Tab reference not found."
            )
            return
        scan_tab = self.db_tab_ref.scan_tab_ref
        sorted_selection = sorted(list(self.selected_files), key=natural_sort_key)
        scan_tab.process_scan_results(sorted_selection)
        if hasattr(scan_tab, "view_db_only_button"):
            scan_tab.view_db_only_button.setChecked(False)
        QMessageBox.information(
            self,
            "Images Sent",
            f"Successfully sent {len(sorted_selection)} images to the Scan Metadata Tab.",
        )

    def send_selection_to_merge_tab(self, single_path=None):
        paths = self._get_target_selection(single_path)
        if not paths:
            QMessageBox.information(self, "No Selection", "No images selected.")
            return
        if (
            not hasattr(self.db_tab_ref, "merge_tab_ref")
            or not self.db_tab_ref.merge_tab_ref
        ):
            QMessageBox.warning(self, "Error", "Merge Tab reference not found.")
            return
        self.db_tab_ref.merge_tab_ref.display_scan_results(paths)
        QMessageBox.information(
            self, "Images Sent", f"Sent {len(paths)} images to the Merge Tab."
        )

    def send_selection_to_delete_tab(self, single_path=None):
        paths = self._get_target_selection(single_path)
        if not paths:
            QMessageBox.information(self, "No Selection", "No images selected.")
            return
        if (
            not hasattr(self.db_tab_ref, "delete_tab_ref")
            or not self.db_tab_ref.delete_tab_ref
        ):
            QMessageBox.warning(self, "Error", "Delete Tab reference not found.")
            return
        delete_tab = self.db_tab_ref.delete_tab_ref
        delete_tab.clear_galleries()
        delete_tab.duplicate_results = {
            "imported": paths
        }  # Adapt data structure for delete tab
        delete_tab.status_label.setText(f"Imported {len(paths)} files from Search.")
        delete_tab.start_loading_thumbnails(paths)
        QMessageBox.information(
            self, "Images Sent", f"Sent {len(paths)} images to the Delete Tab."
        )

    def send_selection_to_wallpaper_tab(self, single_path=None):
        paths = self._get_target_selection(single_path)
        if not paths:
            QMessageBox.information(self, "No Selection", "No images selected.")
            return
        if (
            not hasattr(self.db_tab_ref, "wallpaper_tab_ref")
            or not self.db_tab_ref.wallpaper_tab_ref
        ):
            QMessageBox.warning(self, "Error", "Wallpaper Tab reference not found.")
            return
        self.db_tab_ref.wallpaper_tab_ref.display_scan_results(paths)
        QMessageBox.information(
            self, "Images Sent", f"Sent {len(paths)} images to the Wallpaper Tab."
        )


__all__ = ["_TabCommunicationMixin"]
