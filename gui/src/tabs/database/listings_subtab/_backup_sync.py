"""Encrypted-backup sync/update workflows shared by entity and series listings."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, List

import backend.src.constants as udef
from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import QMessageBox, QProgressDialog

from gui.src.helpers.database.library_session import get_library_db
from gui.src.helpers.web.sync_backup_worker import _SyncBackupWorker

if TYPE_CHECKING:
    from .profile import ListingsProfile


class _BackupSyncMixin:
    """Synchronizes/updates the encrypted listings backup file."""

    _listings_profile: ListingsProfile

    def _local_entries(self) -> List[dict[str, Any]]:
        if self._listings_profile.kind == "entity":
            return self._entities
        return self._entries

    def _set_local_entries(self, entries: List[dict[str, Any]]) -> None:
        if self._listings_profile.kind == "entity":
            self._entities = entries
        else:
            self._entries = entries

    @Slot()
    def _synchronize_listings(self):
        profile = self._listings_profile
        if not self.vault_manager or not self.vault_manager.secret_key:
            QMessageBox.warning(
                self,
                "Authentication Required",
                "Vault manager is not initialized or active. Please log in to sync.",
            )
            return

        secrets_dir = Path(udef.ROOT_DIR) / "assets" / "secrets"
        secrets_dir.mkdir(parents=True, exist_ok=True)
        enc_file_path = str(secrets_dir / profile.enc_filename)

        if not os.path.exists(enc_file_path):
            QMessageBox.warning(
                self,
                "Backup Not Found",
                f"No encrypted {profile.item_noun} backup file found to synchronize from. "
                "Use 'Update Backup' first to generate it.",
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

        self._sync_worker = _SyncBackupWorker(
            "sync",
            profile.sync_worker_label,
            {
                "vault_manager": self.vault_manager,
                "enc_file_path": enc_file_path,
                "local_entries": self._local_entries(),
                "db": db,
            },
        )
        self._sync_worker.progress.connect(self._on_sync_progress)
        self._sync_worker.finished.connect(self._on_sync_finished)
        self._sync_worker.error.connect(
            lambda err: self._on_sync_finished((False, str(err), None))
        )
        self._sync_worker.start()

    def _on_sync_progress(self, percent, text):
        dlg = getattr(self, "progress_dialog", None)
        if dlg is not None:
            dlg.setLabelText(text)
            dlg.setValue(percent)

    def _on_sync_finished(self, result):
        profile = self._listings_profile
        if getattr(self, "progress_dialog", None):
            self.progress_dialog.close()
            self.progress_dialog = None  # pyrefly: ignore [bad-assignment]

        if result is None:
            return  # cancelled (no result channel message by design)
        success, message, result_data = result
        if success:
            merged_entries, synced_imgs = result_data
            self._set_local_entries(merged_entries)
            self._rebuild_gallery()

            img_info = (
                f"\nAlso restored {synced_imgs} missing image(s) from backup."
                if synced_imgs
                else ""
            )
            QMessageBox.information(
                self,
                "Synchronization Complete",
                f"Successfully synchronized {profile.sync_success_noun}!\n"
                f"Merged local and backup entries to a total of {len(merged_entries)} entries."
                f"{img_info}",
            )
        else:
            QMessageBox.critical(
                self,
                "Sync Error",
                f"An error occurred during synchronization:\n{message}",
            )

    @Slot()
    def _update_encrypted_backup(self):
        profile = self._listings_profile
        if not self.vault_manager or not self.vault_manager.secret_key:
            QMessageBox.warning(
                self,
                "Authentication Required",
                "Vault manager is not initialized or active. Please log in to update backup.",
            )
            return

        secrets_dir = Path(udef.ROOT_DIR) / "assets" / "secrets"
        secrets_dir.mkdir(parents=True, exist_ok=True)
        enc_file_path = str(secrets_dir / profile.enc_filename)

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

        self._backup_worker = _SyncBackupWorker(
            "backup",
            profile.sync_worker_label,
            {
                "vault_manager": self.vault_manager,
                "enc_file_path": enc_file_path,
                "entries": self._local_entries(),
            },
        )
        self._backup_worker.progress.connect(self._on_backup_progress)
        self._backup_worker.finished.connect(self._on_backup_finished)
        self._backup_worker.error.connect(
            lambda err: self._on_backup_finished((False, str(err), None))
        )
        self._backup_worker.start()

    def _on_backup_progress(self, percent, text):
        dlg = getattr(self, "progress_dialog", None)
        if dlg is not None:
            dlg.setLabelText(text)
            dlg.setValue(percent)

    def _on_backup_finished(self, result):
        profile = self._listings_profile
        if getattr(self, "progress_dialog", None):
            self.progress_dialog.close()
            self.progress_dialog = None  # pyrefly: ignore [bad-assignment]

        if result is None:
            return  # cancelled (no result channel message by design)
        success, message, result_data = result
        if success:
            backup_count = result_data
            img_info = (
                f"\nAlso backed up {backup_count} image(s) to multi-part archive."
                if backup_count
                else ""
            )
            entries = self._local_entries()
            QMessageBox.information(
                self,
                "Backup Updated",
                f"Successfully generated encrypted backup {profile.backup_doc_label} file "
                f"with {len(entries)} entries.{img_info}",
            )
        else:
            QMessageBox.critical(
                self,
                "Backup Error",
                f"An error occurred while generating backup:\n{message}",
            )


__all__ = ["_BackupSyncMixin"]
