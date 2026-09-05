"""Non-visual library session state shared by database-family modules."""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QWidget


class LibraryDatabaseService:
    """The database handle and vault session, never a DatabaseTab widget."""

    def __init__(self, vault_manager: Any = None) -> None:
        self.vault_manager = vault_manager
        self.db: Any = None


LIBRARY_DATABASE_SERVICE = "library-database"


def coerce_library_database_service(candidate: Any) -> LibraryDatabaseService:
    """Adapt legacy non-widget test doubles without retaining a tab instance."""
    if isinstance(candidate, LibraryDatabaseService):
        return candidate
    if isinstance(candidate, QWidget):
        raise TypeError("Database-family modules require LibraryDatabaseService, not QWidget")
    service = LibraryDatabaseService(getattr(candidate, "vault_manager", None))
    service.db = getattr(candidate, "db", None)
    return service


__all__ = ["LIBRARY_DATABASE_SERVICE", "LibraryDatabaseService", "coerce_library_database_service"]
