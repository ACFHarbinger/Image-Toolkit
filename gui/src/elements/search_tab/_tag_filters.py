"""Tag-type and tag checkbox-list filtering for ``SearchTab``.

Extracted from ``search_tab.py`` -- pure code motion, no logic change
(see ``_ui_builder.py``'s docstring).
"""

from __future__ import annotations

from typing import Dict, List, Optional

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QListWidgetItem

from ...utils.sort_utils import natural_sort_key


class _TagFiltersMixin:
    """Tag-type checkbox row and the tag list it filters."""

    def _get_tags_from_db(self) -> List[Dict[str, str]]:
        db = self.db_tab_ref.db
        if not db:
            return []
        try:
            db_tags = db.get_all_tags_with_categories()
            return sorted(db_tags, key=lambda x: natural_sort_key(x["name"]))
        except Exception:
            pass
        return []

    def _get_category_colors(self) -> Dict[str, str]:
        """{category_name: color} from tag_categories, data-driven instead
        of a hardcoded literal so custom/extended categories pick up their
        real color automatically."""
        db = self.db_tab_ref.db
        if not db:
            return {}
        try:
            return {c["name"]: c["color"] for c in db.list_tag_categories()}
        except Exception:
            return {}

    def _get_active_tag_types(self) -> Optional[set]:
        """Return the set of checked tag type names, or None if list is empty."""
        if self.tag_types_list_widget.count() == 0:
            return None
        active = set()
        for i in range(self.tag_types_list_widget.count()):
            item = self.tag_types_list_widget.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                active.add(item.data(Qt.ItemDataRole.UserRole))
        return active

    @Slot()
    def _on_tag_type_changed(self):
        """Rebuild the tags list to only show tags of checked types."""
        self._populate_tags_for_active_types()

    def _populate_tags_for_active_types(self):
        """Re-populate the tags list based on which category checkboxes are checked."""
        active_types = self._get_active_tag_types()
        color_map = self._get_category_colors()
        # Preserve previously checked tag names
        previously_checked = {
            self.tags_list_widget.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self.tags_list_widget.count())
            if self.tags_list_widget.item(i).checkState() == Qt.CheckState.Checked
        }

        self.tags_list_widget.blockSignals(True)
        self.tags_list_widget.clear()

        all_tags = getattr(self, "_all_tags_cache", [])
        for tag_data in all_tags:
            tag_name = tag_data["name"]
            tag_category = tag_data["category"] if tag_data["category"] else ""
            # Filter by active categories
            if active_types is not None and tag_category not in active_types:
                continue
            item = QListWidgetItem(tag_name.replace("_", " ").title())
            item.setData(Qt.ItemDataRole.UserRole, tag_name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked
                if tag_name in previously_checked
                else Qt.CheckState.Unchecked
            )
            text_color = color_map.get(tag_category, "#95a5a6")
            item.setForeground(QColor(text_color))
            self.tags_list_widget.addItem(item)
        self.tags_list_widget.blockSignals(False)

    @Slot()
    def _setup_tag_checkboxes(self):
        tags_data = self._get_tags_from_db()
        self._all_tags_cache = tags_data
        color_map = self._get_category_colors()

        # Build / refresh the tag-category filter row, ordered per
        # tag_categories.sort_order (unknown/legacy names sort last).
        known_categories = list(color_map.keys())
        seen_categories = sorted(
            {(t["category"] or "") for t in tags_data},
            key=lambda x: (
                known_categories.index(x) if x in known_categories else len(known_categories),
                x,
            ),
        )
        self.tag_types_list_widget.blockSignals(True)
        # Keep previously checked categories
        previously_checked_types = {
            self.tag_types_list_widget.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self.tag_types_list_widget.count())
            if self.tag_types_list_widget.item(i).checkState() == Qt.CheckState.Checked
        }
        self.tag_types_list_widget.clear()
        for t in seen_categories:
            display = t if t else "(No Category)"
            item = QListWidgetItem(display)
            item.setData(Qt.ItemDataRole.UserRole, t)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            # All categories start checked; preserve state on refresh
            is_checked = (not previously_checked_types) or (t in previously_checked_types)
            item.setCheckState(
                Qt.CheckState.Checked if is_checked else Qt.CheckState.Unchecked
            )
            item.setForeground(QColor(color_map.get(t, "#95a5a6")))
            self.tag_types_list_widget.addItem(item)
        self.tag_types_list_widget.blockSignals(False)

        # Populate tags list filtered by active types
        self._populate_tags_for_active_types()

    def get_selected_tags(self) -> List[str]:
        return [
            self.tags_list_widget.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self.tags_list_widget.count())
            if self.tags_list_widget.item(i).checkState() == Qt.CheckState.Checked
        ]

    def search_by_tag(self, tag_name: str) -> None:
        """DB.8c: jump here already filtered to a single tag (e.g. from
        Management's tag table "Search Images with this Tag" action).
        Checks every tag-type filter first so the target tag is
        guaranteed to be in the (type-filtered) tags list regardless of
        whatever type filter state was active before."""
        self.clear_filters()
        self.tag_types_list_widget.blockSignals(True)
        for i in range(self.tag_types_list_widget.count()):
            self.tag_types_list_widget.item(i).setCheckState(Qt.CheckState.Checked)
        self.tag_types_list_widget.blockSignals(False)
        self._populate_tags_for_active_types()

        for i in range(self.tags_list_widget.count()):
            item = self.tags_list_widget.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == tag_name:
                item.setCheckState(Qt.CheckState.Checked)
                break
        self.perform_search()


__all__ = ["_TagFiltersMixin"]
