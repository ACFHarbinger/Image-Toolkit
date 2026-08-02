"""Semantic (CLIP) text->image search -- DB.7.

An additive "Search by Meaning" box alongside the existing structured
Search Database form/button, rather than folding semantic mode into
perform_search()/toggle_search() -- keeps the existing, well-tested
structured-search flow (also driven by the QML bridge's
execute_search()) untouched. Composes with the existing group/subgroup/
tag/format filters as a SQL prefilter (SearchRepo.semantic_image_search,
DB.3/DB.7).
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QThreadPool
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from ...helpers import SemanticSearchWorker
from ...styles import apply_shadow_effect


class _SemanticSearchMixin:
    """"Search by Meaning" natural-language box."""

    def _build_semantic_search_section(self, layout: QVBoxLayout) -> None:
        group = QGroupBox("🧠 Semantic Search (find images by meaning, not filename)")
        group_layout = QHBoxLayout(group)

        self.semantic_query_edit = QLineEdit()
        self.semantic_query_edit.setPlaceholderText(
            "Describe what you're looking for, e.g. \"a sunset over water\"…"
        )
        self.semantic_query_edit.returnPressed.connect(self.perform_semantic_search)
        group_layout.addWidget(self.semantic_query_edit)

        self.semantic_search_button = QPushButton("Search by Meaning")
        apply_shadow_effect(
            self.semantic_search_button, color_hex="#000000", radius=8, x_offset=0, y_offset=3
        )
        self.semantic_search_button.clicked.connect(self.perform_semantic_search)
        group_layout.addWidget(self.semantic_search_button)

        layout.addWidget(group)
        self.current_semantic_worker: Optional[SemanticSearchWorker] = None

    def perform_semantic_search(self):
        db = self.db_tab_ref.db
        if not db:
            QMessageBox.warning(self, "Error", "Please connect to the database first.")
            return
        query = self.semantic_query_edit.text().strip()
        if not query:
            QMessageBox.information(
                self, "Semantic Search", "Enter a description to search by meaning."
            )
            return
        if self.current_semantic_worker is not None:
            return

        selected_groups = self.get_selected_groups()
        selected_subgroups = self.get_selected_subgroups()

        self.clear_search_data()
        self.semantic_search_button.setEnabled(False)
        self.semantic_search_button.setText("Searching…")
        self.progress_bar.show()

        worker = SemanticSearchWorker(
            db,
            text=query,
            top_k=200,
            # semantic_image_search takes one group/subgroup name, not a
            # list -- only apply the prefilter when the user narrowed to
            # exactly one (a multi-select OR would need an API change).
            group_name=selected_groups[0] if len(selected_groups) == 1 else None,
            subgroup_name=selected_subgroups[0] if len(selected_subgroups) == 1 else None,
            tags=self.get_selected_tags() or None,
            input_formats=self.get_selected_formats(),
        )
        worker.signals.finished.connect(self._on_semantic_search_finished)
        worker.signals.error.connect(self._on_semantic_search_error)
        worker.signals.cancelled.connect(self._on_semantic_search_cancelled)
        self.current_semantic_worker = worker
        QThreadPool.globalInstance().start(worker)

    def _reset_semantic_ui(self, message: str) -> None:
        self.current_semantic_worker = None
        self.semantic_search_button.setEnabled(True)
        self.semantic_search_button.setText("Search by Meaning")
        self.progress_bar.hide()
        self.results_count_label.setText(message)

    def _display_ranked_results(self, hits: list) -> None:
        """Show semantic-search hits in their given (relevance) order --
        bypasses start_loading_thumbnails()'s _apply_sort(), which would
        otherwise silently re-sort a relevance-ranked list alphabetically."""
        paths = [h[2] for h in hits]
        self.cancel_loading()
        self.master_found_files = paths
        self._found_pixmap_cache.clear()
        self._perform_found_search()

    def _on_semantic_search_finished(self, hits: list) -> None:
        self._reset_semantic_ui(f"Semantic search: {len(hits)} match(es).")
        self._display_ranked_results(hits)

    def _on_semantic_search_error(self, message: str) -> None:
        self._reset_semantic_ui("Semantic search failed.")
        QMessageBox.critical(self, "Semantic Search Error", message)

    def _on_semantic_search_cancelled(self) -> None:
        self._reset_semantic_ui("Semantic search cancelled.")

    def find_similar_images(self, file_path: str) -> None:
        """"Find similar" context-menu action -- query by *file_path*'s own
        embedding (computed on the fly; not persisted, unlike the
        Management backfill's stored embeddings)."""
        db = self.db_tab_ref.db
        if not db:
            QMessageBox.warning(self, "Error", "Please connect to the database first.")
            return
        if self.current_semantic_worker is not None:
            QMessageBox.information(
                self, "Busy", "A semantic search is already in progress."
            )
            return

        image_row = db.get_image_by_path(file_path)
        exclude_id = image_row["id"] if image_row else None

        self.clear_search_data()
        self.results_count_label.setText("Finding similar images…")
        self.progress_bar.show()

        worker = SemanticSearchWorker(
            db, image_path=file_path, top_k=100, exclude_image_id=exclude_id,
        )
        worker.signals.finished.connect(self._on_semantic_search_finished)
        worker.signals.error.connect(self._on_semantic_search_error)
        worker.signals.cancelled.connect(self._on_semantic_search_cancelled)
        self.current_semantic_worker = worker
        QThreadPool.globalInstance().start(worker)


__all__ = ["_SemanticSearchMixin"]
