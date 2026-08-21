"""Tab-config persistence (``collect``/``get_default_config``/``set_config``).

Extracted from ``scan_metadata_tab.py`` -- pure code motion, no logic
change (see ``_ui_builder.py``'s docstring).
"""

from __future__ import annotations

import os
from typing import Any, Dict

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox


class _ConfigMixin:
    """Save/restore scan directory, view filter, and batch-metadata form state."""

    def refresh_image_directory(self):
        if hasattr(self, "scanned_dir") and self.scanned_dir:
            self.populate_scan_image_gallery(self.scanned_dir, is_refresh=False)
        else:
            self.handle_scan_directory_return()

    def collect(self) -> dict:
        return {
            "scan_directory": self.scan_directory_path.text().strip() or None,
            "view_new_only": self.view_new_only,  # Added
            "batch_metadata": {
                "group_name": self.group_combo.currentText().strip() or "",
                "subgroup_name": self.subgroup_combo.currentText().strip() or "",
                "tags": [
                    self.tags_list_widget.item(i).data(Qt.ItemDataRole.UserRole)
                    for i in range(self.tags_list_widget.count())
                    if self.tags_list_widget.item(i).checkState()
                    == Qt.CheckState.Checked
                ],
            },
        }

    def get_default_config(self) -> Dict[str, Any]:
        return {
            "scan_directory": "",
            "view_new_only": False,
            "batch_metadata": {"group_name": "", "subgroup_name": "", "tags": []},
        }

    def set_config(self, config: Dict[str, Any]):
        try:
            # View New Only toggle
            if "view_new_only" in config:
                self.view_new_only_button.setChecked(config["view_new_only"])

            if "scan_directory" in config:
                self.scan_directory_path.setText(config.get("scan_directory", ""))
                if os.path.isdir(config["scan_directory"]):
                    self.populate_scan_image_gallery(config["scan_directory"])

            if "batch_metadata" in config:
                metadata = config.get("batch_metadata", {})
                self.group_combo.setCurrentText(metadata.get("group_name", ""))
                self.subgroup_combo.setCurrentText(metadata.get("subgroup_name", ""))
                self._setup_tag_checkboxes()
                selected_tags = set(metadata.get("tags", []))
                for i in range(self.tags_list_widget.count()):
                    item = self.tags_list_widget.item(i)
                    item.setCheckState(
                        Qt.CheckState.Checked
                        if item.data(Qt.ItemDataRole.UserRole) in selected_tags
                        else Qt.CheckState.Unchecked
                    )
            QMessageBox.information(
                self,
                "Config Loaded",
                "Scan metadata configuration applied successfully.",
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Config Error",
                f"Failed to apply scan metadata configuration:\n{e}",
            )


__all__ = ["_ConfigMixin"]
