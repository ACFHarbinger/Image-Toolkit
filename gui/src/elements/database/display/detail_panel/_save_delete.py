"""Form-to-dict collection and the save/delete button slots.

Extracted from ``detail_panel.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any, Dict, Optional

from PySide6.QtCore import Slot
from PySide6.QtWidgets import QMessageBox


class _SaveDeleteMixin:
    """Collects the form into a dict and emits saved/deleted signals."""

    def _collect(self) -> Optional[Dict[str, Any]]:
        title = self.f_title.text().strip()
        if not title:
            QMessageBox.warning(self, "Missing Title", "Please enter a title.")
            return None
        return {
            "id": self._entry_id or str(uuid.uuid4()),
            "title": title,
            "type": self.f_type.currentText(),
            "status": self.f_status.currentText(),
            "personal_rating": self.f_personal_rating.value(),
            "community_rating": round(self.f_community_rating.value(), 2),
            "year": self.f_year.value(),
            "episodes": self.f_episodes.value(),
            "current_episode": self.f_current_episode.value(),
            "associated_entities": self.assoc_entities_ids,
            "local_file": self.f_local_file.text().strip(),
            "web_link": self.f_web_link.text().strip(),
            "summary": self.f_summary.toPlainText().strip(),
            "review": self.f_review.toPlainText().strip(),
            "image_path": self._image_path,
            "episode_list": self._episode_data,
            "date_added": str(date.today()),
        }

    @Slot()
    def _on_save(self):
        entry = self._collect()
        if entry:
            self.saved.emit(entry)

    @Slot()
    def _on_delete(self):
        if not self._entry_id:
            return
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            "Permanently remove this entry from your listings?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.deleted.emit(self._entry_id)


__all__ = ["_SaveDeleteMixin"]
