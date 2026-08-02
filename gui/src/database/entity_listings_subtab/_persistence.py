"""Library-DB persistence: load, repo accessors, upsert/delete.

Extracted from ``entity_listings_subtab.py`` -- pure code motion, no logic
change.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from backend.src.database.unified.entity_repo import EntityRepo
from backend.src.database.unified.search_repo import SearchRepo
from gui.src.helpers.database.library_session import get_library_db
from PySide6.QtWidgets import QMessageBox


class _PersistenceMixin:
    """Loads/saves entities against the unified library database."""

    def _load_data(self):
        self._entities = []

        db = get_library_db(self.vault_manager, parent=self)
        if db is None:
            return
        try:
            self._entities = EntityRepo(db).list_entities()
        except Exception as e:
            logging.exception("[EntityListingsSubTab] Failed to load from library DB")
            QMessageBox.critical(
                self,
                "Library Database Unavailable",
                "Could not load entities from the unified library database:\n"
                f"{e}\n\n"
                "Your existing entities may not be visible, and anything "
                "added or changed in this session will NOT be saved until "
                "this is fixed. Check the app log for details.",
            )

    def _entity_repo(self) -> Optional[EntityRepo]:
        """Return an EntityRepo on the session DB, or None when the vault is locked."""
        db = get_library_db(self.vault_manager, parent=self)
        return EntityRepo(db) if db is not None else None

    def _search_repo(self) -> Optional[SearchRepo]:
        """Return a SearchRepo on the session DB, or None when the vault is locked."""
        db = get_library_db(self.vault_manager, parent=self)
        return SearchRepo(db) if db is not None else None

    def _upsert_entity(self, entity: Dict[str, Any]) -> bool:
        """Persist a single entity in one transaction — the entity row, its
        credits, and both association directions commit (or roll back)
        together via :meth:`EntityRepo.save_entity`.

        Returns ``True`` on success. Callers MUST check this — silently
        swallowing the error here previously meant a newly added entity could
        look saved while never actually reaching disk, only to vanish the
        next time the app was launched."""
        repo = self._entity_repo()
        if repo is None:
            QMessageBox.warning(
                self,
                "Not Saved",
                "The vault is locked (no active password), so this entity was "
                "NOT written to the library database. It will be lost when "
                "you close the app.",
            )
            return False
        try:
            repo.save_entity(entity)
            return True
        except Exception as e:
            logging.exception("[EntityListingsSubTab] Failed to upsert entity")
            QMessageBox.critical(
                self,
                "Save Failed",
                f"Failed to save '{entity.get('name', '')}' to the library "
                f"database:\n{e}\n\n"
                "This entity was NOT persisted and will be lost on restart.",
            )
            return False

    def _delete_entity_row(self, entity_id: str) -> bool:
        """Delete a single entity row; credits and association rows cascade."""
        repo = self._entity_repo()
        if repo is None:
            return False
        try:
            repo.delete_entity(entity_id)
            return True
        except Exception as e:
            logging.exception("[EntityListingsSubTab] Failed to delete entity")
            QMessageBox.critical(
                self,
                "Delete Failed",
                f"Failed to delete entity from the library database:\n{e}",
            )
            return False


__all__ = ["_PersistenceMixin"]
