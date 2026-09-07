"""Right-click context menu controller for ``DatabaseTab`` (§5.17, #544)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtWidgets import QMenu

if TYPE_CHECKING:
    pass


class DatabaseContextMenuController:
    """Edit/Remove/Merge context menus for the three management tables."""

    def __init__(self, tab: Any) -> None:
        self.tab = tab

    def show_group_context_menu(self, pos) -> None:
        tab = self.tab
        item = tab.groups_table.itemAt(pos)
        if not item:
            return
        menu = QMenu(tab)
        edit_action = menu.addAction("Edit Group")
        remove_action = menu.addAction("Remove Group")
        action = menu.exec(tab.groups_table.mapToGlobal(pos))
        if action == edit_action:
            self.edit_selected_group_cell()
        elif action == remove_action:
            tab.remove_selected_group()

    def edit_selected_group_cell(self) -> None:
        item = self.tab.groups_table.currentItem()
        if item:
            self.tab.groups_table.editItem(item)

    def show_subgroup_context_menu(self, pos) -> None:
        tab = self.tab
        item = tab.subgroups_table.itemAt(pos)
        if not item:
            return
        menu = QMenu(tab)
        edit_action = menu.addAction("Edit Subgroup") if item.column() == 0 else None
        remove_action = menu.addAction("Remove Subgroup")
        action = menu.exec(tab.subgroups_table.mapToGlobal(pos))
        if action == edit_action:
            self.edit_selected_subgroup_cell()
        elif action == remove_action:
            tab.remove_selected_subgroup()

    def edit_selected_subgroup_cell(self) -> None:
        tab = self.tab
        current_row = tab.subgroups_table.currentRow()
        if current_row < 0:
            return
        item_to_edit = tab.subgroups_table.item(current_row, 0)
        if item_to_edit:
            tab.subgroups_table.editItem(item_to_edit)

    def show_tag_context_menu(self, pos) -> None:
        tab = self.tab
        item = tab.tags_table.itemAt(pos)
        if not item:
            return
        menu = QMenu(tab)
        edit_action = menu.addAction("Edit Cell")
        merge_action = menu.addAction("🔀 Merge Into…")
        search_action = menu.addAction("🔍 Search Images with this Tag")
        search_listings_action = menu.addAction("🔍 Search Listings with this Tag")
        remove_action = menu.addAction("Remove Tag")
        action = menu.exec(tab.tags_table.mapToGlobal(pos))
        if action == edit_action:
            self.edit_selected_tag_cell()
        elif action == merge_action:
            tab.merge_selected_tag()
        elif action == search_action:
            tab.search_images_with_selected_tag()
        elif action == search_listings_action:
            tab.search_listings_with_selected_tag()
        elif action == remove_action:
            tab.remove_selected_tag()

    def edit_selected_tag_cell(self) -> None:
        item = self.tab.tags_table.currentItem()
        if item:
            self.tab.tags_table.editItem(item)


# Backward-compatible alias
_ContextMenusMixin = DatabaseContextMenuController

__all__ = ["DatabaseContextMenuController", "_ContextMenusMixin"]
