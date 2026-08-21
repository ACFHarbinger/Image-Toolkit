"""Shared gallery behavior for database record-card listings."""

from __future__ import annotations

from gui.src.classes import AbstractClassTwoGalleries
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QWidget


class ListingGalleryBase(AbstractClassTwoGalleries):
    """Gallery base for record cards rather than filesystem thumbnails.

    Reuses ``AbstractClassTwoGalleries``' search syntax, thumbnail-size
    persistence, lifecycle, and dedicated worker pool while adapting its
    file-oriented navigation and zoom operations to ID-keyed database cards.
    """

    def __init__(self) -> None:
        super().__init__()
        self.thumbnail_size: int = int(getattr(self, "thumbnail_size", 180))
        self._listing_card_size = self.thumbnail_size
        self._listing_card_map: dict[str, QWidget] = {}
        self._listing_page_ids: list[str] = []
        self._focused_listing_index = -1

    def get_default_config(self) -> dict:
        return {"thumbnail_size": 180}

    def set_config(self, config: dict) -> None:
        raw_size = config.get("thumbnail_size", self.thumbnail_size)
        try:
            size = int(raw_size)
        except (TypeError, ValueError):
            size = self.thumbnail_size
        self.thumbnail_size = max(96, min(320, size))
        self._listing_card_size = self.thumbnail_size

    def _on_layout_change(self) -> None:
        if hasattr(self, "_grid"):
            self._rebuild_gallery()

    def _configure_listing_gallery(self, scroll) -> None:
        if hasattr(scroll, "ctrl_wheel"):
            scroll.ctrl_wheel.connect(self._on_listing_zoom)
            self._scroll_zoom_connected = True

    def _on_listing_zoom(self, delta: int) -> None:
        size = max(96, min(320, self._listing_card_size + (16 if delta > 0 else -16)))
        if size == self._listing_card_size:
            return
        self._listing_card_size = size
        self.thumbnail_size = size
        self.approx_item_width = size + self.padding_width + 20
        self._save_thumbnail_size()
        self._rebuild_gallery()

    def _reset_listing_cards(self) -> None:
        self._listing_card_map.clear()
        self._listing_page_ids.clear()
        self._focused_listing_index = -1

    def _register_listing_card(self, item_id: str, card) -> None:
        card.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._listing_card_map[item_id] = card
        self._listing_page_ids.append(item_id)

    def _activate_listing(self, item_id: str) -> None:
        try:
            self._focused_listing_index = self._listing_page_ids.index(item_id)
        except ValueError:
            self._focused_listing_index = -1
        self._on_card_clicked(item_id)

    @staticmethod
    def _has_search_operators(query: str) -> bool:
        return any(marker in query for marker in ('"', "|")) or any(
            token.startswith("-") and len(token) > 1 for token in query.split()
        )

    def _filter_records_with_operators(self, records: list[dict], query: str, text_builder) -> list[dict]:
        indexed = [f"{record.get('id', '')}\0{text_builder(record)}" for record in records]
        matched = self.common_filter_string_list(indexed, query)
        ids = {value.split("\0", 1)[0] for value in matched}
        return [record for record in records if record.get("id") in ids]

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()
        if key not in (
            Qt.Key.Key_Left,
            Qt.Key.Key_Right,
            Qt.Key.Key_Up,
            Qt.Key.Key_Down,
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
            Qt.Key.Key_Space,
        ):
            super().keyPressEvent(event)
            return

        if not self._listing_page_ids:
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            if 0 <= self._focused_listing_index < len(self._listing_page_ids):
                self._activate_listing(self._listing_page_ids[self._focused_listing_index])
            event.accept()
            return

        cols = max(
            1,
            self.gallery_scroll.viewport().width() // max(1, self._listing_card_size + 20),
        )
        index = max(0, self._focused_listing_index)
        if key == Qt.Key.Key_Right:
            index += 1
        elif key == Qt.Key.Key_Left:
            index -= 1
        elif key == Qt.Key.Key_Down:
            index += cols
        elif key == Qt.Key.Key_Up:
            index -= cols
        index = max(0, min(index, len(self._listing_page_ids) - 1))
        self._focused_listing_index = index
        card = self._listing_card_map.get(self._listing_page_ids[index])
        if card is not None:
            card.setFocus()
            self.gallery_scroll.ensureWidgetVisible(card)
        event.accept()


__all__ = ["ListingGalleryBase"]
