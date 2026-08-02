"""Gallery filtering/sorting, rebuild, and resize/show events.

Extracted from ``series_listings_subtab.py`` -- pure code motion, no logic
change.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List

from gui.src.constants.listings import CARD_SIZE
from gui.src.elements.database.display.listing_card import _ListingCard
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

# sort_combo display text -> SearchRepo.filter_media's sort_key (DB.5).
_SORT_KEY_MAP = {
    "Sort by: Title": "title",
    "Sort by: Rating": "rating",
    "Sort by: Episodes": "episodes",
    "Sort by: Current Episode": "current_episode",
    "Sort by: Date": "date",
    "Sort by: Type": "type",
    "Sort by: Status": "status",
    "Sort by: Local Filename": "local_file",
    "Sort by: Tags": "tags",
}


class _GalleryMixin:
    """Filters/sorts entries via SearchRepo and rebuilds the card grid."""

    def _filtered_entries(self) -> List[Dict[str, Any]]:
        # Semantic search mode (DB.7): show results sorted by descending
        # similarity score -- same precedence/shape as recommendation mode
        # below, checked first since it's the more specific, explicitly
        # user-triggered state.
        if getattr(self, "_semantic_search_results", None) is not None:
            assert self._semantic_search_results is not None
            sem_map = {mid: score for mid, score in self._semantic_search_results}
            result = [e for e in self._entries if e.get("id") in sem_map]
            result.sort(key=lambda e: sem_map.get(e.get("id", ""), 0.0), reverse=True)
            return result

        # Recommendation mode: show results sorted by descending relevance score
        if getattr(self, "_recommendation_results", None) is not None:
            assert self._recommendation_results is not None
            rec_map = {uid: score for uid, score in self._recommendation_results}
            result = [e for e in self._entries if e.get("id") in rec_map]
            result.sort(key=lambda e: rec_map.get(e.get("id", ""), 0.0), reverse=True)
            return result

        # Search box, type/status combos, and (if active) the Advanced Search
        # dialog's criteria are all evaluated in one SQL query via
        # SearchRepo.filter_media (DB.5) — no more full-list Python scan.
        type_filter = (
            self._filter_type
            if self._filter_type and self._filter_type not in (
                "All", "All Types", "None", "",
            )
            else None
        )
        status_filter = (
            self._filter_status
            if self._filter_status not in ("All", "All Status")
            else None
        )
        sort_field = self.sort_combo.currentText()
        sort_key = _SORT_KEY_MAP.get(sort_field, "title")
        descending = self.sort_order_combo.currentText() == "Descending"

        repo = self._search_repo()
        if repo is None:
            # Vault locked / DB unavailable — nothing better to show than the
            # last loaded snapshot, unfiltered.
            return list(self._entries)

        try:
            ids = repo.filter_media(
                search_query=self._search_query,
                type_filter=type_filter,
                status_filter=status_filter,
                advanced_criteria=self._advanced_search_criteria,
                sort_key=sort_key,
                descending=descending,
            )
        except Exception:
            logging.exception(
                "[SeriesListingsSubTab] SQL filter/sort failed; showing "
                "unfiltered entries"
            )
            return list(self._entries)

        by_id = {e["id"]: e for e in self._entries if "id" in e}
        result = [by_id[i] for i in ids if i in by_id]

        if sort_key == "local_file":
            # Basename-of-path sort isn't expressible in portable SQL (no
            # bundled REVERSE()); SQL already did the filtering above, so
            # this is a sort over the already-filtered subset, not a
            # full-table scan.
            result.sort(
                key=lambda x: Path(x.get("local_file", "")).name.lower()
                if x.get("local_file")
                else "",
                reverse=descending,
            )

        return result

    def _rebuild_gallery(self):
        # Clear old widgets
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater() # pyrefly: ignore [missing-attribute]

        visible = self._filtered_entries()
        if not visible:
            placeholder = QLabel(
                "No entries found.\nClick '＋ Add Entry' to get started."
            )
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            placeholder.setStyleSheet("color:#555;font-size:14px;")
            self._grid.addWidget(placeholder, 0, 0)
        else:
            cols = max(1, self.gallery_scroll.width() // (CARD_SIZE + 20))
            for i, entry in enumerate(visible):
                card = _ListingCard(entry)
                card.clicked.connect(self._on_card_clicked)
                card.add_requested.connect(self._on_add_new)
                card.delete_requested.connect(self._on_card_delete_requested)
                card.image_remove_requested.connect(
                    self._on_card_image_remove_requested
                )
                self._grid.addWidget(card, i // cols, i % cols)

        # Stats
        total = len(self._entries)
        completed = sum(1 for e in self._entries if e.get("status") == "Completed")
        self.stats_label.setText(
            f"{total} entries total · {completed} completed · showing {len(visible)}"
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._resize_timer.start()

    def showEvent(self, event):
        super().showEvent(event)


__all__ = ["_GalleryMixin", "_SORT_KEY_MAP"]
