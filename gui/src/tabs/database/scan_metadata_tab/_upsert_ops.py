"""Batch metadata upsert (via ``MetadataEditorWindow``/``UpsertWorker``) + delete.

Extracted from ``scan_metadata_tab.py`` -- pure code motion, no logic
change (see ``_ui_builder.py``'s docstring).
"""

from __future__ import annotations

from PySide6.QtCore import Slot
from PySide6.QtWidgets import QMessageBox

from gui.src.helpers import UpsertWorker

from ....windows import MetadataEditorWindow


class _UpsertOpsMixin:
    """Open the metadata editor, run the background upsert worker, and DB-delete."""

    def perform_upsert_operation(self):
        """Open the MetadataEditorWindow for the currently selected images."""
        db = self.database_service.db
        if not db:
            QMessageBox.warning(self, "Error", "Connect to database first.")
            return
        if not self.selected_image_paths:
            QMessageBox.warning(self, "No Selection", "Select at least one image first.")
            return

        paths = sorted(self.selected_image_paths)
        dialog = MetadataEditorWindow(paths, db, parent=self)
        dialog.metadata_confirmed.connect(self._execute_upsert)
        dialog.show()

    @Slot(list)
    def _execute_upsert(self, results: list):
        """Receive per-image metadata dicts from MetadataEditorWindow and hand
        them to a background UpsertWorker (DB.6 P3b). Only image decode
        (width/height) runs off the GUI thread; the actual DB writes are
        applied on the main thread in one batched transaction once the
        worker finishes, in ``_on_upsert_prepared`` below."""
        db = self.database_service.db
        if not db or not results:
            return
        if self.current_upsert_worker is not None:
            return  # an upsert is already running

        self.upsert_button.setEnabled(False)
        self._upsert_button_label = self.upsert_button.text()

        worker = UpsertWorker(results)
        self.current_upsert_worker = worker
        worker.progress.connect(self._on_upsert_progress)
        worker.sig_finished.connect(self._on_upsert_prepared)
        worker.error.connect(self._on_upsert_error)
        worker.finished.connect(self._cleanup_upsert_worker)
        worker.start()

    def _cleanup_upsert_worker(self):
        worker = self.current_upsert_worker
        self.current_upsert_worker = None
        if worker is not None:
            worker.deleteLater()
        self.upsert_button.setEnabled(True)
        if hasattr(self, "_upsert_button_label"):
            self.upsert_button.setText(self._upsert_button_label)

    @Slot(int, int)
    def _on_upsert_progress(self, current: int, total: int):
        self.upsert_button.setText(f"Upserting {current}/{total}...")

    @Slot(str)
    def _on_upsert_error(self, message: str):
        QMessageBox.critical(self, "Error", message)

    @Slot(list)
    def _on_upsert_prepared(self, prepared: list):  # noqa: C901
        """Apply all prepared entries in one transaction (main thread —
        DB writes are not done on the worker thread)."""
        db = self.database_service.db
        if not db:
            return
        success_count = 0
        touched_group_names: set = set()
        try:
            with db.transaction():
                for entry in prepared:
                    path = entry["path"]
                    group_name = entry.get("group_name")
                    subgroup_name = entry.get("subgroup_name")
                    tags = entry.get("tags")
                    width = entry.get("width")
                    height = entry.get("height")
                    if group_name and group_name.strip():
                        touched_group_names.add(group_name)

                    existing = db.get_image_by_path(path)
                    if existing:
                        db.update_image(
                            existing["id"],
                            group_name=group_name,
                            subgroup_name=subgroup_name,
                            tags=tags,
                        )
                    else:
                        db.add_image(
                            path,
                            embedding=None,
                            group_name=group_name,
                            subgroup_name=subgroup_name,
                            tags=tags,
                            width=width,
                            height=height,
                        )
                    success_count += 1

                    if self.view_new_only:
                        if path in self.scan_image_list:
                            self.scan_image_list.remove(path)
                        if path in self.scan_filtered_list:
                            self.scan_filtered_list.remove(path)
                    else:
                        self.dual.found_gallery.model.mark_in_db(path, True)

            if self.view_new_only:
                self._refresh_scan_gallery()

            QMessageBox.information(
                self, "Success", f"Upserted {success_count} images."
            )
            self.update_button_states(True)

            # DB.8d (scoped): offer to auto-create/link a listing for any
            # newly-touched image group with no linked listing yet.
            self._maybe_offer_auto_listings(sorted(touched_group_names))

        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def delete_selected_images(self):
        db = self.database_service.db
        if not db:
            return
        if (
            QMessageBox.question(
                self,
                "Confirm",
                f"Delete {len(self.selected_image_paths)} entries from DB?",
            )
            == QMessageBox.StandardButton.Yes
        ):
            for path in self.selected_image_paths:
                img = db.get_image_by_path(path)
                if img:
                    db.delete_image(img["id"])

                self.dual.found_gallery.model.mark_in_db(path, False)

            QMessageBox.information(self, "Success", "Deleted entries.")


__all__ = ["_UpsertOpsMixin"]
