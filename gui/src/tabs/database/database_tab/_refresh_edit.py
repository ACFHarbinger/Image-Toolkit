"""Table refresh and inline-edit controller for ``DatabaseTab`` (§5.17, #544)."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMenu, QMessageBox, QTableWidgetItem

if TYPE_CHECKING:
    pass


class DatabaseRefreshController:
    """Reload group/subgroup/tag/registry tables; handle inline cell edits."""

    def __init__(self, tab: Any) -> None:
        self.tab = tab

    def refresh_groups_list(self) -> None:
        tab = self.tab
        if not tab.db:
            tab.groups_table.setRowCount(0)
            return
        tab.groups_table.blockSignals(True)
        tab.old_edit_value = None
        try:
            groups = tab.db.get_all_groups()
            tab.groups_table.setRowCount(len(groups))
            for row, group_name in enumerate(groups):
                name_item = QTableWidgetItem(group_name)
                tab.groups_table.setItem(row, 0, name_item)
            tab._refresh_all_group_combos()
            tab.update_statistics()
        except Exception as e:
            QMessageBox.critical(
                tab, "Error", f"Failed to load groups list:\n{str(e)}"
            )
        finally:
            tab.groups_table.blockSignals(False)

    def refresh_subgroups_list(self) -> None:
        tab = self.tab
        if not tab.db:
            tab.subgroups_table.setRowCount(0)
            return
        tab.subgroups_table.blockSignals(True)
        tab.old_edit_value = None

        parent_group_filter = tab.existing_subgroups_filter_combo.currentText()

        results = []
        try:
            if not parent_group_filter:
                raw_data = tab.db.get_all_subgroups_detailed()
                results = raw_data
            else:
                subgroup_names = tab.db.get_subgroups_for_group(parent_group_filter)
                results = [(name, parent_group_filter) for name in subgroup_names]

            tab.subgroups_table.setRowCount(len(results))
            for row, (sub_name, grp_name) in enumerate(results):
                name_item = QTableWidgetItem(sub_name)
                group_item = QTableWidgetItem(grp_name)
                group_item.setFlags(group_item.flags() & ~Qt.ItemFlag.ItemIsEditable)

                tab.subgroups_table.setItem(row, 0, name_item)
                tab.subgroups_table.setItem(row, 1, group_item)

        except Exception as e:
            QMessageBox.critical(
                tab, "Error", f"Failed to load subgroups list:\n{str(e)}"
            )
        finally:
            tab.subgroups_table.blockSignals(False)

    def refresh_tags_list(self) -> None:
        tab = self.tab
        if not tab.db:
            tab.tags_table.setRowCount(0)
            return
        tab.tags_table.blockSignals(True)
        tab.old_edit_value = None
        try:
            self._refresh_tag_category_combos()
            tags = tab.db.get_all_tags_with_categories()
            tab.tags_table.setRowCount(len(tags))
            for row, tag_data in enumerate(tags):
                name_item = QTableWidgetItem(tag_data["name"])
                category_item = QTableWidgetItem(tag_data["category"])
                tab.tags_table.setItem(row, 0, name_item)
                tab.tags_table.setItem(row, 1, category_item)
            tab.update_statistics()
        except Exception as e:
            QMessageBox.critical(tab, "Error", f"Failed to load tags list:\n{str(e)}")
        finally:
            tab.tags_table.blockSignals(False)

    def _refresh_tag_category_combos(self) -> None:
        tab = self.tab
        if not tab.db:
            return
        try:
            names = [c["name"] for c in tab.db.list_tag_categories()]
        except Exception:
            return
        for combo in (tab.new_tag_type_combo, tab.bulk_tag_type_combo):
            current = combo.currentText()
            combo.blockSignals(True)
            combo.clear()
            combo.addItems([""] + names)
            combo.setCurrentText(current)
            combo.blockSignals(False)

    def refresh_image_registry(self) -> None:
        tab = self.tab
        if not tab.db:
            tab.image_registry_table.setRowCount(0)
            tab._registry_rows = []
            return
        try:
            images = tab.db.search_images()
            tab._registry_rows = [
                (
                    img.get("file_path", ""),
                    img.get("group_name") or "",
                    img.get("subgroup_name") or "",
                )
                for img in images
            ]
            tab.registry_filter_edit.clear()
            self._populate_registry_table(tab._registry_rows)
        except Exception as e:
            QMessageBox.critical(
                tab, "Error", f"Failed to load image registry:\n{str(e)}"
            )

    def _populate_registry_table(self, rows: list) -> None:
        tab = self.tab
        tab.image_registry_table.setSortingEnabled(False)
        tab.image_registry_table.setRowCount(len(rows))
        for row, (path, group, subgroup) in enumerate(rows):
            path_item = QTableWidgetItem(path)
            path_item.setToolTip(path)
            tab.image_registry_table.setItem(row, 0, path_item)
            tab.image_registry_table.setItem(row, 1, QTableWidgetItem(group))
            tab.image_registry_table.setItem(row, 2, QTableWidgetItem(subgroup))
        tab.image_registry_table.setSortingEnabled(True)

    def _apply_registry_filter(self, text: str) -> None:
        tab = self.tab
        needle = text.strip().lower()
        if not needle:
            self._populate_registry_table(tab._registry_rows)
            return
        filtered = [
            (p, g, s)
            for p, g, s in tab._registry_rows
            if needle in p.lower() or needle in g.lower() or needle in s.lower()
        ]
        self._populate_registry_table(filtered)

    def _show_registry_context_menu(self, pos) -> None:
        tab = self.tab
        index = tab.image_registry_table.indexAt(pos)
        if not index.isValid():
            return
        row = index.row()
        path_item = tab.image_registry_table.item(row, 0)
        if not path_item:
            return
        path = path_item.text()
        menu = QMenu(tab)
        copy_action = menu.addAction("📋 Copy Path")
        open_action = menu.addAction("📂 Open Containing Folder")
        chosen = menu.exec(tab.image_registry_table.viewport().mapToGlobal(pos))
        if chosen == copy_action:
            from PySide6.QtWidgets import QApplication

            QApplication.clipboard().setText(path)
        elif chosen == open_action:
            import subprocess

            folder = os.path.dirname(path)
            if os.path.isdir(folder):
                subprocess.Popen(["xdg-open", folder])

    def store_old_value(self, row: int, col: int) -> None:
        tab = self.tab
        table = tab.sender()
        if not table:
            return
        item = table.item(row, col)  # pyrefly: ignore [missing-attribute]
        if item:
            tab.old_edit_value = item.text()

    def handle_group_edited(self, item: QTableWidgetItem) -> None:
        tab = self.tab
        if not tab.db or tab.old_edit_value is None:
            return
        new_name = item.text().strip()
        old_name = tab.old_edit_value
        tab.old_edit_value = None
        if not new_name:
            QMessageBox.warning(tab, "Error", "Group name cannot be empty.")
            item.setText(old_name)
            return
        if new_name == old_name:
            return
        try:
            tab.db.rename_group(old_name, new_name)
            tab.refresh_groups_list()
            tab.refresh_subgroups_list()
            tab.update_statistics()
        except Exception as e:
            if "UNIQUE" in str(e):
                QMessageBox.warning(
                    tab, "Error", f"A group named '{new_name}' already exists."
                )
            else:
                QMessageBox.critical(
                    tab, "Error", f"Failed to rename group:\n{str(e)}"
                )
            item.setText(old_name)

    def handle_subgroup_edited(self, item: QTableWidgetItem) -> None:
        tab = self.tab
        if not tab.db or tab.old_edit_value is None:
            return
        col = item.column()
        if col != 0:
            if item.text() != tab.old_edit_value:
                item.setText(tab.old_edit_value)
            tab.old_edit_value = None
            return
        new_name = item.text().strip()
        old_name = tab.old_edit_value
        tab.old_edit_value = None
        if new_name == old_name:
            return
        row = item.row()
        parent_group = tab.subgroups_table.item(row, 1).text()  # pyrefly: ignore [missing-attribute]
        if not new_name:
            QMessageBox.warning(tab, "Error", "Subgroup name cannot be empty.")
            item.setText(old_name)
            return
        try:
            tab.db.rename_subgroup(old_name, new_name, parent_group)
            tab.refresh_subgroup_autocomplete()
            tab.update_statistics()
        except Exception as e:
            if "UNIQUE" in str(e):
                QMessageBox.warning(
                    tab,
                    "Error",
                    f"A subgroup named '{new_name}' already exists in this group.",
                )
            else:
                QMessageBox.critical(
                    tab, "Error", f"Failed to rename subgroup:\n{str(e)}"
                )
            item.setText(old_name)

    def handle_tag_edited(self, item: QTableWidgetItem) -> None:
        tab = self.tab
        if not tab.db or tab.old_edit_value is None:
            return
        new_value = item.text().strip()
        old_value = tab.old_edit_value
        tab.old_edit_value = None
        if new_value == old_value:
            return
        row = item.row()
        col = item.column()
        if col == 0:
            old_name = old_value
            new_name = new_value
            if not new_name:
                QMessageBox.warning(tab, "Error", "Tag name cannot be empty.")
                item.setText(old_name)
                return
            try:
                tab.db.rename_tag(old_name, new_name)
                if item.text() != new_name:
                    item.setText(new_name)
                tab.update_statistics()
                tab._publish_tag_catalog_changed()
            except Exception as e:
                if "UNIQUE" in str(e):
                    QMessageBox.warning(
                        tab, "Error", f"A tag named '{new_name}' already exists."
                    )
                else:
                    QMessageBox.critical(
                        tab, "Error", f"Failed to rename tag:\n{str(e)}"
                    )
                item.setText(old_name)
        elif col == 1:
            tag_name = tab.tags_table.item(row, 0).text()  # pyrefly: ignore [missing-attribute]
            new_category = new_value.title()
            try:
                tab.db.update_tag_category(tag_name, new_category)
                if item.text() != new_category:
                    item.setText(new_category)
            except Exception as e:
                QMessageBox.critical(
                    tab, "Error", f"Failed to update tag category:\n{str(e)}"
                )
                item.setText(old_value)


# Backward-compatible alias
_RefreshEditMixin = DatabaseRefreshController

__all__ = ["DatabaseRefreshController", "_RefreshEditMixin"]
