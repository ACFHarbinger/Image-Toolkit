"""``SyncDataSubtab`` — today's cloud-data sync UI as a self-contained widget.

Extracted from the monolithic ``DriveSyncTab`` so the parent can host it
alongside the new "Local Directory Sync" subtab in a ``QTabWidget``.  All
behaviour is unchanged; provider auth is delegated back to the parent
``DriveSyncTab`` via the ``get_auth_config`` / ``get_provider_text``
callables it passes at construction time.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import backend.src.constants as udef
from PySide6.QtCore import QThreadPool, Signal, Slot
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from .....constants import DRY_RUN
from .....helpers import DropboxDriveSyncWorker, GoogleDriveSyncWorker, OneDriveSyncWorker
from .....styles import apply_shadow_effect, set_button_role
from .....windows.logging import LogWindow


class SyncDataSubtab(QWidget):
    """Cloud-data one-way/bidirectional sync against a remote Drive folder.

    The parent ``DriveSyncTab`` owns auth state; this subtab receives two
    callables so it can query the currently selected provider and auth config
    without duplicating that logic.
    """

    # Emitted on every worker status message so the parent can forward to a
    # shared log if desired.
    status_update = Signal(str)

    def __init__(
        self,
        get_auth_config: Callable[[], Optional[Dict[str, Any]]],
        get_provider_text: Callable[[], str],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._get_auth_config = get_auth_config
        self._get_provider_text = get_provider_text
        self.current_worker: Optional[Any] = None
        self.log_window = LogWindow(parent=self)
        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)

        # --- Path config group ---
        config_group = QGroupBox("Sync Paths")
        config_layout = QVBoxLayout(config_group)

        local_layout = QHBoxLayout()
        self.local_path = QLineEdit(udef.LOCAL_SOURCE_PATH)
        self.local_path.setPlaceholderText("Local directory to synchronize")
        btn_browse_local = QPushButton("Browse Local Dir")
        apply_shadow_effect(btn_browse_local, "#000000", 8, 0, 3)
        btn_browse_local.clicked.connect(self._browse_local)
        local_layout.addWidget(self.local_path)
        local_layout.addWidget(btn_browse_local)

        remote_layout = QHBoxLayout()
        self.remote_path = QLineEdit(udef.DRIVE_DESTINATION_FOLDER_NAME)
        self.remote_path.setPlaceholderText("Drive folder (e.g. Backups/2025)")
        remote_layout.addWidget(self.remote_path)

        # Share folder (Google service account only — parent hides this group
        # for other providers via _update_provider_visibility())
        self.share_group = QGroupBox("Share Options")
        share_layout = QHBoxLayout(self.share_group)
        self.share_email_input = QLineEdit()
        self.share_email_input.setPlaceholderText(
            "Optional: user email to grant Editor access"
        )
        self.btn_share_folder = QPushButton("Share Folder Now")
        apply_shadow_effect(self.btn_share_folder, "#000000", 8, 0, 3)
        self.btn_share_folder.clicked.connect(self._share_remote_folder)
        share_layout.addWidget(QLabel("Share folder with:"))
        share_layout.addWidget(self.share_email_input)
        share_layout.addWidget(self.btn_share_folder)

        config_layout.addWidget(QLabel("Local Source Directory:"))
        config_layout.addLayout(local_layout)
        config_layout.addWidget(QLabel("Remote Destination Path:"))
        config_layout.addLayout(remote_layout)
        config_layout.addWidget(self.share_group)

        # --- Sync Behavior group ---
        behavior_group = QGroupBox("Sync Behavior")
        behavior_layout = QVBoxLayout(behavior_group)

        lbl_lo = QLabel("Action for files found ONLY Locally (Local Orphans):")
        lbl_lo.setStyleSheet("font-weight: bold; color: #3498db;")
        behavior_layout.addWidget(lbl_lo)
        self._bg_local = QButtonGroup(self)
        self.rb_upload = QRadioButton("Upload to Remote (Merge)")
        self.rb_upload.setChecked(True)
        self.rb_delete_local = QRadioButton("Delete from Local (Mirror Remote)")
        self.rb_delete_local.setStyleSheet("color: #e74c3c;")
        self.rb_ignore_local = QRadioButton("Do Nothing (Ignore)")
        self.rb_ignore_local.setStyleSheet("color: #95a5a6;")
        for rb in (self.rb_upload, self.rb_delete_local, self.rb_ignore_local):
            self._bg_local.addButton(rb)
        lo_row = QHBoxLayout()
        for rb in (self.rb_upload, self.rb_delete_local, self.rb_ignore_local):
            lo_row.addWidget(rb)
        lo_row.addStretch()
        behavior_layout.addLayout(lo_row)

        behavior_layout.addSpacing(8)
        lbl_ro = QLabel("Action for files found ONLY on Remote (Remote Orphans):")
        lbl_ro.setStyleSheet("font-weight: bold; color: #2ecc71;")
        behavior_layout.addWidget(lbl_ro)
        self._bg_remote = QButtonGroup(self)
        self.rb_download = QRadioButton("Download to Local (Merge)")
        self.rb_download.setChecked(True)
        self.rb_delete_remote = QRadioButton("Delete from Remote (Mirror Local)")
        self.rb_delete_remote.setStyleSheet("color: #e74c3c;")
        self.rb_ignore_remote = QRadioButton("Do Nothing (Ignore)")
        self.rb_ignore_remote.setStyleSheet("color: #95a5a6;")
        for rb in (self.rb_download, self.rb_delete_remote, self.rb_ignore_remote):
            self._bg_remote.addButton(rb)
        ro_row = QHBoxLayout()
        for rb in (self.rb_download, self.rb_delete_remote, self.rb_ignore_remote):
            ro_row.addWidget(rb)
        ro_row.addStretch()
        behavior_layout.addLayout(ro_row)

        # --- Dry-run + view map ---
        options_row = QHBoxLayout()
        self.dry_run_checkbox = QCheckBox("Perform Dry Run (Simulate only)")
        self.dry_run_checkbox.setChecked(DRY_RUN)
        self.dry_run_checkbox.setStyleSheet("QCheckBox { color: #f1c40f; }")
        self.btn_view_remote = QPushButton("View Remote Files Map")
        apply_shadow_effect(self.btn_view_remote, "#000000", 8, 0, 3)
        self.btn_view_remote.clicked.connect(self._view_remote_map)
        options_row.addWidget(self.dry_run_checkbox)
        options_row.addStretch()
        options_row.addWidget(self.btn_view_remote)

        # --- Sync button ---
        self.sync_button = QPushButton("Run Synchronization Now")
        set_button_role(self.sync_button, "success")
        apply_shadow_effect(self.sync_button, "#000000", 8, 0, 3)
        self.sync_button.clicked.connect(self._toggle_sync)

        main_layout.addWidget(config_group)
        main_layout.addWidget(behavior_group)
        main_layout.addLayout(options_row)
        main_layout.addWidget(self.sync_button)
        main_layout.addStretch(1)

    # ------------------------------------------------------------------
    # Provider-visibility wiring (called by parent on provider change)
    # ------------------------------------------------------------------

    def update_provider_visibility(self, provider_text: str) -> None:
        """Show/hide provider-specific widgets (called by parent)."""
        is_google_sa = provider_text.startswith("Google Drive (Service Account)")
        is_google = provider_text.startswith("Google Drive")
        self.share_group.setVisible(is_google_sa)
        self.btn_view_remote.setEnabled(is_google)
        self.sync_button.setEnabled(True)

    # ------------------------------------------------------------------
    # Config persistence
    # ------------------------------------------------------------------

    def collect(self) -> dict:
        act_local = "upload"
        if self.rb_delete_local.isChecked():
            act_local = "delete_local"
        elif self.rb_ignore_local.isChecked():
            act_local = "ignore_local"

        act_remote = "download"
        if self.rb_delete_remote.isChecked():
            act_remote = "delete_remote"
        elif self.rb_ignore_remote.isChecked():
            act_remote = "ignore_remote"

        return {
            "local_path": self.local_path.text().strip(),
            "remote_path": self.remote_path.text().strip(),
            "dry_run": self.dry_run_checkbox.isChecked(),
            "share_email": self.share_email_input.text().strip(),
            "action_local_orphans": act_local,
            "action_remote_orphans": act_remote,
        }

    def set_config(self, config: dict) -> None:
        self.local_path.setText(config.get("local_path", udef.LOCAL_SOURCE_PATH))
        self.remote_path.setText(
            config.get("remote_path", udef.DRIVE_DESTINATION_FOLDER_NAME)
        )
        self.dry_run_checkbox.setChecked(config.get("dry_run", True))
        self.share_email_input.setText(config.get("share_email", ""))

        act_local = config.get("action_local_orphans", "upload")
        if act_local == "delete_local":
            self.rb_delete_local.setChecked(True)
        elif act_local == "ignore_local":
            self.rb_ignore_local.setChecked(True)
        else:
            self.rb_upload.setChecked(True)

        act_remote = config.get("action_remote_orphans", "download")
        if act_remote == "delete_remote":
            self.rb_delete_remote.setChecked(True)
        elif act_remote == "ignore_remote":
            self.rb_ignore_remote.setChecked(True)
        else:
            self.rb_download.setChecked(True)

    # ------------------------------------------------------------------
    # Sync job control
    # ------------------------------------------------------------------

    def _toggle_sync(self) -> None:
        if self.current_worker is None:
            self._run_sync(clear_log=True)
        else:
            self._stop_sync()

    def _stop_sync(self) -> None:
        if self.current_worker:
            self.current_worker.stop()
            self._unlock_ui()
            self.log_window.append_log("\nManually interrupted. Resetting UI...")
            self.current_worker = None

    def _run_sync(self, clear_log: bool = True, force_live: bool = False) -> None:
        auth_config = self._get_auth_config()
        if not auth_config:
            return

        local_path = self.local_path.text().strip()
        remote_path = self.remote_path.text().strip()
        is_dry_run = self.dry_run_checkbox.isChecked() and not force_live

        if not os.path.isdir(local_path):
            QMessageBox.warning(self, "Error", f"Local folder invalid:\n{local_path}")
            return
        if not remote_path:
            QMessageBox.warning(self, "Error", "Remote path cannot be empty.")
            return

        share_email: Optional[str] = None
        if auth_config.get("mode") == "service_account":
            email = self.share_email_input.text().strip()
            if email:
                share_email = email

        act_local = (
            "delete_local"
            if self.rb_delete_local.isChecked()
            else "ignore_local"
            if self.rb_ignore_local.isChecked()
            else "upload"
        )
        act_remote = (
            "delete_remote"
            if self.rb_delete_remote.isChecked()
            else "ignore_remote"
            if self.rb_ignore_remote.isChecked()
            else "download"
        )

        msg = "STOP" if not is_dry_run else "STOP (Dry Run)"
        self._lock_ui(message=msg, is_running=True, clear_log=clear_log)
        self.log_window.show()

        provider_text = self._get_provider_text()
        common = {
            "auth_config": auth_config,
            "local_path": local_path,
            "remote_path": remote_path,
            "dry_run": is_dry_run,
            "action_local_orphans": act_local,
            "action_remote_orphans": act_remote,
        }

        if provider_text.startswith("Google Drive"):
            self.current_worker = GoogleDriveSyncWorker(
                **common, user_email_to_share_with=share_email
            )
        elif provider_text == "Dropbox":
            self.current_worker = DropboxDriveSyncWorker(**common)
        elif provider_text == "OneDrive":
            self.current_worker = OneDriveSyncWorker(**common)
        else:
            QMessageBox.warning(self, "Error", f"Unknown provider: {provider_text}")
            self._unlock_ui()
            return

        self.current_worker.signals.status_update.connect(self._on_status_update)
        self.current_worker.signals.sync_finished.connect(self._on_sync_finished)
        QThreadPool.globalInstance().start(self.current_worker)

    @Slot(str)
    def _on_status_update(self, msg: str) -> None:
        self.log_window.append_log(msg)
        self.status_update.emit(msg)

    @Slot(bool, str, bool)
    def _on_sync_finished(self, success: bool, message: str, was_dry_run: bool) -> None:
        self._unlock_ui()
        mode = "DRY RUN" if was_dry_run else "LIVE"
        status = "Completed" if success else "Failed"
        self.log_window.append_log(f"\nFINAL STATUS: {mode} Sync {status}. {message}")
        self.current_worker = None

        if not success and "manually cancelled" not in message:
            QMessageBox.critical(self, "Sync Failed", message)
            return

        if success and was_dry_run:
            reply = QMessageBox.question(
                self,
                "Dry Run Completed",
                "The Dry Run finished successfully.\n\n"
                "Do you want to apply these changes now (Execute LIVE Sync)?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.log_window.append_log(
                    "\nUser confirmed. Starting LIVE run..."
                )
                self._run_sync(clear_log=False, force_live=True)

    # ------------------------------------------------------------------
    # Minor actions
    # ------------------------------------------------------------------

    def _view_remote_map(self) -> None:
        auth_config = self._get_auth_config()
        if not auth_config:
            return
        remote_path = self.remote_path.text().strip()
        if not remote_path:
            QMessageBox.warning(self, "Error", "Remote path cannot be empty.")
            return

        self._lock_ui_minor()
        self.log_window.show()
        self.log_window.clear_log()

        worker = GoogleDriveSyncWorker(
            auth_config=auth_config,
            local_path=str(Path.home()),  # not used for listing
            remote_path=remote_path,
            dry_run=True,
        )
        worker.signals.status_update.connect(self._on_status_update)
        worker.signals.sync_finished.connect(lambda *_: self._unlock_ui_minor())
        QThreadPool.globalInstance().start(worker)

    def _share_remote_folder(self) -> None:
        QMessageBox.information(
            self,
            "Share Folder",
            "Run a sync first with the share email set — the folder will be shared "
            "automatically on the next sync.",
        )

    def _browse_local(self) -> None:
        from PySide6.QtWidgets import QFileDialog

        path = QFileDialog.getExistingDirectory(self, "Select Local Directory")
        if path:
            self.local_path.setText(path)

    # ------------------------------------------------------------------
    # UI lock helpers
    # ------------------------------------------------------------------

    def _lock_ui(
        self,
        message: str,
        is_running: bool = False,
        clear_log: bool = False,
    ) -> None:
        self.sync_button.setText(message)
        set_button_role(self.sync_button, "danger" if is_running else "success")
        self.sync_button.setEnabled(True)

        enabled = not is_running
        for w in (
            self.local_path,
            self.remote_path,
            self.dry_run_checkbox,
            self.rb_upload,
            self.rb_delete_local,
            self.rb_ignore_local,
            self.rb_download,
            self.rb_delete_remote,
            self.rb_ignore_remote,
            self.btn_view_remote,
            self.btn_share_folder,
            self.share_email_input,
        ):
            w.setEnabled(enabled)
        if clear_log:
            self.log_window.clear_log()
        QApplication.processEvents()

    def _unlock_ui(self) -> None:
        self._lock_ui(message="Run Synchronization Now", is_running=False)
        provider_text = self._get_provider_text()
        self.update_provider_visibility(provider_text)

    def _lock_ui_minor(self) -> None:
        self.btn_view_remote.setEnabled(False)
        self.btn_share_folder.setEnabled(False)
        self.sync_button.setEnabled(False)
        QApplication.processEvents()

    def _unlock_ui_minor(self) -> None:
        self.btn_view_remote.setEnabled(True)
        self.btn_share_folder.setEnabled(True)
        self.sync_button.setEnabled(True)


__all__ = ["SyncDataSubtab"]
