"""Create/remove methods for groups, subgroups, and tags on ``DatabaseTab``.

Extracted from ``database_tab.py`` -- pure code motion, no logic change
(see ``_ui_connection.py``'s docstring).
"""

from __future__ import annotations

from PySide6.QtWidgets import QInputDialog, QMessageBox


class _CrudMixin:
    """Create and remove groups/subgroups/tags."""

    def create_new_group(self):
        if not self.db:
            QMessageBox.warning(self, "Error", "Please connect to a database first")
            return
        group_names_str = self.new_group_name_edit.text().strip()
        group_names = [
            name.strip() for name in group_names_str.split(",") if name.strip()
        ]
        if not group_names:
            QMessageBox.warning(self, "Error", "Group Name(s) cannot be empty.")
            return
        try:
            count = 0
            for name in group_names:
                self.db.add_group(name)
                count += 1
            QMessageBox.information(
                self, "Success", f"Successfully created {count} group(s)."
            )
            self.new_group_name_edit.clear()
            self.refresh_groups_list()
            self.update_statistics()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create groups:\n{str(e)}")

    def create_new_subgroup(self):
        if not self.db:
            QMessageBox.warning(self, "Error", "Please connect to a database first")
            return
        parent_group = self.new_subgroup_parent_combo.currentText().strip()
        if not parent_group:
            QMessageBox.warning(
                self, "Error", "You must select or enter a Parent Group."
            )
            return
        subgroup_names_str = self.new_subgroup_name_edit.text().strip()
        subgroup_names = [
            name.strip() for name in subgroup_names_str.split(",") if name.strip()
        ]
        if not subgroup_names:
            QMessageBox.warning(self, "Error", "Subgroup Name(s) cannot be empty.")
            return
        try:
            self.db.add_group(parent_group)
            count = 0
            for name in subgroup_names:
                self.db.add_subgroup(name, parent_group)
                count += 1
            QMessageBox.information(
                self,
                "Success",
                f"Successfully created {count} subgroup(s) for '{parent_group}'.",
            )
            self.new_subgroup_name_edit.clear()
            self._refresh_all_group_combos()
            self.new_subgroup_parent_combo.setCurrentText(parent_group)
            if self.existing_subgroups_filter_combo.currentText() == parent_group:
                self.refresh_subgroups_list()
            self.refresh_subgroup_autocomplete()
            self.update_statistics()
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to create subgroups:\n{str(e)}"
            )

    def create_new_tag(self):
        if not self.db:
            QMessageBox.warning(self, "Error", "Please connect to a database first")
            return
        tag_names_str = self.new_tag_name_edit.text().strip()
        tag_type = self.new_tag_type_combo.currentText().strip().title()
        tag_names = [name.strip() for name in tag_names_str.split(",") if name.strip()]
        if not tag_names:
            QMessageBox.warning(self, "Error", "Tag Name(s) cannot be empty.")
            return
        try:
            count = 0
            for name in tag_names:
                self.db.add_tag(name, tag_type if tag_type else None)
                count += 1
            QMessageBox.information(
                self, "Success", f"Successfully created/updated {count} tag(s)."
            )
            self.new_tag_name_edit.clear()
            self.new_tag_type_combo.setCurrentIndex(0)
            self.refresh_tags_list()
            self.update_statistics()
            if self.scan_tab_ref:
                self.scan_tab_ref._setup_tag_checkboxes()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create tags:\n{str(e)}")

    def remove_selected_group(self):
        self.old_edit_value = None
        if not self.db:
            QMessageBox.warning(self, "Error", "Please connect to a database first")
            return
        current_row = self.groups_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(
                self, "Error", "Please select a group from the list to remove."
            )
            return
        item = self.groups_table.item(current_row, 0)
        group_name = item.text()  # pyrefly: ignore [missing-attribute]
        confirm = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete the group '{group_name}'?\n\n"
            f"WARNING: This will also delete ALL associated subgroups.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            try:
                self.db.delete_group(group_name)
                self.refresh_groups_list()
                self.refresh_subgroups_list()
                self.refresh_subgroup_autocomplete()
                self.update_statistics()
                QMessageBox.information(
                    self, "Success", f"Group '{group_name}' and its subgroups removed."
                )
            except Exception as e:
                QMessageBox.critical(
                    self, "Error", f"Failed to remove group:\n{str(e)}"
                )

    def remove_selected_subgroup(self):
        self.old_edit_value = None
        if not self.db:
            QMessageBox.warning(self, "Error", "Please connect to a database first")
            return
        current_row = self.subgroups_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(
                self, "Error", "Please select a subgroup from the list to remove."
            )
            return
        item_subgroup = self.subgroups_table.item(current_row, 0)
        item_group = self.subgroups_table.item(current_row, 1)
        subgroup_name = item_subgroup.text()  # pyrefly: ignore [missing-attribute]
        group_name = item_group.text()  # pyrefly: ignore [missing-attribute]
        confirm = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete the subgroup '{subgroup_name}' from group '{group_name}'?\n\n"
            f"(Note: This only removes the subgroup from this list. Images already using this name will not be affected.)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            try:
                self.db.delete_subgroup(subgroup_name, group_name)
                self.refresh_subgroups_list()
                self.refresh_subgroup_autocomplete()
                self.update_statistics()
                QMessageBox.information(
                    self, "Success", f"Subgroup '{subgroup_name}' removed."
                )
            except Exception as e:
                QMessageBox.critical(
                    self, "Error", f"Failed to remove subgroup:\n{str(e)}"
                )

    def remove_selected_tag(self):
        self.old_edit_value = None
        if not self.db:
            QMessageBox.warning(self, "Error", "Please connect to a database first")
            return
        current_row = self.tags_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(
                self, "Error", "Please select a tag from the list to remove."
            )
            return
        item = self.tags_table.item(current_row, 0)
        tag_name = item.text()  # pyrefly: ignore [missing-attribute]
        confirm = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete the tag '{tag_name}'?\n\n"
            f"WARNING: This will also remove this tag from ALL images that use it.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            try:
                self.db.delete_tag(tag_name)
                self.refresh_tags_list()
                self.update_statistics()
                if self.scan_tab_ref:
                    self.scan_tab_ref._setup_tag_checkboxes()
                QMessageBox.information(self, "Success", f"Tag '{tag_name}' removed.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to remove tag:\n{str(e)}")

    def merge_selected_tag(self):
        """DB.8c: repoint every image/media reference from the selected
        (source) tag to a chosen destination tag, then drop the source --
        cleans up the case/underscore duplicates the old CSV-genre split
        used to produce."""
        if not self.db:
            QMessageBox.warning(self, "Error", "Please connect to a database first")
            return
        current_row = self.tags_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(
                self, "Error", "Please select a tag from the list to merge."
            )
            return
        item = self.tags_table.item(current_row, 0)
        source_name = item.text()  # pyrefly: ignore [missing-attribute]

        candidates = [t for t in self.db.get_all_tags() if t != source_name]
        if not candidates:
            QMessageBox.information(
                self, "Merge Tags", "There is no other tag to merge into."
            )
            return

        dest_name, ok = QInputDialog.getItem(
            self,
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
            self,
            "Confirm Merge",
            f"Merge '{source_name}' into '{dest_name}'? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.No:
            return

        try:
            self.db.merge_tags(source_name, dest_name)
            self.refresh_tags_list()
            self.update_statistics()
            if self.scan_tab_ref:
                self.scan_tab_ref._setup_tag_checkboxes()
            QMessageBox.information(
                self, "Success", f"'{source_name}' merged into '{dest_name}'."
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to merge tags:\n{str(e)}")

    def search_images_with_selected_tag(self):
        """DB.8c: "click a tag anywhere -> search images with this tag."
        Filters the Search tab's state via DatabaseTab.search_tab_ref
        (the same cross-tab reference every "Send To..." action in
        SearchTab already uses) and switches MainWindow to it directly --
        see search_listings_with_selected_tag()'s docstring for the
        tab-activation mechanism this reuses.
        """
        current_row = self.tags_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(
                self, "Error", "Please select a tag from the list first."
            )
            return
        item = self.tags_table.item(current_row, 0)
        tag_name = item.text()  # pyrefly: ignore [missing-attribute]

        if not self.search_tab_ref:
            QMessageBox.warning(self, "Error", "Search Tab reference not found.")
            return

        self.search_tab_ref.search_by_tag(tag_name)
        if self.main_window_ref is not None:
            self.main_window_ref.command_combo.setCurrentText("Library Database")
            self.main_window_ref._select_tab_by_name("Image Search")
        else:
            QMessageBox.information(
                self, "Search Started",
                f"Searching images tagged '{tag_name}' in the Search tab.",
            )

    def search_listings_with_selected_tag(self):
        """DB.8c: "click a tag anywhere -> search listings with this tag."
        Entities have no tags in the unified schema (only media_items and
        images do -- see backend/src/database/unified/schema.sql), so this
        targets Series Listings only. Its search box already matches
        tags/genres, not just titles (SearchRepo.filter_media(),
        DB.5) -- no new filter UI needed, just set the existing box.

        Reuses the real tab-activation mechanism MainWindow's Ctrl+T tab
        search already exercises internally (command_combo +
        _select_tab_by_name -- see gui/src/windows/main/_tab_search.py's
        _activate()), via DatabaseTab.main_window_ref/listings_tab_ref,
        both threaded in by gui/src/windows/main/_tab_registry.py the same
        way as every other *_tab_ref on this class.
        """
        current_row = self.tags_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(
                self, "Error", "Please select a tag from the list first."
            )
            return
        item = self.tags_table.item(current_row, 0)
        tag_name = item.text()  # pyrefly: ignore [missing-attribute]

        if not self.listings_tab_ref:
            QMessageBox.warning(self, "Error", "Listings Tab reference not found.")
            return

        series_listings = self.listings_tab_ref.series_listings
        self.listings_tab_ref.tab_widget.setCurrentWidget(series_listings)
        series_listings.search_box.setText(tag_name)

        if self.main_window_ref is not None:
            self.main_window_ref.command_combo.setCurrentText("Library Database")
            self.main_window_ref._select_tab_by_name("Listings")
        else:
            QMessageBox.information(
                self, "Search Started",
                f"Searching listings tagged '{tag_name}' in the Listings tab.",
            )


__all__ = ["_CrudMixin"]
