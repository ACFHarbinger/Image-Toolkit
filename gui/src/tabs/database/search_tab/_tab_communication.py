"""Sending the current selection to other tabs (Scan/Merge/Delete/Wallpaper).

Extracted from ``search_tab.py`` -- pure code motion, no logic change
(see ``_ui_builder.py``'s docstring).
"""

from __future__ import annotations

from PySide6.QtWidgets import QMessageBox

from gui.src.modules.events import ImportPathsIntent, NavigateIntent

from ....utils.sort_utils import natural_sort_key


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
        sorted_selection = sorted(list(self.selected_files), key=natural_sort_key)
        self.event_hub.publish(
            ImportPathsIntent(
                origin="library.search",
                module_id="library.scan",
                paths=tuple(sorted_selection),
            )
        )
        self.event_hub.publish(NavigateIntent(origin="library.search", module_id="library.scan"))
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
        self.event_hub.publish(
            ImportPathsIntent(origin="library.search", module_id="system.merge", paths=tuple(paths))
        )
        self.event_hub.publish(NavigateIntent(origin="library.search", module_id="system.merge"))
        QMessageBox.information(
            self, "Images Sent", f"Sent {len(paths)} images to the Merge Tab."
        )

    def send_selection_to_delete_tab(self, single_path=None):
        paths = self._get_target_selection(single_path)
        if not paths:
            QMessageBox.information(self, "No Selection", "No images selected.")
            return
        self.event_hub.publish(
            ImportPathsIntent(origin="library.search", module_id="system.similarity", paths=tuple(paths))
        )
        self.event_hub.publish(NavigateIntent(origin="library.search", module_id="system.similarity"))
        QMessageBox.information(
            self, "Images Sent", f"Sent {len(paths)} images to the Delete Tab."
        )

    def send_selection_to_wallpaper_tab(self, single_path=None):
        paths = self._get_target_selection(single_path)
        if not paths:
            QMessageBox.information(self, "No Selection", "No images selected.")
            return
        self.event_hub.publish(
            ImportPathsIntent(origin="library.search", module_id="system.wallpaper", paths=tuple(paths))
        )
        self.event_hub.publish(NavigateIntent(origin="library.search", module_id="system.wallpaper"))
        QMessageBox.information(
            self, "Images Sent", f"Sent {len(paths)} images to the Wallpaper Tab."
        )


__all__ = ["_TabCommunicationMixin"]
