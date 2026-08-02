"""MyAnimeList auto-fill worker dispatch and result handling.

Extracted from ``detail_panel.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

from gui.src.constants.listings import ENTRY_STATUS
from gui.src.helpers.web.mal_sync_worker import MalSyncWorker
from PySide6.QtCore import Slot
from PySide6.QtWidgets import QMessageBox


class _MalSyncMixin:
    """Fetches MAL metadata via a background worker and applies the result."""

    @Slot()
    def _on_fetch_mal_clicked(self):
        title = self.f_title.text().strip()
        if not title:
            QMessageBox.warning(self, "No Title", "Please enter a title before fetching from MAL.")
            return
        self.btn_mal.setText("Fetching...")
        self.btn_mal.setEnabled(False)
        self._mal_worker = MalSyncWorker(title)
        self._mal_worker.sig_finished.connect(self._on_mal_finished)
        self._mal_worker.error.connect(self._on_mal_error)
        self._mal_worker.start()

    @Slot(dict)
    def _on_mal_finished(self, data: dict):
        synopsis = data.get("synopsis", "")
        if synopsis:
            self.f_summary.setPlainText(synopsis)
        episodes = data.get("episodes")
        if episodes:
            self.f_episodes.setValue(int(episodes))
        score = data.get("score")
        if score:
            self.f_community_rating.setValue(float(score))
        genres = data.get("genres", "")
        if genres:
            self.f_genres.setText(genres)
        year = data.get("year")
        if year:
            self.f_year.setValue(int(year))
        mapped_status = data.get("status", "")
        if mapped_status and mapped_status in ENTRY_STATUS:
            self.f_status.setCurrentText(mapped_status)
        mal_url = data.get("mal_url", "")
        if mal_url and not self.f_web_link.text().strip():
            self.f_web_link.setText(mal_url)

        self._auto_associate_entities(data)

        self.btn_mal.setText("Auto-Fill from MAL")
        self.btn_mal.setEnabled(True)

    @Slot(str)
    def _on_mal_error(self, message: str):
        QMessageBox.critical(self, "MAL Fetch Error", message)
        self.btn_mal.setText("Auto-Fill from MAL")
        self.btn_mal.setEnabled(True)


__all__ = ["_MalSyncMixin"]
