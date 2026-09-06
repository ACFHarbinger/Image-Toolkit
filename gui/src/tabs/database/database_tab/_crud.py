"""Create/remove controller for groups, subgroups, and tags on ``DatabaseTab`` (§5.17, #544)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtWidgets import QInputDialog, QMessageBox

from gui.src.modules.events import FilterByTagIntent, NavigateIntent

if TYPE_CHECKING:
    pass


class DatabaseCrudController:
    """Create and remove groups/subgroups/tags for DatabaseTab."""

    def __init__(self, tab: Any) -> None:
        self.tab = tab

    def create_new_group(self) -> None:
        tab = self.tab
        if not tab.db:
            QMessageBox.warning(tab, "Error", "Please connect to a database first")
            return
        group_names_str = tab.new_group_name_edit.text().strip()
        group_names = [
            name.strip() for name in group_names_str.split(",") if name.strip()
        ]
        if not group_names:
            QMessageBox.warning(tab, "Error", "Group Name(s) cannot be empty.")
            return
        try:
            count = 0
            for name in group_names:
                tab.db.add_group(name)
                count += 1
            QMessageBox.information(
                tab, "Success", f"Successfully created {count} group(s)."
            )
            tab.new_group_name_edit.clear()
            tab.refresh_groups_list()
            tab.update_statistics()
        except Exception as e:
            QMessageBox.critical(tab, "Error", f"Failed to create groups:\n{str(e)}")

    def create_new_subgroup(self) -> None:
        tab = self.tab
        if not tab.db:
            QMessageBox.warning(tab, "Error", "Please connect to a database first")
            return
        parent_group = tab.new_subgroup_parent_combo.currentText().strip()
        if not parent_group:
            QMessageBox.warning(
                tab, "Error", "You must select or enter a Parent Group."
            )
            return
        subgroup_names_str = tab.new_subgroup_name_edit.text().strip()
        subgroup_names = [
            name.strip() for name in subgroup_names_str.split(",") if name.strip()
        ]
        if not subgroup_names:
            QMessageBox.warning(tab, "Error", "Subgroup Name(s) cannot be empty.")
            return
        try:
            tab.db.add_group(parent_group)
            count = 0
            for name in subgroup_names:
                tab.db.add_subgroup(name, parent_group)
                count += 1
            QMessageBox.information(
                tab,
                "Success",
                f"Successfully created {count} subgroup(s) for '{parent_group}'.",
            )
            tab.new_subgroup_name_edit.clear()
            tab._refresh_all_group_combos()
            tab.new_subgroup_parent_combo.setCurrentText(parent_group)
            if tab.existing_subgroups_filter_combo.currentText() == parent_group:
                tab.refresh_subgroups_list()
            tab.refresh_subgroup_autocomplete()
            tab.update_statistics()
        except Exception as e:
            QMessageBox.critical(
                tab, "Error", f"Failed to create subgroups:\n{str(e)}"
            )

    def create_new_tag(self) -> None:
        tab = self.tab
        if not tab.db:
            QMessageBox.warning(tab, "Error", "Please connect to a database first")
            return
        tag_names_str = tab.new_tag_name_edit.text().strip()
        tag_type = tab.new_tag_type_combo.currentText().strip().title()
        tag_names = [name.strip() for name in tag_names_str.split(",") if name.strip()]
        if not tag_names:
            QMessageBox.warning(tab, "Error", "Tag Name(s) cannot be empty.")
            return
        try:
            count = 0
            for name in tag_names:
                tab.db.add_tag(name, tag_type if tag_type else None)
                count += 1
            QMessageBox.information(
                tab, "Success", f"Successfully created/updated {count} tag(s)."
            )
            tab.new_tag_name_edit.clear()
            tab.new_tag_type_combo.setCurrentIndex(0)
            tab.refresh_tags_list()
            tab.update_statistics()
            tab._publish_tag_catalog_changed()
        except Exception as e:
            QMessageBox.critical(tab, "Error", f"Failed to create tags:\n{str(e)}")

    def remove_selected_group(self) -> None:
        tab = self.tab
        tab.old_edit_value = None
        if not tab.db:
            QMessageBox.warning(tab, "Error", "Please connect to a database first")
            return
        current_row = tab.groups_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(
                tab, "Error", "Please select a group from the list to remove."
            )
            return
        item = tab.groups_table.item(current_row, 0)
        group_name = item.text()  # pyrefly: ignore [missing-attribute]
        confirm = QMessageBox.question(
            tab,
            "Confirm Delete",
            f"Are you sure you want to delete the group '{group_name}'?\n\n"
            f"WARNING: This will also delete ALL associated subgroups.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            try:
                tab.db.delete_group(group_name)
                tab.refresh_groups_list()
                tab.refresh_subgroups_list()
                tab.refresh_subgroup_autocomplete()
                tab.update_statistics()
                QMessageBox.information(
                    tab, "Success", f"Group '{group_name}' and its subgroups removed."
                )
            except Exception as e:
                QMessageBox.critical(
                    tab, "Error", f"Failed to remove group:\n{str(e)}"
                )

    remove_selected_groups = remove_selected_group

    def remove_selected_subgroup(self) -> None:
        tab = self.tab
        tab.old_edit_value = None
        if not tab.db:
            QMessageBox.warning(tab, "Error", "Please connect to a database first")
            return
        current_row = tab.subgroups_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(
                tab, "Error", "Please select a subgroup from the list to remove."
            )
            return
        item_subgroup = tab.subgroups_table.item(current_row, 0)
        item_group = tab.subgroups_table.item(current_row, 1)
        subgroup_name = item_subgroup.text()  # pyrefly: ignore [missing-attribute]
        group_name = item_group.text()  # pyrefly: ignore [missing-attribute]
        confirm = QMessageBox.question(
            tab,
            "Confirm Delete",
            f"Are you sure you want to delete the subgroup '{subgroup_name}' from group '{group_name}'?\n\n"
            f"(Note: This only removes the subgroup from this list. Images already using this name will not be affected.)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            try:
                tab.db.delete_subgroup(subgroup_name, group_name)
                tab.refresh_subgroups_list()
                tab.refresh_subgroup_autocomplete()
                tab.update_statistics()
                QMessageBox.information(
                    tab, "Success", f"Subgroup '{subgroup_name}' removed."
                )
            except Exception as e:
                QMessageBox.critical(
                    tab, "Error", f"Failed to remove subgroup:\n{str(e)}"
                )

    remove_selected_subgroups = remove_selected_subgroup

    def remove_selected_tag(self) -> None:
        tab = self.tab
        tab.old_edit_value = None
        if not tab.db:
            QMessageBox.warning(tab, "Error", "Please connect to a database first")
            return
        current_row = tab.tags_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(
                tab, "Error", "Please select a tag from the list to remove."
            )
            return
        item = tab.tags_table.item(current_row, 0)
        tag_name = item.text()  # pyrefly: ignore [missing-attribute]
        confirm = QMessageBox.question(
            tab,
            "Confirm Delete",
            f"Are you sure you want to delete the tag '{tag_name}'?\n\n"
            f"WARNING: This will also remove this tag from ALL images that use it.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            try:
                tab.db.delete_tag(tag_name)
                tab.refresh_tags_list()
                tab.update_statistics()
                tab._publish_tag_catalog_changed()
                QMessageBox.information(tab, "Success", f"Tag '{tag_name}' removed.")
            except Exception as e:
                QMessageBox.critical(tab, "Error", f"Failed to remove tag:\n{str(e)}")

    remove_selected_tags = remove_selected_tag

    def merge_selected_tag(self) -> None:
        tab = self.tab
        if not tab.db:
            QMessageBox.warning(tab, "Error", "Please connect to a database first")
            return
        current_row = tab.tags_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(
                tab, "Error", "Please select a tag from the list to merge."
            )
            return
        item = tab.tags_table.item(current_row, 0)
        source_name = item.text()  # pyrefly: ignore [missing-attribute]

        candidates = [t for t in tab.db.get_all_tags() if t != source_name]
        if not candidates:
            QMessageBox.information(
                tab, "Merge Tags", "There is no other tag to merge into."
            )
            return

        dest_name, ok = QInputDialog.getItem(
            tab,
            "Merge Tags",
            f"Merge '{source_name}' into which tag?\n\n"
            f"Every image/media reference to '{source_name}' will be "
            f"repointed to the destination, and '{source_name}' will be deleted.",
            candidates,
            editable=False,
        )
        if not ok or not dest_name:
            return

        confirm = QMessageBox.question(
            tab,
            "Confirm Merge",
            f"Merge '{source_name}' into '{dest_name}'? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.No:
            return

        try:
            tab.db.merge_tags(source_name, dest_name)
            tab.refresh_tags_list()
            tab.update_statistics()
            tab._publish_tag_catalog_changed()
            QMessageBox.information(
                tab, "Success", f"'{source_name}' merged into '{dest_name}'."
            )
        except Exception as e:
            QMessageBox.critical(tab, "Error", f"Failed to merge tags:\n{str(e)}")

    def search_images_with_selected_tag(self) -> None:
        tab = self.tab
        current_row = tab.tags_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(
                tab, "Error", "Please select a tag from the list first."
            )
            return
        item = tab.tags_table.item(current_row, 0)
        tag_name = item.text()  # pyrefly: ignore [missing-attribute]

        if tab.event_hub is None:
            QMessageBox.warning(tab, "Error", "Search navigation is unavailable.")
            return

        tab.event_hub.publish(
            FilterByTagIntent(origin="library.management", module_id="library.search", tag_name=tag_name)
        )
        tab.event_hub.publish(NavigateIntent(origin="library.management", module_id="library.search"))

    def search_listings_with_selected_tag(self) -> None:
        tab = self.tab
        current_row = tab.tags_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(
                tab, "Error", "Please select a tag from the list first."
            )
            return
        item = tab.tags_table.item(current_row, 0)
        tag_name = item.text()  # pyrefly: ignore [missing-attribute]

        if tab.event_hub is None:
            QMessageBox.warning(tab, "Error", "Listings navigation is unavailable.")
            return

        tab.event_hub.publish(
            FilterByTagIntent(origin="library.management", module_id="library.listings", tag_name=tag_name)
        )
        tab.event_hub.publish(NavigateIntent(origin="library.management", module_id="library.listings"))


# Backward-compatible alias
_CrudMixin = DatabaseCrudController

__all__ = ["DatabaseCrudController", "_CrudMixin"]
