"""Load an entry into the form (or clear it for a new one).

Extracted from ``detail_panel.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from gui.src.tabs.core.elements.common.listings_common import normalize_id_list
from PySide6.QtCore import QTimer


class _EntryLifecycleMixin:
    """load_entry()/clear_for_new() -- form population and reset."""

    def load_entry(  # noqa: C901
        self,
        entry: Dict[str, Any],
        cached_entities: Optional[List[Dict[str, Any]]] = None,
    ):
        self._entry_id = entry.get("id")
        self._image_path = entry.get("image_path", "")
        self.f_title.setText(entry.get("title", ""))
        self.f_type.setCurrentText(entry.get("type", "Anime"))
        self.f_status.setCurrentText(entry.get("status", "Plan to Watch"))
        self.f_personal_rating.setValue(
            entry.get("personal_rating", entry.get("rating", 0))  # pyrefly: ignore [bad-argument-type]
        )
        self.f_community_rating.setValue(float(entry.get("community_rating", 0.0)))
        self.f_year.setValue(entry.get("year", 0))
        self.f_episodes.setValue(entry.get("episodes", 1))
        self.f_current_episode.setValue(entry.get("current_episode", 0))
        self.assoc_entities_ids = normalize_id_list(entry.get("associated_entities", []))

        self.f_local_file.setText(entry.get("local_file", ""))
        self.f_web_link.setText(entry.get("web_link", ""))

        self._update_assoc_entities_display()
        self._refresh_grouped_tags_display()

        self.f_summary.setPlainText(entry.get("summary", ""))
        self.f_review.setPlainText(entry.get("review", ""))
        self._episode_data = entry.get("episode_list", [])
        self.del_btn.setVisible(True)
        self.episode_group.setVisible(True)

        QTimer.singleShot(0, self._refresh_image)
        QTimer.singleShot(0, self._refresh_episode_list)

    def clear_for_new(self):
        self._entry_id = None
        self._image_path = ""
        self._episode_data = []
        self.f_title.clear()
        self.f_type.setCurrentIndex(0)
        self.f_status.setCurrentIndex(0)
        self.f_personal_rating.setValue(0)
        self.f_community_rating.setValue(0.0)
        self.f_year.setValue(0)
        self.f_episodes.setValue(1)
        self.f_current_episode.setValue(0)
        self.assoc_entities_ids = []
        self.f_assoc_entities_display.clear()
        self.f_assoc_entities_display.setToolTip("")
        self.grouped_tags_display.set_grouped_tags({})
        self.f_local_file.clear()
        self.f_web_link.clear()
        self.f_summary.clear()
        self.f_review.clear()
        self.img_preview.clear()
        self.img_preview.setText("No Image")
        self.img_preview.setStyleSheet("border:2px dashed #4f545c;border-radius:8px;color:#888;font-size:12px;")
        self._refresh_episode_list()
        self.del_btn.setVisible(False)
        self.episode_group.setVisible(False)


__all__ = ["_EntryLifecycleMixin"]
