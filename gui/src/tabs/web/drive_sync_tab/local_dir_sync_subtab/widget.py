"""``LocalDirSyncSubtab`` — Bidirectional sync of ``~/.image-toolkit/`` ↔ remote cloud folder.

Allows syncing configs, themes, presets, and metadata between machines
while strictly excluding keystores, private keys, logs, and cache by default.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

from PySide6.QtCore import Signal, Slot
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .....helpers.web.cloud.local_dir_sync_worker import (
    DEFAULT_EXCLUDES,
    ConflictPolicy,
    LocalDirSyncWorker,
)
from .....styles import apply_shadow_effect, set_button_role
from .....windows.logging import LogWindow


class LocalDirSyncSubtab(QWidget):
    """Subtab for synchronizing ~/.image-toolkit/ with a remote cloud directory."""

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
        self.current_worker: Optional[LocalDirSyncWorker] = None
        self.log_window = LogWindow(parent=self)
        self._warned_cloud_transfer = False

        self._build_ui()

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)

        # ------------------ SECURITY NOTICE BANNER ------------------
        security_box = QGroupBox("Privacy & Security Notice")
        sec_layout = QVBoxLayout(security_box)
        sec_label = QLabel(
            "Local Directory Sync sends non-secret configuration, QSS styles, and metadata "
            "from your local application directory to your cloud storage. "
            "Private vault keys (*.vault, *.p12, *.key) and logs containing local file paths "
            "are excluded by default."
        )
        sec_label.setWordWrap(True)
        sec_label.setStyleSheet("color: #e67e22; font-weight: bold;")
        sec_layout.addWidget(sec_label)

        # ------------------ PATHS CONFIG ------------------
        path_group = QGroupBox("Directory Configuration")
        path_layout = QVBoxLayout(path_group)

        # Local directory
        local_row = QHBoxLayout()
        self.local_path_input = QLineEdit(str(Path.home() / ".image-toolkit"))
        btn_browse_local = QPushButton("Browse")
        apply_shadow_effect(btn_browse_local, "#000000", 8, 0, 3)
        btn_browse_local.clicked.connect(self._browse_local_dir)
        local_row.addWidget(self.local_path_input)
        local_row.addWidget(btn_browse_local)

        # Remote directory
        remote_row = QHBoxLayout()
        self.remote_folder_input = QLineEdit(".image-toolkit")
        self.remote_folder_input.setPlaceholderText("Remote cloud folder name (e.g. .image-toolkit)")
        remote_row.addWidget(self.remote_folder_input)

        path_layout.addWidget(QLabel("Local Application Directory (~/.image-toolkit/):"))
        path_layout.addLayout(local_row)
        path_layout.addWidget(QLabel("Remote Destination Directory:"))
        path_layout.addLayout(remote_row)

        # ------------------ CONFLICT & EXCLUDES ------------------
        options_group = QGroupBox("Sync Options & Excludes")
        opt_layout = QVBoxLayout(options_group)

        # Conflict resolution policy
        policy_label = QLabel("Conflict Resolution Policy (when modified on both sides):")
        policy_label.setStyleSheet("font-weight: bold; color: #3498db;")
        opt_layout.addWidget(policy_label)

        self.bg_policy = QButtonGroup(self)
        self.rb_newer_wins = QRadioButton("Newer Wins (Timestamp comparison)")
        self.rb_newer_wins.setChecked(True)
        self.rb_prefer_local = QRadioButton("Prefer Local (Overwrite Remote)")
        self.rb_prefer_remote = QRadioButton("Prefer Remote (Overwrite Local)")

        self.bg_policy.addButton(self.rb_newer_wins)
        self.bg_policy.addButton(self.rb_prefer_local)
        self.bg_policy.addButton(self.rb_prefer_remote)

        policy_row = QHBoxLayout()
        policy_row.addWidget(self.rb_newer_wins)
        policy_row.addWidget(self.rb_prefer_local)
        policy_row.addWidget(self.rb_prefer_remote)
        policy_row.addStretch()
        opt_layout.addLayout(policy_row)

        # Excludes text area
        opt_layout.addSpacing(6)
        opt_layout.addWidget(QLabel("Exclude Patterns (comma or newline separated):"))
        self.excludes_edit = QTextEdit()
        self.excludes_edit.setMaximumHeight(65)
        self.excludes_edit.setPlainText(", ".join(DEFAULT_EXCLUDES))
        opt_layout.addWidget(self.excludes_edit)

        # ------------------ EXECUTION CONTROLS ------------------
        ctrl_layout = QHBoxLayout()
        self.dry_run_checkbox = QCheckBox("Perform Dry Run (Simulate plan only)")
        self.dry_run_checkbox.setChecked(True)
        self.dry_run_checkbox.setStyleSheet("QCheckBox { color: #f1c40f; font-weight: bold; }")

        self.btn_view_plan = QPushButton("Preview Sync Plan")
        apply_shadow_effect(self.btn_view_plan, "#000000", 8, 0, 3)
        self.btn_view_plan.clicked.connect(self._preview_plan)

        ctrl_layout.addWidget(self.dry_run_checkbox)
        ctrl_layout.addStretch()
        ctrl_layout.addWidget(self.btn_view_plan)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)

        # Main sync button
        self.sync_button = QPushButton("Run Directory Sync Now")
        set_button_role(self.sync_button, "success")
        apply_shadow_effect(self.sync_button, "#000000", 8, 0, 3)
        self.sync_button.clicked.connect(self._toggle_sync)

        # Assemble main layout
        main_layout.addWidget(security_box)
        main_layout.addWidget(path_group)
        main_layout.addWidget(options_group)
        main_layout.addLayout(ctrl_layout)
        main_layout.addWidget(self.progress_bar)
        main_layout.addWidget(self.sync_button)
        main_layout.addStretch(1)

    def _browse_local_dir(self) -> None:
        chosen = QFileDialog.getExistingDirectory(
            self,
            "Select Local Application Directory",
            self.local_path_input.text().strip(),
        )
        if chosen:
            self.local_path_input.setText(chosen)

    def _get_conflict_policy(self) -> ConflictPolicy:
        if self.rb_prefer_local.isChecked():
            return ConflictPolicy.PREFER_LOCAL
        if self.rb_prefer_remote.isChecked():
            return ConflictPolicy.PREFER_REMOTE
        return ConflictPolicy.NEWER_WINS

    def _get_excludes(self) -> Tuple[str, ...]:
        raw = self.excludes_edit.toPlainText().replace("\n", ",")
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        return tuple(parts)

    def update_provider_visibility(self, provider_text: str) -> None:
        """Called by parent when provider changes."""
        self.sync_button.setEnabled(True)
        self.btn_view_plan.setEnabled(True)

    def collect(self) -> dict:
        return {
            "local_path": self.local_path_input.text().strip(),
            "remote_folder": self.remote_folder_input.text().strip(),
            "conflict_policy": self._get_conflict_policy().value,
            "excludes": self.excludes_edit.toPlainText().strip(),
            "dry_run": self.dry_run_checkbox.isChecked(),
        }

    def set_config(self, config: dict) -> None:
        if "local_path" in config:
            self.local_path_input.setText(config["local_path"])
        if "remote_folder" in config:
            self.remote_folder_input.setText(config["remote_folder"])
        if "dry_run" in config:
            self.dry_run_checkbox.setChecked(bool(config["dry_run"]))
        if "excludes" in config:
            self.excludes_edit.setPlainText(config["excludes"])

        pol = config.get("conflict_policy", ConflictPolicy.NEWER_WINS.value)
        if pol == ConflictPolicy.PREFER_LOCAL.value:
            self.rb_prefer_local.setChecked(True)
        elif pol == ConflictPolicy.PREFER_REMOTE.value:
            self.rb_prefer_remote.setChecked(True)
        else:
            self.rb_newer_wins.setChecked(True)

    def _preview_plan(self) -> None:
        self._start_worker(dry_run=True)

    def _toggle_sync(self) -> None:
        if self.current_worker is None:
            self._start_worker(dry_run=self.dry_run_checkbox.isChecked())
        else:
            self._stop_sync()

    def _stop_sync(self) -> None:
        if self.current_worker:
            self.current_worker.stop()
            self._unlock_ui()
            self.log_window.append_log("\nDirectory sync interrupted by user.")
            self.current_worker = None

    def _start_worker(self, dry_run: bool) -> None:
        # Check one-time confirmation warning for live sync
        if not dry_run and not self._warned_cloud_transfer:
            reply = QMessageBox.warning(
                self,
                "Cloud Transfer Confirmation",
                "You are about to synchronize files from ~/.image-toolkit/ to the cloud.\n\n"
                "Although private vault keys and logs are excluded, other configuration and metadata "
                "will be uploaded to your connected cloud account.\n\n"
                "Do you want to proceed with live synchronization?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            self._warned_cloud_transfer = True

        auth_config = self._get_auth_config()
        if not auth_config:
            return

        local_dir = Path(self.local_path_input.text().strip())
        if not local_dir.is_dir():
            QMessageBox.warning(self, "Invalid Path", f"Local directory does not exist:\n{local_dir}")
            return

        remote_folder = self.remote_folder_input.text().strip()
        if not remote_folder:
            QMessageBox.warning(self, "Invalid Path", "Remote destination folder name cannot be empty.")
            return

        provider_text = self._get_provider_text()

        self._lock_ui(is_running=True, dry_run=dry_run)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.log_window.show()
        self.log_window.clear_log()

        self.current_worker = LocalDirSyncWorker(
            auth_config=auth_config,
            provider_text=provider_text,
            local_root=local_dir,
            remote_folder=remote_folder,
            dry_run=dry_run,
            conflict_policy=self._get_conflict_policy(),
            excludes=self._get_excludes(),
            parent=self,
        )

        self.current_worker.status.connect(self._on_status)
        self.current_worker.progress.connect(self._on_progress)
        self.current_worker.finished.connect(self._on_finished)
        self.current_worker.start()

    @Slot(str)
    def _on_status(self, msg: str) -> None:
        self.log_window.append_log(msg)
        self.status_update.emit(msg)

    @Slot(int, int)
    def _on_progress(self, done: int, total: int) -> None:
        if total > 0:
            self.progress_bar.setMaximum(total)
            self.progress_bar.setValue(done)

    @Slot(bool, str, bool)
    def _on_finished(self, success: bool, message: str, was_dry_run: bool) -> None:
        self._unlock_ui()
        self.progress_bar.setVisible(False)
        mode = "DRY RUN" if was_dry_run else "LIVE"
        status = "Success" if success else "Failed"
        self.log_window.append_log(f"\n[{mode}] Directory Sync {status}: {message}")
        self.current_worker = None

        if not success and "Cancelled" not in message:
            QMessageBox.critical(self, "Sync Error", message)
            return

        if success and was_dry_run:
            reply = QMessageBox.question(
                self,
                "Dry Run Completed",
                "Dry run completed successfully with no errors.\n\n"
                "Would you like to execute LIVE synchronization now?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._start_worker(dry_run=False)

    def _lock_ui(self, is_running: bool, dry_run: bool) -> None:
        msg = "STOP" if not dry_run else "STOP (Dry Run)"
        self.sync_button.setText(msg if is_running else "Run Directory Sync Now")
        set_button_role(self.sync_button, "danger" if is_running else "success")

        enabled = not is_running
        self.local_path_input.setEnabled(enabled)
        self.remote_folder_input.setEnabled(enabled)
        self.excludes_edit.setEnabled(enabled)
        self.dry_run_checkbox.setEnabled(enabled)
        self.btn_view_plan.setEnabled(enabled)
        self.rb_newer_wins.setEnabled(enabled)
        self.rb_prefer_local.setEnabled(enabled)
        self.rb_prefer_remote.setEnabled(enabled)
        QApplication.processEvents()

    def _unlock_ui(self) -> None:
        self._lock_ui(is_running=False, dry_run=False)


__all__ = ["LocalDirSyncSubtab"]
