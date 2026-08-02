"""Semantic (BGE-M3) "Search by Meaning" + embedding-index backfill for
``EntityListingsSubTab`` -- DB.7 listings side. Mirrors
``series_listings_subtab/_semantic_search.py`` exactly, against
``EntityRepo``/``entity`` embeddings instead of ``MediaRepo``/``media_item``.
"""

from __future__ import annotations

from typing import List, Tuple

from gui.src.helpers.database.library_session import get_library_db
from gui.src.helpers.database.listings_embedding_worker import ListingsEmbeddingWorker
from gui.src.helpers.database.listings_semantic_search_worker import (
    ListingsSemanticSearchWorker,
)
from PySide6.QtCore import QThreadPool, Slot
from PySide6.QtWidgets import QInputDialog, QMessageBox


def _entity_embedding_text(entity: dict) -> str:
    parts = [entity.get("name") or ""]
    for key in ("type", "role"):
        val = entity.get(key)
        if val:
            parts.append(str(val))
    notes = (entity.get("notes") or "").strip()
    if notes:
        parts.append(notes)
    return ". ".join(p for p in parts if p)


class _SemanticSearchMixin:
    """"Search by Meaning" + "Build Search Index" toolbar actions."""

    @Slot()
    def _on_semantic_search(self) -> None:
        if not self.vault_manager or not self.vault_manager.raw_password:
            QMessageBox.information(
                self,
                "Secure Access Required",
                "You must be logged in to search by meaning.",
            )
            return
        if self._active_semantic_worker is not None:
            return

        query, ok = QInputDialog.getText(
            self,
            "Search by Meaning",
            "Describe who you're looking for, e.g. \"director known for "
            "space westerns\":",
        )
        if not ok or not query.strip():
            return

        db = get_library_db(self.vault_manager, parent=self)
        if db is None:
            QMessageBox.warning(self, "Error", "The library database is unavailable.")
            return

        worker = ListingsSemanticSearchWorker(db, domain="entity", text=query.strip(), top_k=50)
        worker.signals.finished.connect(self._on_semantic_search_finished)
        worker.signals.error.connect(self._on_semantic_search_error)
        self._active_semantic_worker = worker
        self.stats_label.setText("🧠 Searching by meaning…")
        QThreadPool.globalInstance().start(worker)

    def _on_semantic_search_finished(self, hits: List[Tuple[str, float, str]]) -> None:
        self._active_semantic_worker = None
        if not hits:
            self.stats_label.setText(
                "🧠 No semantic matches (index may be empty -- try 'Build Search Index')."
            )
            return
        self._semantic_search_results = [(h[0], h[1]) for h in hits]
        self.clear_semantic_btn.show()
        self.stats_label.setText(f"🧠 {len(hits)} semantic match(es).")
        self._rebuild_gallery()

    def _on_semantic_search_error(self, message: str) -> None:
        self._active_semantic_worker = None
        QMessageBox.warning(self, "Semantic Search Error", message)
        self.stats_label.setText("🧠 Semantic search failed.")

    def _clear_semantic_search(self) -> None:
        self._semantic_search_results = None
        self.clear_semantic_btn.hide()
        self._rebuild_gallery()

    @Slot()
    def _on_build_search_index(self) -> None:
        """Backfill BGE-M3 embeddings for every entity that doesn't have
        one yet. No dedicated listings "Management" tab exists, so this
        lives right next to the search entry point that needs it."""
        if not self.vault_manager or not self.vault_manager.raw_password:
            QMessageBox.information(
                self, "Secure Access Required", "You must be logged in to do this."
            )
            return
        if self._active_embed_worker is not None:
            QMessageBox.information(
                self, "Already Running", "An index build is already in progress."
            )
            return

        repo = self._entity_repo()
        if repo is None:
            QMessageBox.warning(self, "Error", "The library database is unavailable.")
            return

        pending_ids = repo.list_unembedded(ListingsEmbeddingWorker.MODEL, limit=100000)
        if not pending_ids:
            QMessageBox.information(
                self, "Up to Date", "Every entity already has a search embedding."
            )
            return

        by_id = {e["id"]: e for e in self._entities}
        items = [
            (entity_id, _entity_embedding_text(by_id[entity_id]))
            for entity_id, _name in pending_ids
            if entity_id in by_id
        ]

        confirm = QMessageBox.question(
            self,
            "Build Search Index",
            f"{len(items)} entit(y/ies) need indexing for semantic search. "
            "This runs a local BGE-M3 model and may take a while for a "
            "large library. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.No:
            return

        worker = ListingsEmbeddingWorker(items)
        worker.progress.connect(
            lambda cur, tot: self.stats_label.setText(f"🧠 Indexing… {cur}/{tot}")
        )
        worker.sig_finished.connect(self._on_build_search_index_finished)
        worker.error.connect(self._on_build_search_index_error)
        self._active_embed_worker = worker
        worker.start()

    def _on_build_search_index_finished(self, results: list) -> None:
        self._active_embed_worker = None
        repo = self._entity_repo()
        if repo is None:
            return
        try:
            for entity_id, model, vector in results:
                repo.upsert_embedding(entity_id, model, vector)
            QMessageBox.information(
                self, "Success", f"Indexed {len(results)} entit(y/ies)."
            )
            self.stats_label.setText(f"🧠 Indexed {len(results)} entit(y/ies).")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to store embeddings: {e}")

    def _on_build_search_index_error(self, message: str) -> None:
        self._active_embed_worker = None
        QMessageBox.warning(self, "Index Build Failed", message)
        self.stats_label.setText("🧠 Index build failed.")


__all__ = ["_SemanticSearchMixin"]
