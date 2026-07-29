"""Associated-entity selection dialog, display refresh, and MAL auto-associate.

Extracted from ``detail_panel.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.src.database.unified.entity_repo import EntityRepo
from gui.src.helpers.core.library_session import get_library_db
from gui.src.tabs.core.elements.common.listings_common import resolve_entity_id_for_mal_name
from gui.src.tabs.core.elements.dialog import _AssociatedEntitiesDialog
from PySide6.QtWidgets import QMessageBox


class _AssociatedEntitiesMixin:
    """Selects/displays associated entities and auto-associates MAL matches."""

    def _select_associated_entities(self):
        all_entities = []
        db = get_library_db(self.vault_manager, parent=self)
        if db is not None:
            try:
                all_entities = EntityRepo(db).list_entities()
            except Exception as e:
                print(f"Failed to load entities from DB for association: {e}")

        if not all_entities:
            QMessageBox.information(
                self,
                "No Entities Available",
                "There are no entities available in Entity Listings. Please add people or organizations first.",
            )
            return

        dlg = _AssociatedEntitiesDialog(all_entities, self.assoc_entities_ids, parent=self)
        if dlg.exec():
            self.assoc_entities_ids = dlg.get_selected_ids()
            self._update_assoc_entities_display()

    def _update_assoc_entities_display(self, _all_entities: Optional[List[Dict[str, Any]]] = None):
        """Resolve associated entity IDs to names using a fresh DB lookup."""
        del _all_entities  # kept for callers; display always reads live data
        if not self.assoc_entities_ids:
            self.f_assoc_entities_display.setPlainText("")
            self.f_assoc_entities_display.setToolTip("")
            return

        name_map: Dict[str, str] = {}
        db = get_library_db(self.vault_manager, parent=self)
        if db is not None:
            try:
                name_map = EntityRepo(db).name_map()
            except Exception as e:
                print(f"Failed to load entity names: {e}")

        names = [name_map.get(ent_id, ent_id) for ent_id in self.assoc_entities_ids]
        display_text = ", ".join(names)
        self.f_assoc_entities_display.setPlainText(display_text)
        self.f_assoc_entities_display.setToolTip(display_text)

    def _auto_associate_entities(self, data: dict) -> None:  # noqa: C901
        try:
            name_map: dict = {}
            db = get_library_db(self.vault_manager, parent=self)
            if db is not None:
                name_map = EntityRepo(db).name_map()
        except Exception:
            return

        if not name_map:
            return

        name_index: dict[str, str] = {name.strip().lower(): entity_id for entity_id, name in name_map.items() if name}
        current_ids: set[str] = set(self.assoc_entities_ids)
        added_count = 0

        def _try_add(name: str) -> None:
            nonlocal added_count
            eid = resolve_entity_id_for_mal_name(name, name_index)
            if eid and eid not in current_ids:
                current_ids.add(eid)
                added_count += 1

        for name in data.get("studios", []):
            _try_add(name)
        for name in data.get("producers", []):
            _try_add(name)
        for name in data.get("characters", []):
            _try_add(name)
        for name in data.get("voice_actors", []):
            _try_add(name)
        for entry in data.get("staff", []):
            _try_add(entry.get("name", ""))

        if added_count > 0:
            self.assoc_entities_ids = list(current_ids)
            self._update_assoc_entities_display()

        if not data.get("characters_available", True):
            msg = (
                "Character and voice-actor data was not available from MyAnimeList "
                "(this is common for 18+ / adult content). Studios and staff were "
                "matched where possible. Please use 'Select Entities' to add "
                "characters manually."
            )
            QMessageBox.information(self, "Auto-Fill — Partial Results", msg)


__all__ = ["_AssociatedEntitiesMixin"]
