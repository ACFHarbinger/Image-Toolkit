"""Group/subgroup checkbox-list filtering for ``SearchTab``.

Extracted from ``search_tab.py`` -- pure code motion, no logic change
(see ``_ui_builder.py``'s docstring).
"""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import QListWidgetItem


class _GroupFiltersMixin:
    """Group/subgroup checkbox lists, kept in sync with the database."""

    @Slot()
    def _refresh_groups_from_db(self):
        """Load groups and detailed subgroups from the DB and populate both lists."""
        db = self.db_tab_ref.db
        if not db:
            return
        try:
            group_list = db.get_all_groups()
            self.populate_groups_list(group_list)
            self._all_subgroups_detailed = db.get_all_subgroups_detailed()
            self._refresh_subgroups_display()
        except Exception as e:
            print(f"[SearchTab] Error refreshing groups: {e}")

    def populate_groups_list(self, group_list: List[str]):
        """Populate groups_list_widget; preserve existing check states by name."""
        self.groups_list_widget.blockSignals(True)
        previously_checked = {
            self.groups_list_widget.item(i).text()
            for i in range(self.groups_list_widget.count())
            if self.groups_list_widget.item(i).checkState() == Qt.CheckState.Checked
        }
        self.groups_list_widget.clear()
        for name in group_list:
            item = QListWidgetItem(name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked
                if name in previously_checked
                else Qt.CheckState.Unchecked
            )
            self.groups_list_widget.addItem(item)
        self.groups_list_widget.blockSignals(False)
        self._refresh_subgroups_display()

    def populate_subgroups_detailed(self, detailed: List[tuple]):
        """Store the full (subgroup, group) list and refresh the display."""
        self._all_subgroups_detailed = detailed
        self._refresh_subgroups_display()

    @Slot()
    def _on_group_selection_changed(self):
        """When group selection changes, refresh the subgroup list."""
        self._refresh_subgroups_display()

    def _refresh_subgroups_display(self):
        """Show only subgroups belonging to any checked group (or all if none checked)."""
        selected_groups = self.get_selected_groups()
        # Preserve currently checked subgroup names (raw subgroup_name only)
        previously_checked = {
            self.subgroups_list_widget.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self.subgroups_list_widget.count())
            if self.subgroups_list_widget.item(i).checkState() == Qt.CheckState.Checked
        }
        self.subgroups_list_widget.blockSignals(True)
        self.subgroups_list_widget.clear()
        for sub_name, grp_name in self._all_subgroups_detailed:
            if selected_groups and grp_name not in selected_groups:
                continue
            label = f"{grp_name}:: {sub_name}"
            item = QListWidgetItem(label)
            # Store raw subgroup name as user data for search query
            item.setData(Qt.ItemDataRole.UserRole, sub_name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked
                if sub_name in previously_checked
                else Qt.CheckState.Unchecked
            )
            self.subgroups_list_widget.addItem(item)
        self.subgroups_list_widget.blockSignals(False)

    def get_selected_groups(self) -> List[str]:
        return [
            self.groups_list_widget.item(i).text()
            for i in range(self.groups_list_widget.count())
            if self.groups_list_widget.item(i).checkState() == Qt.CheckState.Checked
        ]

    def get_selected_subgroups(self) -> List[str]:
        return [
            self.subgroups_list_widget.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self.subgroups_list_widget.count())
            if self.subgroups_list_widget.item(i).checkState() == Qt.CheckState.Checked
        ]

    def filter_by_group(self, group_name: str) -> None:
        """DB.8a: jump here already filtered to a single group (the
        Content Listings detail panel's "View Images" action). Mirrors
        search_by_tag()'s structure (_tag_filters.py) -- refresh from the
        DB first so a just-linked group that predates this SearchTab
        instance's last group-list refresh is guaranteed to be present,
        clear other filters, then check only the target group."""
        self._refresh_groups_from_db()
        self.groups_list_widget.blockSignals(True)
        for i in range(self.groups_list_widget.count()):
            item = self.groups_list_widget.item(i)
            item.setCheckState(
                Qt.CheckState.Checked
                if item.text() == group_name
                else Qt.CheckState.Unchecked
            )
        self.groups_list_widget.blockSignals(False)
        self._refresh_subgroups_display()
        self.filename_edit.clear()
        self.perform_search()

    def update_search_button_state(self, connected: Optional[bool] = None):
        db_connected = self.db_tab_ref.db is not None if connected is None else connected
        self.search_button.setEnabled(db_connected)

        if not db_connected:
            self.results_count_label.setText("Not connected to database.")
        else:
            if self.results_count_label.text() == "Not connected to database.":
                self.results_count_label.setText("Ready to search.")

        if db_connected and not self._db_was_connected:
            self._setup_tag_checkboxes()
            self._refresh_groups_from_db()
        self._db_was_connected = db_connected


__all__ = ["_GroupFiltersMixin"]
