"""Card click/delete/image-remove handlers, context menu, and save/delete slots.

Extracted from ``content_listings_subtab.py`` -- pure code motion, no logic
change.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from gui.src.tabs.core.elements.dialog.advanced_search_dialog import _AdvancedSearchDialog
from PySide6.QtCore import Slot
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QMessageBox
from send2trash import send2trash  # pyrefly: ignore [untyped-import]


class _CardActionsMixin:
    """Advanced search, per-card actions, and the gallery context menu."""

    def _on_advanced_search(self):
        dialog = _AdvancedSearchDialog(
            self, entries=self._entries, entities=self._all_entities
        )
        if self._advanced_search_criteria:
            dialog.load_criteria(self._advanced_search_criteria)

        if dialog.exec():
            criteria = dialog.get_criteria()

            # Check if any criteria is set
            has_crit = any(criteria[k] for k in criteria if k != "match_mode")
            if has_crit:
                self._advanced_search_criteria = criteria
                self.clear_adv_btn.show()
            else:
                self._advanced_search_criteria = None
                self.clear_adv_btn.hide()

            self._rebuild_gallery()

    def _clear_advanced_search(self):
        self._advanced_search_criteria = None
        self.clear_adv_btn.hide()
        self._rebuild_gallery()

    @Slot(str)
    def _on_card_clicked(self, entry_id: str):
        self._selected_id = entry_id
        entry = next((e for e in self._entries if e["id"] == entry_id), None)
        if entry:
            self._detail.load_entry(entry, cached_entities=self._all_entities)

    def _on_card_delete_requested(self, entry_id: str):
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            "Permanently remove this entry from your listings?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._on_entry_deleted(entry_id)

    def _on_card_image_remove_requested(self, entry_id: str):
        prefs = {}
        main_win = self.window()
        if main_win and hasattr(main_win, "cached_creds"):
            prefs = main_win.cached_creds.get("preferences", {})
        send_to_trash_enabled = prefs.get("send_to_trash", True)
        action_name = "Trash" if send_to_trash_enabled else "Permanent Delete"

        reply = QMessageBox.question(
            self,
            f"Confirm {action_name} Image",
            f"Are you sure you want to move the image for this listing to {action_name}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            entry = next((e for e in self._entries if e["id"] == entry_id), None)
            if entry:
                img_path = entry.get("image_path", "")
                if img_path:
                    try:
                        p = Path(img_path)
                        if p.exists() and p.is_file():
                            if send_to_trash_enabled:
                                send2trash(str(p))
                            else:
                                p.unlink(missing_ok=True)
                    except Exception as e:
                        print(f"Failed to delete physical image file: {e}")
                entry["image_path"] = ""
                self._upsert_entry(entry)
                self._rebuild_gallery()
                if self._selected_id == entry_id:
                    self._detail.load_entry(entry, cached_entities=self._all_entities)

    def _show_gallery_context_menu(self, pos):
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background:#2c2f33; color:white; border:1px solid #4f545c; }"
            "QMenu::item:selected { background:#00bcd4; color:black; }"
        )
        add_act = QAction("＋ Add New Content", self)
        add_act.triggered.connect(self._on_add_new)
        menu.addAction(add_act)
        menu.exec(self.gallery_scroll.mapToGlobal(pos))

    @Slot()
    def _on_add_new(self):
        self._selected_id = None
        self._detail.clear_for_new()

    @Slot(dict)
    def _on_entry_saved(self, entry: Dict[str, Any]):
        idx = next(
            (i for i, e in enumerate(self._entries) if e["id"] == entry["id"]), None
        )
        if idx is not None:
            self._entries[idx] = entry
        else:
            self._entries.insert(0, entry)
        # save_media writes the entry AND its media_entity association rows in
        # one transaction; the entity side reads the same table, so the old
        # fetch-all/diff/re-upsert sync loop is gone. Just tell the entity
        # subtab to re-query.
        self._upsert_entry(entry)
        self.entities_changed.emit()
        self._rebuild_gallery()
        self._detail.load_entry(entry, cached_entities=self._all_entities)

    @Slot(str)
    def _on_entry_deleted(self, entry_id: str):
        self._entries = [e for e in self._entries if e["id"] != entry_id]
        # FK cascades remove this entry's association/tag/episode rows.
        self._delete_entry_row(entry_id)
        self.entities_changed.emit()
        self._rebuild_gallery()
        self._detail.clear_for_new()

    def _on_external_reload(self) -> None:
        """Called when another subtab modifies shared data; refreshes in-memory data."""
        self._load_data()
        self._rebuild_gallery()
        if self._selected_id:
            entry = next(
                (e for e in self._entries if e["id"] == self._selected_id), None
            )
            if entry:
                self._detail.load_entry(entry, cached_entities=self._all_entities)


__all__ = ["_CardActionsMixin"]
