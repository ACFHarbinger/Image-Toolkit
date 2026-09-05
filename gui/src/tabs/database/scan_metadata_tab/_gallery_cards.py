"""Tag checkbox setup and DB status helpers for ScanMetadataTab.

Card creation and styling are promoted to AbstractClassTwoGalleries (§Issue 446).
"""

from __future__ import annotations

from typing import Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import QListWidgetItem, QWidget


class _GalleryCardsMixin:
    """Tag checkbox population and DB-card creation helper for ScanMetadataTab."""

    def _create_gallery_card(
        self,
        path: str,
        pixmap: Optional[QPixmap],
        is_selected: bool,
        is_in_db: bool = False,
    ) -> QWidget:
        card = self.create_card_widget(path, pixmap, is_selected)
        card.setProperty("in_db", is_in_db)
        if hasattr(self, "update_card_style"):
            self.update_card_style(card, is_selected)
        return card

    def _get_tags_from_db(self) -> List[Dict[str, str]]:
        db = self.database_service.db
        if not db:
            return []
        try:
            return db.get_all_tags_with_categories()
        except Exception:
            pass
        return []

    def _setup_tag_checkboxes(self):
        self.tags_list_widget.clear()

        tags_data = self._get_tags_from_db()

        for tag_data in tags_data:
            tag_name = tag_data["name"]

            item = QListWidgetItem(tag_name.replace("_", " ").title())
            item.setData(Qt.ItemDataRole.UserRole, tag_name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)

            item.setForeground(QColor(tag_data.get("color") or "#95a5a6"))

            self.tags_list_widget.addItem(item)


__all__ = ["_GalleryCardsMixin"]
