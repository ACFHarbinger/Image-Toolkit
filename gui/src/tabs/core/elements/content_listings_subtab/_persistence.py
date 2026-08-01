"""Library-DB persistence: load, repo accessors, upsert/delete.

Extracted from ``content_listings_subtab.py`` -- pure code motion, no logic
change.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from backend.src.database.unified.entity_repo import EntityRepo
from backend.src.database.unified.media_repo import MediaRepo
from backend.src.database.unified.search_repo import SearchRepo
from gui.src.helpers.database.library_session import get_library_db
from PySide6.QtWidgets import QMessageBox


class _PersistenceMixin:
    """Loads/saves content entries against the unified library database."""

    def _load_data(self):
        self._entries = []
        self._all_entities = []

        db = get_library_db(self.vault_manager, parent=self)
        if db is None:
            return
        try:
            self._entries = MediaRepo(db).list_media()
            self._all_entities = EntityRepo(db).list_entities()
        except Exception as e:
            logging.exception("[ContentListingsSubTab] Failed to load from library DB")
            QMessageBox.critical(
                self,
                "Library Database Unavailable",
                "Could not load listings from the unified library database:\n"
                f"{e}\n\n"
                "Your existing listings may not be visible, and anything "
                "added or changed in this session will NOT be saved until "
                "this is fixed. Check the app log for details.",
            )

    def _media_repo(self) -> Optional[MediaRepo]:
        """Return a MediaRepo on the session DB, or None when the vault is locked."""
        db = get_library_db(self.vault_manager, parent=self)
        return MediaRepo(db) if db is not None else None

    def _search_repo(self) -> Optional[SearchRepo]:
        """Return a SearchRepo on the session DB, or None when the vault is locked."""
        db = get_library_db(self.vault_manager, parent=self)
        return SearchRepo(db) if db is not None else None

    def _upsert_entry(self, entry: Dict[str, Any]) -> bool:
        """Persist a single content entry in one transaction — the entry row,
        its episodes, its genre/tag links, and its entity associations all
        commit (or roll back) together via :meth:`MediaRepo.save_media`.

        Returns ``True`` on success. Callers MUST check this and warn the user
        on failure — silently swallowing the error here previously meant a
        newly added entry could look saved (present in the in-memory list and
        the gallery) while never actually reaching disk, only to vanish the
        next time the app was launched."""
        repo = self._media_repo()
        if repo is None:
            QMessageBox.warning(
                self,
                "Not Saved",
                "The vault is locked (no active password), so this entry was "
                "NOT written to the library database. It will be lost when "
                "you close the app.",
            )
            return False
        try:
            repo.save_media(entry)
            return True
        except Exception as e:
            logging.exception("[ContentListingsSubTab] Failed to upsert entry")
            QMessageBox.critical(
                self,
                "Save Failed",
                f"Failed to save '{entry.get('title', '')}' to the library "
                f"database:\n{e}\n\n"
                "This entry was NOT persisted and will be lost on restart.",
            )
            return False

    def _delete_entry_row(self, entry_id: str) -> bool:
        """Delete a single content row; episodes/tag links/associations cascade."""
        repo = self._media_repo()
        if repo is None:
            return False
        try:
            repo.delete_media(entry_id)
            return True
        except Exception as e:
            logging.exception("[ContentListingsSubTab] Failed to delete entry")
            QMessageBox.critical(
                self,
                "Delete Failed",
                f"Failed to delete entry from the library database:\n{e}",
            )
            return False


__all__ = ["_PersistenceMixin"]
