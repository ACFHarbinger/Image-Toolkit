"""Login/Vault Sync, Logging, and Reset State sections + their methods.

Extracted from ``settings_window.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from backend.src.constants import (
    DAEMON_CONFIG_PATH,
    IMAGE_TOOLKIT_DIR,
    LOCAL_SECRETS_DIR,
    SECRETS_DIR,
    THUMBNAIL_CACHE_DIR,
)
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)


class _ResetStateMixin:
    """Builds the Login/Vault Sync, Logging, and Reset State groupboxes and their handlers."""

    def _build_login_vault_section(self):
        login_groupbox = QGroupBox("Login/Account Information (Master Password Reset)")
        login_groupbox.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        login_layout = QFormLayout(login_groupbox)
        login_layout.setContentsMargins(10, 10, 10, 10)

        self.account_input = QLineEdit()
        self.account_input.setReadOnly(True)
        self.account_input.setText(self.current_account_name)

        self.new_password_input = QLineEdit()
        self.new_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.new_password_input.setPlaceholderText("Enter NEW Master Password to reset")

        login_layout.addRow(QLabel("Account Name:"), self.account_input)
        login_layout.addRow(QLabel("New Master Password:"), self.new_password_input)

        vault_sync_groupbox = QGroupBox("Cryptography Vault Sync and Load")
        vault_sync_groupbox.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        vault_sync_layout = QVBoxLayout(vault_sync_groupbox)
        vault_sync_layout.setContentsMargins(10, 10, 10, 10)

        vault_sync_desc = QLabel(
            "Synchronize active cryptography files between your home directory (~/.image-toolkit/secrets) "
            "and the repository templates (assets/secrets)."
        )
        vault_sync_desc.setStyleSheet("color: #aaa; font-size: 11px;")
        vault_sync_desc.setWordWrap(True)
        vault_sync_layout.addWidget(vault_sync_desc)

        btn_layout = QHBoxLayout()
        self.btn_sync_vault = QPushButton("Sync Vault 📤")
        self.btn_sync_vault.setToolTip(
            "Copy active keystore, vault, and pepper files from ~/.image-toolkit/secrets to the repository template directory."
        )
        self.btn_sync_vault.setStyleSheet("background-color: #7b1fa2; color: white; font-weight: bold;")
        self.btn_sync_vault.clicked.connect(self._sync_vault_to_assets)

        self.btn_load_vault = QPushButton("Load Vault 📥")
        self.btn_load_vault.setToolTip(
            "Overwrite active files in ~/.image-toolkit/secrets with template files from the repository directory."
        )
        self.btn_load_vault.setStyleSheet("background-color: #2c3e50; color: white; font-weight: bold;")
        self.btn_load_vault.clicked.connect(self._load_vault_from_assets)

        btn_layout.addWidget(self.btn_sync_vault)
        btn_layout.addWidget(self.btn_load_vault)
        vault_sync_layout.addLayout(btn_layout)

        return login_groupbox, vault_sync_groupbox

    def _build_logging_section(self) -> QGroupBox:
        logging_groupbox = QGroupBox("Logging")
        logging_groupbox.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        logging_layout = QFormLayout(logging_groupbox)
        logging_layout.setContentsMargins(10, 10, 10, 10)

        self.log_level_combo = QComboBox()
        self.log_level_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        self.log_level_combo.setCurrentText(self.pref_log_level)
        self.log_level_combo.setToolTip("Minimum severity level to write to the log (DEBUG = most verbose)")
        logging_layout.addRow("Log Level:", self.log_level_combo)

        self.file_logging_check = QCheckBox("Save logs to ~/.image-toolkit/logs/ (rotating, 5 × 1 MB)")
        self.file_logging_check.setChecked(self.pref_file_logging)
        logging_layout.addRow(self.file_logging_check)

        log_dir_label = QLabel(f"<small>Log directory: {IMAGE_TOOLKIT_DIR / 'logs'}</small>")
        log_dir_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        logging_layout.addRow(log_dir_label)

        log_buttons_layout = QHBoxLayout()
        self.btn_view_logs = QPushButton("View App Logs")
        self.btn_view_logs.setToolTip("Open the active application log file in the default system viewer.")
        self.btn_view_logs.clicked.connect(self._view_app_logs)

        self.btn_view_daemon_logs = QPushButton("View Daemon Logs")
        self.btn_view_daemon_logs.setToolTip("Open the slideshow daemon log file in the default system viewer.")
        self.btn_view_daemon_logs.clicked.connect(self._view_daemon_logs)

        log_buttons_layout.addWidget(self.btn_view_logs)
        log_buttons_layout.addWidget(self.btn_view_daemon_logs)
        logging_layout.addRow(log_buttons_layout)

        return logging_groupbox

    def _build_reset_state_section(self) -> QGroupBox:
        reset_groupbox = QGroupBox("Reset State")
        reset_groupbox.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        reset_state_layout = QVBoxLayout(reset_groupbox)
        reset_state_layout.setContentsMargins(10, 10, 10, 10)
        reset_state_layout.setSpacing(8)

        reset_state_layout.addWidget(QLabel("<b>Warning:</b> these actions are immediate and cannot be undone."))

        # Row 1: thumbnail cache
        cache_row = QHBoxLayout()
        cache_info = QLabel(f"<small>Disk thumbnail cache: <code>{THUMBNAIL_CACHE_DIR}</code></small>")
        cache_info.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.btn_clear_cache = QPushButton("Clear Thumbnail Cache")
        self.btn_clear_cache.setToolTip(
            "Delete all cached thumbnail files from disk. They will be regenerated on next gallery load."
        )
        self.btn_clear_cache.setStyleSheet("background-color: #e67e22; color: white; font-weight: bold;")
        self.btn_clear_cache.clicked.connect(self._clear_thumbnail_cache)
        cache_row.addWidget(cache_info, 1)
        cache_row.addWidget(self.btn_clear_cache)
        reset_state_layout.addLayout(cache_row)

        # Row 2: slideshow daemon reset
        daemon_row = QHBoxLayout()
        daemon_info = QLabel(
            "<small>Stops the daemon, removes its PID file, and deletes the slideshow config JSON file.</small>"
        )
        daemon_info.setWordWrap(True)
        self.btn_reset_daemon = QPushButton("Reset Slideshow Daemon")
        self.btn_reset_daemon.setToolTip("Delete the daemon PID file and remove the slideshow config JSON file.")
        self.btn_reset_daemon.setStyleSheet("background-color: #e67e22; color: white; font-weight: bold;")
        self.btn_reset_daemon.clicked.connect(self._reset_slideshow_daemon)
        daemon_row.addWidget(daemon_info, 1)
        daemon_row.addWidget(self.btn_reset_daemon)
        reset_state_layout.addLayout(daemon_row)

        # Row 2.5: reset extraction history
        history_row = QHBoxLayout()
        history_info = QLabel(
            "<small>Delete the central extraction history JSON file containing parameters and file associations.</small>"
        )
        history_info.setWordWrap(True)
        self.btn_reset_history = QPushButton("Reset Extraction History")
        self.btn_reset_history.setToolTip(
            "Deletes the .extraction_history.json file on disk and resets the dropdown selection list."
        )
        self.btn_reset_history.setStyleSheet("background-color: #e67e22; color: white; font-weight: bold;")
        self.btn_reset_history.clicked.connect(self._reset_extraction_history)
        history_row.addWidget(history_info, 1)
        history_row.addWidget(self.btn_reset_history)
        reset_state_layout.addLayout(history_row)

        # Row 3: clear logs
        logs_row = QHBoxLayout()
        logs_info = QLabel(
            f"<small>Application and daemon logs directory: <code>{IMAGE_TOOLKIT_DIR / 'logs'}</code></small>"
        )
        logs_info.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.btn_clear_logs = QPushButton("Clear All Logs")
        self.btn_clear_logs.setToolTip("Delete all application and daemon log files from disk.")
        self.btn_clear_logs.setStyleSheet("background-color: #e67e22; color: white; font-weight: bold;")
        self.btn_clear_logs.clicked.connect(self._clear_application_logs)
        logs_row.addWidget(logs_info, 1)
        logs_row.addWidget(self.btn_clear_logs)
        reset_state_layout.addLayout(logs_row)

        # Row 4: tab configs + system profiles
        tab_cfg_row = QHBoxLayout()
        tab_cfg_info = QLabel(
            "<small>Removes all saved tab configurations, active tab config "
            "assignments, and system preference profiles from the vault.</small>"
        )
        tab_cfg_info.setWordWrap(True)
        self.btn_clear_tab_configs = QPushButton("Clear Tab Configs and Profiles")
        self.btn_clear_tab_configs.setToolTip(
            "Wipe tab_configurations, active_tab_configs, and system_preference_profiles from the vault."
        )
        self.btn_clear_tab_configs.setStyleSheet("background-color: #c0392b; color: white; font-weight: bold;")
        self.btn_clear_tab_configs.clicked.connect(self._clear_tab_configs)
        tab_cfg_row.addWidget(tab_cfg_info, 1)
        tab_cfg_row.addWidget(self.btn_clear_tab_configs)
        reset_state_layout.addLayout(tab_cfg_row)

        return reset_groupbox

    # ------------------------------------------------------------------
    # --- Reset State Methods ------------------------------------------
    # ------------------------------------------------------------------

    def _clear_thumbnail_cache(self):
        """Deletes all cached thumbnail files from the disk cache directory."""
        reply = QMessageBox.question(
            self,
            "Confirm Clear",
            f"Delete all thumbnail cache files in:\n{THUMBNAIL_CACHE_DIR}\n\n"
            "Thumbnails will be regenerated on the next gallery load.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            if THUMBNAIL_CACHE_DIR.exists():
                shutil.rmtree(str(THUMBNAIL_CACHE_DIR))
                THUMBNAIL_CACHE_DIR.mkdir(parents=True, exist_ok=True)
                deleted_msg = "Thumbnail cache cleared successfully."
            else:
                deleted_msg = "Thumbnail cache directory did not exist — nothing to clear."
            QMessageBox.information(self, "Cache Cleared", deleted_msg)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to clear thumbnail cache:\n{e}")

    def _reset_slideshow_daemon(self):
        """Stops the daemon, deletes its PID file, and deletes the config JSON file."""
        reply = QMessageBox.question(
            self,
            "Confirm Reset",
            "This will:\n"
            f"  • Delete the PID file ({IMAGE_TOOLKIT_DIR / '.slideshow.pid'})\n"
            f"  • Delete the slideshow config file ({DAEMON_CONFIG_PATH})\n\n"
            "The daemon will stop if it is currently running. Log files will NOT be deleted.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        messages = []
        errors = []

        pid_path = IMAGE_TOOLKIT_DIR / ".slideshow.pid"
        try:
            if pid_path.exists():
                pid_path.unlink()
                messages.append("Deleted PID file.")
            else:
                messages.append("PID file not found (already clean).")
        except Exception as e:
            errors.append(f"Could not delete PID file: {e}")

        try:
            if DAEMON_CONFIG_PATH.exists():
                DAEMON_CONFIG_PATH.unlink()
                messages.append("Deleted slideshow config file.")
            else:
                messages.append("Slideshow config file not found (already clean).")
        except Exception as e:
            errors.append(f"Could not delete slideshow config file: {e}")

        summary = "\n".join(messages)
        if errors:
            QMessageBox.warning(
                self,
                "Partial Reset",
                f"Completed with issues:\n{summary}\n\nErrors:\n" + "\n".join(errors),
            )
        else:
            QMessageBox.information(self, "Daemon Reset", summary)

    def _reset_extraction_history(self):
        """Deletes the .extraction_history.json file and clears the UI dropdown."""
        history_file = IMAGE_TOOLKIT_DIR / ".extraction_history.json"
        reply = QMessageBox.question(
            self,
            "Confirm Reset",
            f"Are you sure you want to delete the extraction history file?\n\n{history_file}\n\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            if history_file.exists():
                history_file.unlink()
                QMessageBox.information(self, "Success", "Extraction history file deleted successfully.")
            else:
                QMessageBox.information(
                    self,
                    "Information",
                    "Extraction history file not found (already clean).",
                )

            # Immediately notify tabs to reload / clear history
            if self.main_window_ref:
                for cat_tabs in self.main_window_ref.all_tabs.values():
                    for tab in cat_tabs.values():
                        if hasattr(tab, "_load_extraction_history") and callable(tab._load_extraction_history):
                            tab._load_extraction_history()
                        if hasattr(tab, "_update_recent_extractions_ui") and callable(
                            tab._update_recent_extractions_ui
                        ):
                            tab._update_recent_extractions_ui()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to reset extraction history:\n{e}")

    def _view_app_logs(self):
        """Opens the application log file in the default system viewer."""
        log_path = IMAGE_TOOLKIT_DIR / "logs" / "image_toolkit.log"
        if not log_path.exists():
            QMessageBox.information(self, "No Logs", "No application log file found yet.")
            return

        try:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(log_path)))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open log file:\n{e}")

    def _view_daemon_logs(self):
        """Opens the daemon log file in the default system viewer."""
        log_path = IMAGE_TOOLKIT_DIR / "logs" / "slideshow_daemon.log"
        if not log_path.exists():
            QMessageBox.information(self, "No Logs", "No daemon log file found yet.")
            return

        try:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(log_path)))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open daemon log file:\n{e}")

    def _clear_application_logs(self):
        """Deletes all log files from the global logs directory."""
        log_dir = IMAGE_TOOLKIT_DIR / "logs"
        reply = QMessageBox.question(
            self,
            "Confirm Clear Logs",
            f"Delete all application and daemon log files in:\n{log_dir}?\n\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            if log_dir.exists():
                # Delete all contents but keep the directory
                for item in log_dir.iterdir():
                    if item.is_file():
                        item.unlink()
                    elif item.is_dir():
                        shutil.rmtree(str(item))
                deleted_msg = "All logs cleared successfully."
            else:
                deleted_msg = "Log directory did not exist — nothing to clear."
            QMessageBox.information(self, "Logs Cleared", deleted_msg)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to clear logs:\n{e}")

    def _clear_tab_configs(self):
        """Wipes all tab configurations, active assignments, and system profiles from the vault."""
        reply = QMessageBox.question(
            self,
            "Confirm Clear",
            "This will permanently remove:\n"
            "  • All saved tab configurations\n"
            "  • All active tab config assignments\n"
            "  • All system preference profiles\n\n"
            "This cannot be undone. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        if not self.vault_manager:
            QMessageBox.critical(self, "Error", "Vault manager is not available.")
            return

        try:
            user_data = self.vault_manager.load_account_credentials()
            user_data["tab_configurations"] = {}
            user_data["active_tab_configs"] = {}
            user_data["system_preference_profiles"] = {}
            user_data["session_recovery_data"] = {}

            # Clear the encrypted session recovery file if it exists
            try:
                username = getattr(self.vault_manager, "account_name", None)
                if username:
                    for recovery_dir in (os.path.expanduser("~/.image-toolkit/recovery"),):
                        enc_file_path = os.path.join(recovery_dir, f"recovery_{username}.enc")
                        if os.path.exists(enc_file_path):
                            os.remove(enc_file_path)
            except Exception as e:
                print(f"Warning: Failed to delete recovery file: {e}")

            if self._save_vault_data(user_data):
                # Reset in-memory state
                self.tab_defaults_config = {}
                self.active_tab_configs = {}
                self.system_profiles = {}

                # Reset UI combo boxes
                for combo in self.startup_config_combos.values():
                    combo.clear()
                    combo.addItem("None (Default)")
                self._refresh_profile_combo()

                QMessageBox.information(
                    self,
                    "Cleared",
                    "All tab configurations and system profiles have been removed.",
                )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to clear tab configs:\n{e}")

    def _sync_vault_to_assets(self):
        """
        Sync active files from ~/.image-toolkit/secrets to the assets/secrets template directory.
        """
        active_dir = Path(LOCAL_SECRETS_DIR)
        template_dir = Path(SECRETS_DIR)
        if not active_dir.exists():
            QMessageBox.warning(self, "Sync Error", "Active cryptography directory does not exist.")
            return

        template_dir.mkdir(parents=True, exist_ok=True)

        # List of files to sync
        files_to_sync = []
        for item in active_dir.iterdir():
            if item.is_file():
                files_to_sync.append(item.name)

        if not files_to_sync:
            QMessageBox.information(
                self,
                "Sync Vault",
                "No cryptographic files found in active directory to sync.",
            )
            return

        try:
            for fname in files_to_sync:
                src = active_dir / fname
                dst = template_dir / fname
                shutil.copy2(src, dst)
                print(f"[SettingsWindow] Synced {src} -> {dst}")

            QMessageBox.information(
                self,
                "Sync Vault Success",
                f"Successfully synced {len(files_to_sync)} cryptographic file(s) to template directory:\n{template_dir}",
            )
        except Exception as e:
            QMessageBox.critical(self, "Sync Error", f"Failed to sync vault files: {e}")

    def _load_vault_from_assets(self):
        """
        Load (overwrite) active files in ~/.image-toolkit/secrets with ones from the assets/secrets template directory.
        """
        active_dir = Path(LOCAL_SECRETS_DIR)
        template_dir = Path(SECRETS_DIR)
        if not template_dir.exists():
            QMessageBox.warning(
                self,
                "Load Error",
                "Repository template cryptography directory does not exist.",
            )
            return

        # Confirm overwrite
        reply = QMessageBox.question(
            self,
            "Confirm Load Vault",
            "This will OVERWRITE your active cryptography files in ~/.image-toolkit/secrets with the template files. "
            "Are you sure you want to proceed?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        active_dir.mkdir(parents=True, exist_ok=True)

        # List of files to load
        files_to_load = []
        for item in template_dir.iterdir():
            if item.is_file():
                files_to_load.append(item.name)

        if not files_to_load:
            QMessageBox.information(
                self,
                "Load Vault",
                "No template files found in assets directory to load.",
            )
            return

        try:
            for fname in files_to_load:
                src = template_dir / fname
                dst = active_dir / fname
                shutil.copy2(src, dst)
                print(f"[SettingsWindow] Loaded {src} -> {dst}")

            QMessageBox.information(
                self,
                "Load Vault Success",
                f"Successfully loaded {len(files_to_load)} cryptographic file(s) to active directory:\n{active_dir}\nPlease restart the application to apply.",
            )
        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"Failed to load vault files: {e}")


__all__ = ["_ResetStateMixin"]
