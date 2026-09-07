"""Connection lifecycle + statistics controller for ``DatabaseTab`` (§5.17, #544)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from backend.src.database.unified.facade import UnifiedImageDatabase as ImageDatabase
from PySide6.QtWidgets import QInputDialog, QMessageBox

from gui.src.constants.elements import EMBED_MODEL
from gui.src.helpers.database.embedding_worker import ImageEmbeddingWorker
from gui.src.helpers.database.library_session import get_library_db

if TYPE_CHECKING:
    pass


class DatabaseConnectionController:
    """Open/reset the library store, refresh statistics, toggle button state."""

    def __init__(self, tab: Any) -> None:
        self.tab = tab

    def connect_database(self, silent: bool = False) -> None:
        """Open the unified library store (Argon2id runs once per session)."""
        tab = self.tab
        try:
            session_db = get_library_db(tab.vault_manager, parent=tab)
            if session_db is None:
                if not silent:
                    QMessageBox.warning(
                        tab,
                        "Vault Locked",
                        "The unified library requires an unlocked vault. "
                        "Log in first, then press 'Open Library'.",
                    )
                tab.update_button_states(connected=False)
                return

            tab.db = ImageDatabase(session_db)
            tab.database_service.db = tab.db
            tab.update_statistics()
            tab.update_button_states(connected=True)
            tab._refresh_all_group_combos()
            tab.refresh_subgroup_autocomplete()
            tab.refresh_tags_list()
            tab.refresh_groups_list()
            tab.refresh_subgroups_list()
            tab.refresh_image_registry()

            tab._publish_tag_catalog_changed()

            if not silent:
                QMessageBox.information(
                    tab, "Success", "Unified library opened."
                )
        except Exception as e:
            QMessageBox.critical(
                tab, "Error", f"Failed to open the library database:\n{str(e)}"
            )
            tab.update_button_states(connected=False)
            tab._publish_database_availability(False)
            tab.stats_label.setText("Library Unavailable")

    def reset_database(self) -> None:
        tab = self.tab
        if not tab.db:
            QMessageBox.warning(tab, "Error", "Please connect to a database first")
            return

        confirm1 = QMessageBox.question(
            tab,
            "Confirm Destructive Action",
            "Are you absolutely sure you want to reset the database?\n\n"
            "ALL DATA (images, tags, groups, subgroups) will be PERMANENTLY DELETED.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if confirm1 == QMessageBox.StandardButton.No:
            QMessageBox.information(tab, "Cancelled", "Database reset was cancelled.")
            return

        text, ok = QInputDialog.getText(
            tab,
            "Final Confirmation",
            "This is your final warning. This action cannot be undone.\n"
            "This will DROP all tables and recreate the schema.\n\n"
            "Type 'RESET' in the box below to proceed:",
        )

        if not ok:
            QMessageBox.information(tab, "Cancelled", "Database reset was cancelled.")
            return

        if text.strip() != "RESET":
            QMessageBox.warning(
                tab,
                "Cancelled",
                "Input did not match 'RESET'. Database reset was cancelled.",
            )
            return

        try:
            tab.db.reset_database()
            QMessageBox.information(
                tab, "Success", "Database has been reset successfully."
            )

            tab.update_statistics()
            tab._refresh_all_group_combos()
            tab.refresh_subgroup_autocomplete()
            tab.refresh_tags_list()
            tab.refresh_groups_list()
            tab.refresh_subgroups_list()
            tab.refresh_image_registry()

            tab._publish_tag_catalog_changed()

        except Exception as e:
            QMessageBox.critical(tab, "Error", f"Failed to reset database:\n{str(e)}")

    def update_statistics(self) -> None:
        tab = self.tab
        if not tab.db:
            return
        try:
            stats = tab.db.get_statistics()

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
            tab.stats_label.setText(stats_text)
            tab._stats_text = stats_text
            tab.qml_stats_changed.emit()
        except Exception as e:
            tab.stats_label.setText(f"Error getting statistics: {str(e)}")

    def run_vacuum(self) -> None:
        tab = self.tab
        if not tab.db:
            return
        try:
            tab.db.maintenance_vacuum(full=False)
            QMessageBox.information(tab, "Success", "Database vacuum completed.")
        except Exception as e:
            QMessageBox.critical(tab, "Error", f"Vacuum failed: {e}")

    def run_reindex(self) -> None:
        tab = self.tab
        if not tab.db:
            return
        try:
            tab.db.maintenance_reindex()
            QMessageBox.information(tab, "Success", "Database reindex completed.")
        except Exception as e:
            QMessageBox.critical(tab, "Error", f"Reindex failed: {e}")

    def run_embed_backfill(self) -> None:
        """DB.7: compute+store semantic embeddings for images that don't
        have one yet. Runs in the background (ImageEmbeddingWorker,
        QThread); the DB write happens back on this (main) thread, in one
        transaction, once the whole batch's vectors are ready -- the
        keyed Database handle is not safe to share across threads."""
        tab = self.tab
        if not tab.db:
            return
        if getattr(tab, "embedding_worker", None) is not None:
            QMessageBox.information(
                tab, "Already Running", "An embedding backfill is already in progress."
            )
            return

        try:
            pending = tab.db.count_unembedded_images(EMBED_MODEL)
        except Exception as e:
            QMessageBox.critical(tab, "Error", f"Failed to check embedding status: {e}")
            return

        if pending == 0:
            QMessageBox.information(
                tab, "Up to Date", "Every image already has a semantic embedding."
            )
            return

        confirm = QMessageBox.question(
            tab,
            "Embed Images",
            f"{pending} image(s) have no semantic embedding yet. Compute them now?\n\n"
            "This runs a local CLIP model over each image and may take a "
            "while for a large library.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.No:
            return

        items = tab.db.list_unembedded_images(EMBED_MODEL, limit=pending)
        tab.btn_embed_backfill.setEnabled(False)
        tab.btn_embed_backfill.setText("🧠 Embedding… 0/%d" % len(items))

        worker = ImageEmbeddingWorker(items, model=EMBED_MODEL)
        worker.progress.connect(self._on_embed_progress)
        worker.sig_finished.connect(self._on_embed_finished)
        worker.error.connect(self._on_embed_error)
        worker.finished.connect(worker.deleteLater)
        worker.finished.connect(lambda: setattr(tab, "embedding_worker", None))
        tab.embedding_worker = worker
        worker.start()

    run_embedding_backfill = run_embed_backfill

    def _on_embed_progress(self, current: int, total: int) -> None:
        self.tab.btn_embed_backfill.setText(f"🧠 Embedding… {current}/{total}")

    def _on_embed_finished(self, results: list) -> None:
        tab = self.tab
        tab.btn_embed_backfill.setEnabled(True)
        tab.btn_embed_backfill.setText("🧠 Embed Unembedded Images")
        if not tab.db:
            return
        try:
            with tab.db.transaction():
                for image_id, model, vector in results:
                    tab.db.upsert_image_embedding(image_id, model, vector)
            QMessageBox.information(
                tab, "Success", f"Embedded {len(results)} image(s)."
            )
        except Exception as e:
            QMessageBox.critical(tab, "Error", f"Failed to store embeddings: {e}")

    def _on_embed_error(self, message: str) -> None:
        self.tab.btn_embed_backfill.setEnabled(True)
        self.tab.btn_embed_backfill.setText("🧠 Embed Unembedded Images")
        QMessageBox.warning(self.tab, "Embedding Failed", message)

    def _refresh_all_group_combos(self) -> None:
        tab = self.tab
        if not tab.db:
            return
        try:
            group_list = tab.db.get_all_groups()

            tab.new_subgroup_parent_combo.clear()
            tab.new_subgroup_parent_combo.addItems([""] + group_list)

            tab.existing_subgroups_filter_combo.clear()
            tab.existing_subgroups_filter_combo.addItems([""] + group_list)

            tab._publish_group_catalog_changed(group_list)

        except Exception as e:
            print(f"Error refreshing group combos: {e}")
            QMessageBox.critical(
                tab, "Error", f"Failed to refresh group dropdowns:\n{str(e)}"
            )

    def refresh_subgroup_autocomplete(self) -> None:
        tab = self.tab
        if not tab.db:
            return
        try:
            detailed = tab.db.get_all_subgroups_detailed()
            tab._publish_subgroup_catalog_changed(detailed)
        except Exception as e:
            print(f"Error refreshing subgroup list data: {e}")

    def update_button_states(self, connected: bool) -> None:
        tab = self.tab
        tab.btn_connect.setVisible(not connected)
        tab.btn_reset_db.setVisible(connected)
        tab.btn_vacuum.setVisible(connected)
        tab.btn_reindex.setVisible(connected)
        tab.btn_embed_backfill.setVisible(connected)

        tab.populate_group.setEnabled(connected)
        tab.btn_auto_populate.setEnabled(connected)
        tab.btn_import_tags.setEnabled(connected)

        tab.btn_remove_group.setEnabled(connected)
        tab.btn_remove_subgroup.setEnabled(connected)
        tab.btn_remove_tag.setEnabled(connected)

        tab._publish_database_availability(connected)

    def check_postgres_status(self) -> None:
        """Interactive reachability and pgvector diagnostic test."""
        from gui.src.helpers.database.postgres_check import show_postgres_status_dialog

        show_postgres_status_dialog(
            parent=self.tab, silent_if_ok=False, vault_manager=self.tab.vault_manager
        )

    def _postgres_config_from_fields(self) -> dict[str, str]:
        tab = self.tab
        return {
            "DB_HOST": tab.postgres_host_edit.text().strip(),
            "DB_PORT": str(tab.postgres_port_spin.value()),
            "DB_NAME": tab.postgres_db_edit.text().strip(),
            "DB_USER": tab.postgres_user_edit.text().strip(),
        }

    def save_postgres_settings(self) -> None:
        """Persist non-secret fields in QSettings and the password in the vault."""
        tab = self.tab
        from gui.src.helpers.database.postgres_check import save_postgres_config

        if not tab.vault_manager or getattr(tab.vault_manager, "is_guest", False):
            QMessageBox.warning(
                tab,
                "PostgreSQL Settings",
                "Sign in to an account before saving a PostgreSQL password.",
            )
            return
        config = self._postgres_config_from_fields()
        if not all(config[field] for field in ("DB_HOST", "DB_NAME", "DB_USER")):
            QMessageBox.warning(
                tab, "PostgreSQL Settings", "Host, database, and user are required."
            )
            return
        try:
            password = tab.postgres_password_edit.text() or None
            save_postgres_config(tab.vault_manager, config, password)
            tab.postgres_password_edit.clear()
            QMessageBox.information(
                tab,
                "PostgreSQL Settings",
                "Connection settings saved. The password is encrypted in your vault.",
            )
        except (OSError, RuntimeError, ValueError) as exc:
            QMessageBox.critical(tab, "PostgreSQL Settings", str(exc))

    def clear_postgres_password(self) -> None:
        """Remove the saved database password without exposing its value."""
        tab = self.tab
        from gui.src.helpers.database.postgres_check import save_postgres_config

        if not tab.vault_manager or getattr(tab.vault_manager, "is_guest", False):
            return
        try:
            save_postgres_config(
                tab.vault_manager, self._postgres_config_from_fields(), password=""
            )
            tab.postgres_password_edit.clear()
            QMessageBox.information(
                tab, "PostgreSQL Settings", "Saved PostgreSQL password cleared."
            )
        except (OSError, RuntimeError, ValueError) as exc:
            QMessageBox.critical(tab, "PostgreSQL Settings", str(exc))


# Backward-compatible alias
_ConnectionStatsMixin = DatabaseConnectionController

__all__ = ["DatabaseConnectionController", "_ConnectionStatsMixin"]
