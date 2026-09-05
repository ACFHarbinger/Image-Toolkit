"""Search-worker dispatch (start/cancel/finished/error) for ``SearchTab``.

Extracted from ``search_tab.py`` -- pure code motion, no logic change
(see ``_ui_builder.py``'s docstring).
"""

from __future__ import annotations

from PySide6.QtCore import QThreadPool, Slot
from PySide6.QtWidgets import QMessageBox

from gui.src.helpers import SearchWorker


class _SearchWorkerMixin:
    """Start/cancel the background SearchWorker and react to its outcomes."""

    @Slot()
    def toggle_search(self):
        if self.current_search_worker:
            self.cancel_search()
        else:
            self.perform_search()

    def perform_search(self):
        db = self.database_service.db
        if not db:
            QMessageBox.warning(self, "Error", "Please connect to the database first.")
            return

        query_params = {
            "group_names": self.get_selected_groups() or None,
            "subgroup_names": self.get_selected_subgroups() or None,
            "filename_pattern": self.filename_edit.text().strip() or None,
            "tags": self.get_selected_tags(),
            "input_formats": self.get_selected_formats(),
            "limit": 10000,  # Increased limit since we have pagination now
        }

        self.clear_search_data()
        self.search_button.setEnabled(False)
        self.search_button.setText("Searching...")
        self.progress_bar.show()

        self.current_search_worker = SearchWorker(db, query_params)
        self.current_search_worker.signals.finished.connect(self.on_search_finished)
        self.current_search_worker.signals.error.connect(self.on_search_error)
        self.current_search_worker.signals.cancelled.connect(self.on_search_cancelled)

        # Use global threadpool for search worker
        QThreadPool.globalInstance().start(self.current_search_worker)

    @Slot(list)
    def on_search_finished(self, matching_files: list):
        self.current_search_worker = None
        self._reset_search_ui(f"Search Complete. Found {len(matching_files)} images.")
        self.display_results(matching_files)

    @Slot(str)
    def on_search_error(self, error_msg: str):
        self.current_search_worker = None
        self._reset_search_ui("Search Failed.")
        QMessageBox.critical(
            self, "Search Error", f"An error occurred during search:\n{error_msg}"
        )
        self.results_count_label.setText(f"Error: {error_msg}")

    @Slot()
    def on_search_cancelled(self):
        self.current_search_worker = None
        self._reset_search_ui("Search Cancelled.")
        self.results_count_label.setText("Search cancelled by user.")

    def cancel_search(self):
        if self.current_search_worker:
            self.current_search_worker.cancel()
            self.search_button.setText("Stopping...")
            self.search_button.setEnabled(False)

    def _reset_search_ui(self, message: str):
        self.search_button.setEnabled(True)
        self.search_button.setText("Search Database")
        self.progress_bar.hide()
        self.results_count_label.setText(message)


__all__ = ["_SearchWorkerMixin"]
