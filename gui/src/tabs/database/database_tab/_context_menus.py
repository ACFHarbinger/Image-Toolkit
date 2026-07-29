"""Right-click context menus for the groups/subgroups/tags tables.

Extracted from ``database_tab.py`` -- pure code motion, no logic change
(see ``_ui_connection.py``'s docstring).
"""

from __future__ import annotations

from PySide6.QtWidgets import QMenu


class _ContextMenusMixin:
    """Edit/Remove context menus for the three management tables."""

    def show_group_context_menu(self, pos):
        item = self.groups_table.itemAt(pos)
        if not item:
            return
        menu = QMenu()
        edit_action = menu.addAction("Edit Group")
        remove_action = menu.addAction("Remove Group")
        action = menu.exec(self.groups_table.mapToGlobal(pos))
        if action == edit_action:
            self.edit_selected_group_cell()
        elif action == remove_action:
            self.remove_selected_group()

    def edit_selected_group_cell(self):
        item = self.groups_table.currentItem()
        if item:
            self.groups_table.editItem(item)

    def show_subgroup_context_menu(self, pos):
        item = self.subgroups_table.itemAt(pos)
        if not item:
            return
        menu = QMenu()
        edit_action = menu.addAction("Edit Subgroup") if item.column() == 0 else None
        remove_action = menu.addAction("Remove Subgroup")
        action = menu.exec(self.subgroups_table.mapToGlobal(pos))
        if action == edit_action:
            self.edit_selected_subgroup_cell()
        elif action == remove_action:
            self.remove_selected_subgroup()

    def edit_selected_subgroup_cell(self):
        current_row = self.subgroups_table.currentRow()
        if current_row < 0:
            return
        item_to_edit = self.subgroups_table.item(current_row, 0)
        if item_to_edit:
            self.subgroups_table.editItem(item_to_edit)

    def show_tag_context_menu(self, pos):
        item = self.tags_table.itemAt(pos)
        if not item:
            return
        menu = QMenu()
        edit_action = menu.addAction("Edit Cell")
        remove_action = menu.addAction("Remove Tag")
        action = menu.exec(self.tags_table.mapToGlobal(pos))
        if action == edit_action:
            self.edit_selected_tag_cell()
        elif action == remove_action:
            self.remove_selected_tag()

    def edit_selected_tag_cell(self):
        item = self.tags_table.currentItem()
        if item:
            self.tags_table.editItem(item)


__all__ = ["_ContextMenusMixin"]
