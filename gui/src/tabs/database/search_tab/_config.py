"""Tab-config persistence (``collect``/``get_default_config``/``set_config``).

Extracted from ``search_tab.py`` -- pure code motion, no logic change
(see ``_ui_builder.py``'s docstring).
"""

from __future__ import annotations

from typing import Any, Dict

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox


class _ConfigMixin:
    """Save/restore group/subgroup/tag/format filter selections."""

    def collect(self) -> Dict[str, Any]:
        return {
            "group_names": self.get_selected_groups() or None,
            "subgroup_names": self.get_selected_subgroups() or None,
            "filename_pattern": self.filename_edit.text().strip() or None,
            "input_formats": self.get_selected_formats() or None,
            "tags": self.get_selected_tags() or None,
        }

    def get_default_config(self) -> Dict[str, Any]:
        return {
            "group_names": [],
            "subgroup_names": [],
            "filename_pattern": "",
            "input_formats": [],
            "tags": [],
        }

    def set_config(self, config: Dict[str, Any]):
        try:
            # Restore group selections
            selected_groups = set(config.get("group_names", []) or [])
            for i in range(self.groups_list_widget.count()):
                item = self.groups_list_widget.item(i)
                item.setCheckState(
                    Qt.CheckState.Checked
                    if item.text() in selected_groups
                    else Qt.CheckState.Unchecked
                )
            # Restore subgroup selections
            selected_subgroups = set(config.get("subgroup_names", []) or [])
            for i in range(self.subgroups_list_widget.count()):
                item = self.subgroups_list_widget.item(i)
                item.setCheckState(
                    Qt.CheckState.Checked
                    if item.data(Qt.ItemDataRole.UserRole) in selected_subgroups
                    else Qt.CheckState.Unchecked
                )
            self.filename_edit.setText(config.get("filename_pattern", ""))
            self._setup_tag_checkboxes()
            selected_tags = set(config.get("tags", []))
            for i in range(self.tags_list_widget.count()):
                item = self.tags_list_widget.item(i)
                item.setCheckState(
                    Qt.CheckState.Checked
                    if item.data(Qt.ItemDataRole.UserRole) in selected_tags
                    else Qt.CheckState.Unchecked
                )
            formats = config.get("input_formats", [])
            if self.dropdown:
                self.remove_all_formats()
                for fmt in formats:
                    if fmt in self.format_buttons:
                        self.format_buttons[fmt].setChecked(True)
                        self.toggle_format(fmt, True)
            else:
                self.input_formats_edit.setText(" ".join(formats))
            QMessageBox.information(
                self, "Config Loaded", "Search configuration applied successfully."
            )
        except Exception as e:
            QMessageBox.critical(
                self, "Config Error", f"Failed to apply search configuration:\n{e}"
            )


__all__ = ["_ConfigMixin"]
