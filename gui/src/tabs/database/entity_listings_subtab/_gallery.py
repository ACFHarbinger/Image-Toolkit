"""Gallery filtering/sorting, rebuild, and resize/show events.

Extracted from ``entity_listings_subtab.py`` -- pure code motion, no logic
change.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Dict, List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from gui.src.constants.elements import ENTITY_LISTINGS_SUBTAB__SORT_KEY_MAP
from gui.src.constants.listings import CARD_SIZE
from gui.src.elements.database.display.entity_card import _EntityCard

# sort_combo display text -> SearchRepo.filter_entities's sort_key (DB.5).


class _GalleryMixin:
    """Filters/sorts entities via SearchRepo and rebuilds the card grid."""

    def _filtered_entities(self) -> List[Dict[str, Any]]:
        # Semantic search mode (DB.7): show results sorted by descending
        # similarity score, same shape as series_listings_subtab's
        # _recommendation_results precedence.
        if getattr(self, "_semantic_search_results", None) is not None:
            assert self._semantic_search_results is not None
            sem_map = {eid: score for eid, score in self._semantic_search_results}
            result = [e for e in self._entities if e.get("id") in sem_map]
            result.sort(key=lambda e: sem_map.get(e.get("id", ""), 0.0), reverse=True)
            return result

        # Search box (name/notes/associated-content-title) and type/role
        # combos are evaluated in one SQL query via SearchRepo.filter_entities
        # (DB.5) — replaces the old per-keystroke full-table title-map
        # rebuild (O(N·M): N entities x M media rows) with a single query.
        type_filter = (
            self._filter_type
            if self._filter_type and self._filter_type not in (
                "All", "All Types", "None", "",
            )
            else None
        )
        role_filter = (
            self._filter_role if self._filter_role not in ("All", "All Roles") else None
        )
        sort_text = self.sort_combo.currentText()
        sort_key = ENTITY_LISTINGS_SUBTAB__SORT_KEY_MAP.get(sort_text, "name")
        descending = self.sort_order_combo.currentText() == "Descending"

        repo = self._search_repo()
        if repo is None:
            # Vault locked / DB unavailable — nothing better to show than the
            # last loaded snapshot, unfiltered.
            return list(self._entities)

        try:
            ids = repo.filter_entities(
                search_query=self._search_query,
                type_filter=type_filter,
                role_filter=role_filter,
                sort_key=sort_key,
                descending=descending,
            )
        except Exception:
            logging.exception(
                "[EntityListingsSubTab] SQL filter/sort failed; showing "
                "unfiltered entities"
            )
            return list(self._entities)

        by_id = {e["id"]: e for e in self._entities if "id" in e}
        return [by_id[i] for i in ids if i in by_id]

    def _rebuild_gallery(self):
        # Clear old widgets
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater() # pyrefly: ignore [missing-attribute]

        visible = self._filtered_entities()
        total_pages = max(1, math.ceil(len(visible) / self._listing_page_size))
        self._listing_page = min(self._listing_page, total_pages - 1)
        start = self._listing_page * self._listing_page_size
        page_entities = visible[start : start + self._listing_page_size]

        if not visible:
            placeholder = QLabel(
                "No entities found.\nClick '＋ Add Entity' to get started."
            )
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            placeholder.setStyleSheet("color:#555;font-size:14px;")
            self._grid.addWidget(placeholder, 0, 0)
        else:
            cols = max(1, self.gallery_scroll.width() // (CARD_SIZE + 20))
            for i, entity in enumerate(page_entities):
                card = _EntityCard(entity)
                card.clicked.connect(self._on_card_clicked)
                card.add_requested.connect(self._on_add_new)
                card.delete_requested.connect(self._on_card_delete_requested)
                self._grid.addWidget(card, i // cols, i % cols)

        # Stats
        total = len(self._entities)
        completed = sum(1 for e in self._entities if e.get("rating", 0) >= 8)
        self.stats_label.setText(
            f"{total} entities total · {completed} highly rated (>=8) · showing {len(visible)}"
        )
        self._page_label.setText(f"Page {self._listing_page + 1} / {total_pages}")
        self._page_prev_btn.setEnabled(self._listing_page > 0)
        self._page_next_btn.setEnabled(self._listing_page + 1 < total_pages)

    def _change_listing_page(self, delta: int) -> None:
        self._listing_page = max(0, self._listing_page + delta)
        self._rebuild_gallery()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._resize_timer.start()

    def showEvent(self, event):
        super().showEvent(event)

    def _on_sort_changed(self, text):
        self._listing_page = 0
        self._rebuild_gallery()


__all__ = ["_GalleryMixin", "ENTITY_LISTINGS_SUBTAB__SORT_KEY_MAP"]
