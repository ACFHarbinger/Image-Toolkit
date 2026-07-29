"""Encrypted-backup sync/update workflows via ``_SyncBackupWorker``.

Extracted from ``entity_listings_subtab.py`` -- pure code motion, no logic
change.
"""

from __future__ import annotations

import os
from pathlib import Path

import backend.src.constants as udef
from gui.src.helpers.core.library_session import get_library_db
from gui.src.helpers.web.sync_backup_worker import _SyncBackupWorker
from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import QMessageBox, QProgressDialog


class _BackupSyncMixin:
    """Synchronizes/updates the encrypted entities backup file."""

    @Slot()
    def _synchronize_listings(self):
        if not self.vault_manager or not self.vault_manager.secret_key:
            QMessageBox.warning(
                self,
                "Authentication Required",
                "Vault manager is not initialized or active. Please log in to sync.",
            )
            return

        secrets_dir = Path(udef.ROOT_DIR) / "assets" / "secrets"
        secrets_dir.mkdir(parents=True, exist_ok=True)
        enc_file_path = str(secrets_dir / "entities.json.enc")

        if not os.path.exists(enc_file_path):
            QMessageBox.warning(
                self,
                "Backup Not Found",
                "No encrypted entities backup file found to synchronize from. Use 'Update Backup' first to generate it.",
            )
            return

        db = get_library_db(self.vault_manager, parent=self)
        if db is None:
            QMessageBox.warning(
                self,
                "Library Unavailable",
                "The unified library database could not be opened; cannot sync.",
            )
            return

        # Create progress dialog
        self.progress_dialog = QProgressDialog(
            "Starting synchronization...", "", 0, 100, self
        )
        self.progress_dialog.setWindowTitle("Synchronizing Backup")
        self.progress_dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.setValue(0)
        self.progress_dialog.setAutoClose(False)
        self.progress_dialog.setAutoReset(False)
        self.progress_dialog.setWindowFlags(
            self.progress_dialog.windowFlags() & ~Qt.WindowType.WindowCloseButtonHint
        )
        self.progress_dialog.show()

        # Start background thread
        self._sync_worker = _SyncBackupWorker(
            "sync",
            "Entity",
            {
                "vault_manager": self.vault_manager,
                "enc_file_path": enc_file_path,
                "local_entries": self._entities,
                "db": db,
            },
        )
        self._sync_worker.progress.connect(self._on_sync_progress)
        self._sync_worker.sig_finished.connect(self._on_sync_finished)
        self._sync_worker.start()

    def _on_sync_progress(self, percent, text):
        dlg = getattr(self, "progress_dialog", None)
        if dlg is not None:
            dlg.setLabelText(text)
            dlg.setValue(percent)

    def _on_sync_finished(self, success, message, result_data):
        if getattr(self, "progress_dialog", None):
            self.progress_dialog.close()
            self.progress_dialog = None # pyrefly: ignore [bad-assignment]

        if success:
            merged_entries, synced_imgs = result_data
            self._entities = merged_entries
            self._rebuild_gallery()

            img_info = (
                f"\nAlso restored {synced_imgs} missing image(s) from backup."
                if synced_imgs
                else ""
            )
            QMessageBox.information(
                self,
                "Synchronization Complete",
                f"Successfully synchronized entities!\nMerged local and backup entries to a total of {len(merged_entries)} entries.{img_info}",
            )
        else:
            QMessageBox.critical(
                self,
                "Sync Error",
                f"An error occurred during synchronization:\n{message}",
            )

    @Slot()
    def _update_encrypted_backup(self):
        if not self.vault_manager or not self.vault_manager.secret_key:
            QMessageBox.warning(
                self,
                "Authentication Required",
                "Vault manager is not initialized or active. Please log in to update backup.",
            )
            return

        secrets_dir = Path(udef.ROOT_DIR) / "assets" / "secrets"
        secrets_dir.mkdir(parents=True, exist_ok=True)
        enc_file_path = str(secrets_dir / "entities.json.enc")

        # Create progress dialog
        self.progress_dialog = QProgressDialog("Starting backup...", "", 0, 100, self)
        self.progress_dialog.setWindowTitle("Updating Backup")
        self.progress_dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.setValue(0)
        self.progress_dialog.setAutoClose(False)
        self.progress_dialog.setAutoReset(False)
        self.progress_dialog.setWindowFlags(
            self.progress_dialog.windowFlags() & ~Qt.WindowType.WindowCloseButtonHint
        )
        self.progress_dialog.show()

        # Start background thread
        self._backup_worker = _SyncBackupWorker(
            "backup",
            "Entity",
            {
                "vault_manager": self.vault_manager,
                "enc_file_path": enc_file_path,
                "entries": self._entities,
            },
        )
        self._backup_worker.progress.connect(self._on_backup_progress)
        self._backup_worker.sig_finished.connect(self._on_backup_finished)
        self._backup_worker.start()

    def _on_backup_progress(self, percent, text):
        dlg = getattr(self, "progress_dialog", None)
        if dlg is not None:
            dlg.setLabelText(text)
            dlg.setValue(percent)

    def _on_backup_finished(self, success, message, result_data):
        if getattr(self, "progress_dialog", None):
            self.progress_dialog.close()
            self.progress_dialog = None # pyrefly: ignore [bad-assignment]

        if success:
            backup_count = result_data
            img_info = (
                f"\nAlso backed up {backup_count} image(s) to multi-part archive."
                if backup_count
                else ""
            )
            QMessageBox.information(
                self,
                "Backup Updated",
                f"Successfully generated encrypted backup entities file with {len(self._entities)} entries.{img_info}",
            )
        else:
            QMessageBox.critical(
                self,
                "Backup Error",
                f"An error occurred while generating backup:\n{message}",
            )


__all__ = ["_BackupSyncMixin"]
