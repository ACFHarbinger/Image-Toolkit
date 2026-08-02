"""Grouped-by-category tag display (Danbooru-style tag overhaul): genres,
freeform tags, and tags carried transitively through associated entities
(``MediaRepo.get_grouped_tags``) render together, grouped by category.
"""

from __future__ import annotations

from backend.src.database.unified.media_repo import MediaRepo
from gui.src.helpers.database.library_session import get_library_db


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


__all__ = ["_GroupedTagsMixin"]
