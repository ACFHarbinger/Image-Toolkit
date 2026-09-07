"""Card click/delete handlers, context menu, and save/delete slots.

Extracted from ``entity_listings_subtab.py`` -- pure code motion, no logic
change.
"""

from __future__ import annotations

from typing import Any, Dict

from PySide6.QtCore import Slot
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QMessageBox


class _CardActionsMixin:
    """Per-card actions, the gallery context menu, and save/delete slots."""

    @Slot(str)
    def _on_card_clicked(self, entity_id: str):
        self._selected_id = entity_id
        entity = next((e for e in self._entities if e["id"] == entity_id), None)
        if entity:
            self._detail.load_entity(entity)

    def _on_card_delete_requested(self, entity_id: str):
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            "Permanently remove this entity from your listings?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._on_entity_deleted(entity_id)

    def _show_gallery_context_menu(self, pos):
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background:#2c2f33; color:white; border:1px solid #4f545c; }"
            "QMenu::item:selected { background:#00bcd4; color:black; }"
        )
        add_act = QAction("＋ Add New Entity", self)
        add_act.triggered.connect(self._on_add_new)
        menu.addAction(add_act)
        menu.exec(self.gallery_scroll.mapToGlobal(pos))

    @Slot()
    def _on_add_new(self):
        self._selected_id = None
        self._detail.clear_for_new()

    @Slot(dict)
    def _on_entity_saved(self, entity: Dict[str, Any]):
        idx = next(
            (i for i, e in enumerate(self._entities) if e["id"] == entity["id"]), None
        )
        if idx is not None:
            self._entities[idx] = entity
        else:
            self._entities.insert(0, entity)
        # save_entity writes the entity, its credits, its media links and its
        # peer links in one transaction; the content side reads the same
        # media_entity table, so the old sync loops are gone. Peer entities'
        # in-memory dicts may now be stale — reload from the store.
        if self._upsert_entity(entity):
            self._load_data()
        self.listings_changed.emit()
        self._rebuild_gallery()
        self._detail.load_entity(entity)

    @Slot(str)
    def _on_entity_deleted(self, entity_id: str):
        self._entities = [e for e in self._entities if e["id"] != entity_id]
        # FK cascades remove this entity's credits and association rows
        # (media_entity + entity_entity, both directions).
        self._delete_entity_row(entity_id)
        self.listings_changed.emit()
        self._load_data()
        self._rebuild_gallery()
        self._detail.clear_for_new()

    def _on_external_reload(self) -> None:
        """Called when another subtab modifies entities.json; refreshes in-memory data."""
        self._load_data()
        self._rebuild_gallery()


__all__ = ["_CardActionsMixin"]
