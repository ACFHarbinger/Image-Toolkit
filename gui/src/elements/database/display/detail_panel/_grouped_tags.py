"""Grouped-by-category tag display (Danbooru-style tag overhaul): genres,
freeform tags, and tags carried transitively through associated entities
(``MediaRepo.get_grouped_tags``) render together, grouped by category.
Also the "+" quick-add-tag action next to that section (replaces the old
standalone Genres/Tags text fields).
"""

from __future__ import annotations

from backend.src.database.unified.media_repo import MediaRepo
from backend.src.database.unified.tag_repo import TagRepo
from gui.src.components.dialogs import AddTagDialog
from gui.src.helpers.database.library_session import get_library_db
from PySide6.QtWidgets import QMessageBox


class _GroupedTagsMixin:
    """Refreshes ``self.grouped_tags_display`` from the current entry."""

    def _refresh_grouped_tags_display(self) -> None:
        if not self._entry_id:
            self.grouped_tags_display.set_grouped_tags({})
            return
        db = get_library_db(self.vault_manager, parent=self)
        if db is None:
            self.grouped_tags_display.set_grouped_tags({})
            return
        try:
            grouped = MediaRepo(db).get_grouped_tags(self._entry_id)
        except Exception as e:
            print(f"Failed to load grouped tags: {e}")
            grouped = {}
        self.grouped_tags_display.set_grouped_tags(grouped)

    def _on_add_tag(self) -> None:
        if not self._entry_id:
            QMessageBox.information(
                self, "Save First", "Save this entry before adding tags."
            )
            return
        db = get_library_db(self.vault_manager, parent=self)
        if db is None:
            QMessageBox.warning(self, "Error", "The library database is not available.")
            return
        try:
            tag_repo = TagRepo(db)
            categories = tag_repo.list_categories(applies_to="listing")
            all_tags = tag_repo.get_all_tags()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load tag vocabulary:\n{e}")
            return

        dlg = AddTagDialog(categories, all_tags, parent=self)
        if not dlg.exec():
            return
        name, category = dlg.get_data()
        if not name:
            return
        try:
            MediaRepo(db).add_tag(self._entry_id, name, category)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to add tag:\n{e}")
            return
        self._refresh_grouped_tags_display()


__all__ = ["_GroupedTagsMixin"]
