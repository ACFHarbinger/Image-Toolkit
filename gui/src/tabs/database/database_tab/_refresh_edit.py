"""Table refresh + inline-edit handlers for ``DatabaseTab``.

Extracted from ``database_tab.py`` -- pure code motion, no logic change
(see ``_ui_connection.py``'s docstring).
"""

from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMenu, QMessageBox, QTableWidgetItem


class _RefreshEditMixin:
    """Reload group/subgroup/tag/registry tables; handle inline cell edits."""

    def refresh_groups_list(self):
        if not self.db:
            self.groups_table.setRowCount(0)
            return
        self.groups_table.blockSignals(True)
        self.old_edit_value = None
        try:
            groups = self.db.get_all_groups()
            self.groups_table.setRowCount(len(groups))
            for row, group_name in enumerate(groups):
                name_item = QTableWidgetItem(group_name)
                self.groups_table.setItem(row, 0, name_item)
            self._refresh_all_group_combos()
            self.update_statistics()
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to load groups list:\n{str(e)}"
            )
        finally:
            self.groups_table.blockSignals(False)

    def refresh_subgroups_list(self):
        if not self.db:
            self.subgroups_table.setRowCount(0)
            return
        self.subgroups_table.blockSignals(True)
        self.old_edit_value = None

        parent_group_filter = self.existing_subgroups_filter_combo.currentText()

        results = []
        try:
            if not parent_group_filter:
                # CASE 1: No filter selected -> Show ALL subgroups with their parents
                #
                raw_data = self.db.get_all_subgroups_detailed()
                results = raw_data  # List of (subgroup_name, group_name)
            else:
                # CASE 2: Filter selected -> Show only specific subgroups
                #
                subgroup_names = self.db.get_subgroups_for_group(parent_group_filter)
                # format as list of tuples to match Case 1
                results = [(name, parent_group_filter) for name in subgroup_names]

            # Populate the Table
            self.subgroups_table.setRowCount(len(results))
            for row, (sub_name, grp_name) in enumerate(results):
                name_item = QTableWidgetItem(sub_name)
                group_item = QTableWidgetItem(grp_name)

                # Lock the parent group cell so it can't be edited here (only subgroup name is editable)
                group_item.setFlags(group_item.flags() & ~Qt.ItemFlag.ItemIsEditable)

                self.subgroups_table.setItem(row, 0, name_item)
                self.subgroups_table.setItem(row, 1, group_item)

        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to load subgroups list:\n{str(e)}"
            )
        finally:
            self.subgroups_table.blockSignals(False)

    def refresh_tags_list(self):
        if not self.db:
            self.tags_table.setRowCount(0)
            return
        self.tags_table.blockSignals(True)
        self.old_edit_value = None
        try:
            tags = self.db.get_all_tags_with_types()
            self.tags_table.setRowCount(len(tags))
            for row, tag_data in enumerate(tags):
                name_item = QTableWidgetItem(tag_data["name"])
                type_item = QTableWidgetItem(tag_data["type"])
                self.tags_table.setItem(row, 0, name_item)
                self.tags_table.setItem(row, 1, type_item)
            self.update_statistics()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load tags list:\n{str(e)}")
        finally:
            self.tags_table.blockSignals(False)

    def refresh_image_registry(self):
        """Populate the Image Registry table with all paths from the DB."""
        if not self.db:
            self.image_registry_table.setRowCount(0)
            self._registry_rows = []
            return
        try:
            images = self.db.search_images()
            self._registry_rows = [
                (
                    img.get("file_path", ""),
                    img.get("group_name") or "",
                    img.get("subgroup_name") or "",
                )
                for img in images
            ]
            self.registry_filter_edit.clear()
            self._populate_registry_table(self._registry_rows)
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to load image registry:\n{str(e)}"
            )

    def _populate_registry_table(self, rows: list) -> None:
        """Fill image_registry_table from a list of (path, group, subgroup) tuples."""
        self.image_registry_table.setSortingEnabled(False)
        self.image_registry_table.setRowCount(len(rows))
        for row, (path, group, subgroup) in enumerate(rows):
            path_item = QTableWidgetItem(path)
            path_item.setToolTip(path)
            self.image_registry_table.setItem(row, 0, path_item)
            self.image_registry_table.setItem(row, 1, QTableWidgetItem(group))
            self.image_registry_table.setItem(row, 2, QTableWidgetItem(subgroup))
        self.image_registry_table.setSortingEnabled(True)

    def _apply_registry_filter(self, text: str) -> None:
        """Filter the Image Registry table client-side without a DB round-trip."""
        needle = text.strip().lower()
        if not needle:
            self._populate_registry_table(self._registry_rows)
            return
        filtered = [
            (p, g, s)
            for p, g, s in self._registry_rows
            if needle in p.lower() or needle in g.lower() or needle in s.lower()
        ]
        self._populate_registry_table(filtered)

    def _show_registry_context_menu(self, pos) -> None:
        """Right-click context menu on the Image Registry table."""
        index = self.image_registry_table.indexAt(pos)
        if not index.isValid():
            return
        row = index.row()
        path_item = self.image_registry_table.item(row, 0)
        if not path_item:
            return
        path = path_item.text()
        menu = QMenu(self)
        copy_action = menu.addAction("📋 Copy Path")
        open_action = menu.addAction("📂 Open Containing Folder")
        chosen = menu.exec(self.image_registry_table.viewport().mapToGlobal(pos))
        if chosen == copy_action:
            from PySide6.QtWidgets import QApplication

            QApplication.clipboard().setText(path)
        elif chosen == open_action:
            import subprocess

            folder = os.path.dirname(path)
            if os.path.isdir(folder):
                subprocess.Popen(["xdg-open", folder])

    def store_old_value(self, row, col):
        table = self.sender()
        if not table:
            return
        item = table.item(row, col)  # pyrefly: ignore [missing-attribute]
        if item:
            self.old_edit_value = item.text()

    def handle_group_edited(self, item: QTableWidgetItem):
        if not self.db or self.old_edit_value is None:
            return
        new_name = item.text().strip()
        old_name = self.old_edit_value
        self.old_edit_value = None
        if not new_name:
            QMessageBox.warning(self, "Error", "Group name cannot be empty.")
            item.setText(old_name)
            return
        if new_name == old_name:
            return
        try:
            self.db.rename_group(old_name, new_name)
            self.refresh_groups_list()
            self.refresh_subgroups_list()
            self.update_statistics()
        except Exception as e:
            if "UNIQUE" in str(e):
                QMessageBox.warning(
                    self, "Error", f"A group named '{new_name}' already exists."
                )
            else:
                QMessageBox.critical(
                    self, "Error", f"Failed to rename group:\n{str(e)}"
                )
            item.setText(old_name)

    def handle_subgroup_edited(self, item: QTableWidgetItem):
        if not self.db or self.old_edit_value is None:
            return
        col = item.column()
        if col != 0:
            if item.text() != self.old_edit_value:
                item.setText(self.old_edit_value)
            self.old_edit_value = None
            return
        new_name = item.text().strip()
        old_name = self.old_edit_value
        self.old_edit_value = None
        if new_name == old_name:
            return
        row = item.row()
        parent_group = self.subgroups_table.item(row, 1).text()  # pyrefly: ignore [missing-attribute]
        if not new_name:
            QMessageBox.warning(self, "Error", "Subgroup name cannot be empty.")
            item.setText(old_name)
            return
        try:
            self.db.rename_subgroup(old_name, new_name, parent_group)
            self.refresh_subgroup_autocomplete()
            self.update_statistics()
        except Exception as e:
            if "UNIQUE" in str(e):
                QMessageBox.warning(
                    self,
                    "Error",
                    f"A subgroup named '{new_name}' already exists in this group.",
                )
            else:
                QMessageBox.critical(
                    self, "Error", f"Failed to rename subgroup:\n{str(e)}"
                )
            item.setText(old_name)

    def handle_tag_edited(self, item: QTableWidgetItem):
        if not self.db or self.old_edit_value is None:
            return
        new_value = item.text().strip()
        old_value = self.old_edit_value
        self.old_edit_value = None
        if new_value == old_value:
            return
        row = item.row()
        col = item.column()
        if col == 0:
            old_name = old_value
            new_name = new_value
            if not new_name:
                QMessageBox.warning(self, "Error", "Tag name cannot be empty.")
                item.setText(old_name)
                return
            try:
                self.db.rename_tag(old_name, new_name)
                if item.text() != new_name:
                    item.setText(new_name)
                self.update_statistics()
                if self.scan_tab_ref:
                    self.scan_tab_ref._setup_tag_checkboxes()
            except Exception as e:
                if "UNIQUE" in str(e):
                    QMessageBox.warning(
                        self, "Error", f"A tag named '{new_name}' already exists."
                    )
                else:
                    QMessageBox.critical(
                        self, "Error", f"Failed to rename tag:\n{str(e)}"
                    )
                item.setText(old_name)
        elif col == 1:
            tag_name = self.tags_table.item(row, 0).text()  # pyrefly: ignore [missing-attribute]
            new_type = new_value.title()
            try:
                self.db.update_tag_type(tag_name, new_type)
                if item.text() != new_type:
                    item.setText(new_type)
            except Exception as e:
                QMessageBox.critical(
                    self, "Error", f"Failed to update tag type:\n{str(e)}"
                )
                item.setText(old_value)


__all__ = ["_RefreshEditMixin"]
