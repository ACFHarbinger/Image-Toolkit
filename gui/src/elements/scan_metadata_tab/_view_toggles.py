""""New Only"/"In DB Only" view toggle buttons + button-state refresh.

Extracted from ``scan_metadata_tab.py`` -- pure code motion, no logic
change (see ``_ui_builder.py``'s docstring).
"""

from __future__ import annotations

from PySide6.QtCore import Slot
from PySide6.QtWidgets import QMessageBox


class _ViewTogglesMixin:
    """Mutually-exclusive New-Only/In-DB-Only filter toggles and button-state refresh."""

    def handle_scan_error(self, message: str):
        QMessageBox.warning(self, "Error Scanning", message)

    @Slot(bool)
    def toggle_new_only_view(self, checked: bool):
        db_connected = self.db_tab_ref.db is not None
        if not db_connected and checked:
            QMessageBox.warning(
                self,
                "Database Required",
                "Please connect to the database to filter by database content.",
            )
            self.view_new_only_button.setChecked(False)
            return

        self.view_new_only = checked
        if checked:
            # Mutually exclusive: turn off "In DB Only"
            self.view_in_db_only_button.setChecked(False)

        if self.view_new_only:
            self.view_new_only_button.setText("👁️ Show Only New (On)")
            self.view_new_only_button.setStyleSheet(
                "background-color: #e67e22; color: white; border: 2px solid #d35400;"
            )
        else:
            self.view_new_only_button.setText("👁️ Show Only New (Not in DB)")
            self.view_new_only_button.setStyleSheet("")

        if hasattr(self, "scanned_dir") and self.scanned_dir:
            self.apply_scan_filters()

    @Slot(bool)
    def toggle_in_db_only_view(self, checked: bool):
        db_connected = self.db_tab_ref.db is not None
        if not db_connected and checked:
            QMessageBox.warning(
                self,
                "Database Required",
                "Please connect to the database to filter by database content.",
            )
            self.view_in_db_only_button.setChecked(False)
            return

        self.view_in_db_only = checked
        if checked:
            # Mutually exclusive: turn off "New Only"
            self.view_new_only_button.setChecked(False)

        if self.view_in_db_only:
            self.view_in_db_only_button.setText("💾 Show Only In DB (On)")
            self.view_in_db_only_button.setStyleSheet(
                "background-color: #3498db; color: white; border: 2px solid #2980b9;"
            )
        else:
            self.view_in_db_only_button.setText("💾 Show Only In DB")
            self.view_in_db_only_button.setStyleSheet("")

        if hasattr(self, "scanned_dir") and self.scanned_dir:
            self.apply_scan_filters()

    def update_button_states(self, connected: bool):
        selection_count = len(self.selected_image_paths)

        if connected and not self._db_was_connected:
            self._setup_tag_checkboxes()
        self._db_was_connected = connected

        self.upsert_button.setText(f"Add/Update {selection_count} Selected Images")
        self.upsert_button.setEnabled(connected and selection_count > 0)
        self.delete_selected_button.setText(f"Delete {selection_count} Images from DB")
        self.delete_selected_button.setEnabled(connected and selection_count > 0)


__all__ = ["_ViewTogglesMixin"]
