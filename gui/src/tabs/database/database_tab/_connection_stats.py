"""Connection lifecycle + statistics methods for ``DatabaseTab``.

Extracted from ``database_tab.py`` -- pure code motion, no logic change
(see ``_ui_connection.py``'s docstring).
"""

from __future__ import annotations

from backend.src.database.unified.facade import UnifiedImageDatabase as ImageDatabase
from gui.src.helpers.core.library_session import get_library_db
from PySide6.QtWidgets import QInputDialog, QMessageBox


class _ConnectionStatsMixin:
    """Open/reset the library store, refresh statistics, toggle button state."""

    def connect_database(self, silent: bool = False):
        """Open the unified library store (Argon2id runs once per session)."""
        try:
            session_db = get_library_db(self.vault_manager, parent=self)
            if session_db is None:
                if not silent:
                    QMessageBox.warning(
                        self,
                        "Vault Locked",
                        "The unified library requires an unlocked vault. "
                        "Log in first, then press 'Open Library'.",
                    )
                self.update_button_states(connected=False)
                return

            self.db = ImageDatabase(session_db)
            self.update_statistics()
            self.update_button_states(connected=True)
            self._refresh_all_group_combos()
            self.refresh_subgroup_autocomplete()
            self.refresh_tags_list()
            self.refresh_groups_list()
            self.refresh_subgroups_list()
            self.refresh_image_registry()

            if self.scan_tab_ref:
                self.scan_tab_ref._setup_tag_checkboxes()

            if not silent:
                QMessageBox.information(
                    self, "Success", "Unified library opened."
                )
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to open the library database:\n{str(e)}"
            )
            self.update_button_states(connected=False)
            self.stats_label.setText("Library Unavailable")
            self.stats_label.setStyleSheet(
                "padding: 10px; background-color: #e74c3c; color: white; border-radius: 5px; font-weight: bold;"
            )

    def reset_database(self):
        if not self.db:
            QMessageBox.warning(self, "Error", "Please connect to a database first")
            return

        confirm1 = QMessageBox.question(
            self,
            "Confirm Destructive Action",
            "Are you absolutely sure you want to reset the database?\n\n"
            "ALL DATA (images, tags, groups, subgroups) will be PERMANENTLY DELETED.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if confirm1 == QMessageBox.StandardButton.No:
            QMessageBox.information(self, "Cancelled", "Database reset was cancelled.")
            return

        text, ok = QInputDialog.getText(
            self,
            "Final Confirmation",
            "This is your final warning. This action cannot be undone.\n"
            "This will DROP all tables and recreate the schema.\n\n"
            "Type 'RESET' in the box below to proceed:",
        )

        if not ok:
            QMessageBox.information(self, "Cancelled", "Database reset was cancelled.")
            return

        if text.strip() != "RESET":
            QMessageBox.warning(
                self,
                "Cancelled",
                "Input did not match 'RESET'. Database reset was cancelled.",
            )
            return

        try:
            self.db.reset_database()
            QMessageBox.information(
                self, "Success", "Database has been reset successfully."
            )

            self.update_statistics()
            self._refresh_all_group_combos()
            self.refresh_subgroup_autocomplete()
            self.refresh_tags_list()
            self.refresh_groups_list()
            self.refresh_subgroups_list()
            self.refresh_image_registry()

            if self.scan_tab_ref:
                self.scan_tab_ref._setup_tag_checkboxes()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to reset database:\n{str(e)}")

    def update_statistics(self):
        if not self.db:
            return
        try:
            stats = self.db.get_statistics()

            # Format file size
            total_bytes = stats.get("total_file_size", 0)
            if total_bytes < 1024:
                size_str = f"{total_bytes} B"
            elif total_bytes < 1024**2:
                size_str = f"{total_bytes / 1024:.2f} KB"
            elif total_bytes < 1024**3:
                size_str = f"{total_bytes / 1024**2:.2f} MB"
            else:
                size_str = f"{total_bytes / 1024**3:.2f} GB"

            last_sync = stats.get("last_sync_date")
            if last_sync is None:
                last_sync_str = "Never"
            elif isinstance(last_sync, str):
                last_sync_str = last_sync  # unified store keeps ISO text dates
            else:
                last_sync_str = last_sync.strftime("%Y-%m-%d %H:%M:%S")

            stats_text = (
                f"📊 Database Statistics:\n"
                f"Images: {stats.get('total_images', 0)} ({size_str}) | "
                f"Tags: {stats.get('total_tags', 0)} | "
                f"Groups: {stats.get('total_groups', 0)} | "
                f"Subgroups: {stats.get('total_subgroups', 0)}\n"
                f"Last Sync: {last_sync_str}"
            )
            self.stats_label.setText(stats_text)
            self.stats_label.setStyleSheet(
                "padding: 10px; background-color: #27ae60; color: white; border-radius: 5px; font-weight: bold;"
            )
        except Exception as e:
            self.stats_label.setText(f"Error getting statistics: {str(e)}")
            self.stats_label.setStyleSheet(
                "padding: 10px; background-color: #e74c3c; color: white; border-radius: 5px; font-weight: bold;"
            )

    def run_vacuum(self):
        if not self.db:
            return
        try:
            self.db.maintenance_vacuum(full=False)
            QMessageBox.information(self, "Success", "Database vacuum completed.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Vacuum failed: {e}")

    def run_reindex(self):
        if not self.db:
            return
        try:
            self.db.maintenance_reindex()
            QMessageBox.information(self, "Success", "Database reindex completed.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Reindex failed: {e}")

    def _refresh_all_group_combos(self):
        if not self.db:
            return
        try:
            group_list = self.db.get_all_groups()

            self.new_subgroup_parent_combo.clear()
            self.new_subgroup_parent_combo.addItems([""] + group_list)

            self.existing_subgroups_filter_combo.clear()
            self.existing_subgroups_filter_combo.addItems([""] + group_list)

            if self.search_tab_ref and hasattr(self.search_tab_ref, "groups_list_widget"):
                self.search_tab_ref.populate_groups_list(group_list)

        except Exception as e:
            print(f"Error refreshing group combos: {e}")
            QMessageBox.critical(
                self, "Error", f"Failed to refresh group dropdowns:\n{str(e)}"
            )

    def refresh_subgroup_autocomplete(self):
        if not self.db:
            return
        if not self.search_tab_ref or not hasattr(
            self.search_tab_ref, "subgroups_list_widget"
        ):
            return
        try:
            detailed = self.db.get_all_subgroups_detailed()
            self.search_tab_ref.populate_subgroups_detailed(detailed)
        except Exception as e:
            print(f"Error refreshing subgroup list data: {e}")

    def update_button_states(self, connected: bool):
        self.btn_connect.setVisible(not connected)
        self.btn_reset_db.setVisible(connected)
        self.btn_vacuum.setVisible(connected)
        self.btn_reindex.setVisible(connected)

        self.populate_group.setEnabled(connected)
        self.btn_auto_populate.setEnabled(connected)
        self.btn_import_tags.setEnabled(connected)

        self.btn_remove_group.setEnabled(connected)
        self.btn_remove_subgroup.setEnabled(connected)
        self.btn_remove_tag.setEnabled(connected)

        if self.scan_tab_ref:
            self.scan_tab_ref.update_button_states(connected)

        if self.search_tab_ref:
            self.search_tab_ref.update_search_button_state(connected)


__all__ = ["_ConnectionStatsMixin"]
