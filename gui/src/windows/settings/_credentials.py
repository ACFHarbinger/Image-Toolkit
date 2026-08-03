"""Credentials, Favourite Directories, and Bulk Update sections + their methods.

Extracted from ``settings_window.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path

from backend.src.constants import API_DIR, ROOT_DIR
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
)

from .app_settings import AppSettings


def dry_run_replace(search: str, replace: str, use_regex: bool, changes: list, val, path_str: str = "") -> None:
    """Recursively record what a bulk find/replace would change, without applying it."""
    if isinstance(val, str):
        if use_regex:
            try:
                new_val, count = re.subn(search, replace, val)
            except Exception:
                new_val = val.replace(search, replace)
                count = val.count(search)
        else:
            new_val = val.replace(search, replace)
            count = val.count(search)
        if count > 0:
            changes.append(f"[{path_str}] '{val}' ➡️ '{new_val}'")
    elif isinstance(val, dict):
        for k, v in val.items():
            dry_run_replace(search, replace, use_regex, changes, v, f"{path_str}/{k}" if path_str else k)
    elif isinstance(val, list):
        for idx, item in enumerate(val):
            dry_run_replace(search, replace, use_regex, changes, item, f"{path_str}[{idx}]")


def recursive_replace(search: str, replace: str, use_regex: bool, val):
    """Recursively apply a bulk find/replace, returning (new_value, replacement_count)."""
    if isinstance(val, str):
        if use_regex:
            try:
                new_val, count = re.subn(search, replace, val)
                return new_val, count
            except Exception:
                new_val = val.replace(search, replace)
                count = val.count(search)
                return new_val, count
        else:
            new_val = val.replace(search, replace)
            count = val.count(search)
            return new_val, count
    elif isinstance(val, dict):
        new_dict = {}
        local_count = 0
        for k, v in val.items():
            new_v, count = recursive_replace(search, replace, use_regex, v)
            new_dict[k] = new_v
            local_count += count
        return new_dict, local_count
    elif isinstance(val, list):
        new_list = []
        local_count = 0
        for item in val:
            new_item, count = recursive_replace(search, replace, use_regex, item)
            new_list.append(new_item)
            local_count += count
        return new_list, local_count
    return val, 0


class _CredentialsMixin:
    """Builds the Credentials, Favourites, and Bulk Update sections and their handlers."""

    def _build_credentials_section(self) -> QGroupBox:
        credentials_groupbox = QGroupBox("Manage Loaded Credentials")
        credentials_groupbox.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        credentials_layout = QVBoxLayout(credentials_groupbox)
        credentials_layout.setContentsMargins(10, 10, 10, 10)

        credentials_desc = QLabel(
            "Manage API credentials loaded in your secure session vault. "
            "You can export unencrypted versions of these files to the backup directory, "
            "import new JSON credential files, or delete existing credentials."
        )
        credentials_desc.setStyleSheet("color: #aaa; font-size: 11px;")
        credentials_desc.setWordWrap(True)
        credentials_layout.addWidget(credentials_desc)

        self.credentials_list = QListWidget()
        self.credentials_list.setMinimumHeight(120)
        self.credentials_list.setMaximumHeight(200)
        self.credentials_list.itemDoubleClicked.connect(self._edit_credential)
        credentials_layout.addWidget(self.credentials_list)

        creds_btn_layout = QHBoxLayout()
        self.btn_export_creds = QPushButton("Export to Backup 📤")
        self.btn_export_creds.setToolTip("Export unencrypted versions of loaded credentials to the backup directory.")
        self.btn_export_creds.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold;")
        self.btn_export_creds.clicked.connect(self._export_credentials_to_backup)

        self.btn_import_cred = QPushButton("Import Credential 📥")
        self.btn_import_cred.setToolTip("Select a new JSON credential file to encrypt and load into the vault.")
        self.btn_import_cred.setStyleSheet("background-color: #2980b9; color: white; font-weight: bold;")
        self.btn_import_cred.clicked.connect(self._import_credential)

        self.btn_edit_cred = QPushButton("Edit Credential ✏️")
        self.btn_edit_cred.setToolTip("View and edit the JSON values of the selected credential.")
        self.btn_edit_cred.setStyleSheet("background-color: #f39c12; color: white; font-weight: bold;")
        self.btn_edit_cred.clicked.connect(self._edit_credential)

        self.btn_delete_cred = QPushButton("Delete Credential ❌")
        self.btn_delete_cred.setToolTip("Delete the selected credential from the vault and disk.")
        self.btn_delete_cred.setStyleSheet("background-color: #c0392b; color: white; font-weight: bold;")
        self.btn_delete_cred.clicked.connect(self._delete_credential)

        creds_btn_layout.addWidget(self.btn_export_creds)
        creds_btn_layout.addWidget(self.btn_import_cred)
        creds_btn_layout.addWidget(self.btn_edit_cred)
        creds_btn_layout.addWidget(self.btn_delete_cred)
        credentials_layout.addLayout(creds_btn_layout)

        return credentials_groupbox

    def _build_favourites_section(self) -> QGroupBox:
        fav_dir_groupbox = QGroupBox("Favourite Directories")
        fav_dir_groupbox.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        fav_dir_layout = QVBoxLayout(fav_dir_groupbox)
        fav_dir_layout.setContentsMargins(10, 10, 10, 10)
        fav_dir_layout.setSpacing(8)

        fav_dir_desc = QLabel(
            "Configure your favourite directories. These directories will appear in the sidebar "
            "of all directory browsing and scan windows."
        )
        fav_dir_desc.setStyleSheet("color: #aaa; font-size: 11px;")
        fav_dir_desc.setWordWrap(True)
        fav_dir_layout.addWidget(fav_dir_desc)

        fav_content_layout = QHBoxLayout()

        self.fav_list_widget = QListWidget()
        self.fav_list_widget.setMinimumHeight(100)
        self.fav_list_widget.setMaximumHeight(200)
        self.fav_list_widget.addItems(self.pref_favourite_directories)
        fav_content_layout.addWidget(self.fav_list_widget, 1)

        fav_buttons_layout = QVBoxLayout()
        fav_buttons_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.btn_add_fav_browse = QPushButton("Browse to Add 📁")
        self.btn_add_fav_browse.setToolTip("Browse the filesystem to select a directory to add to favourites.")
        self.btn_add_fav_browse.setStyleSheet("background-color: #2980b9; color: white; font-weight: bold;")
        self.btn_add_fav_browse.clicked.connect(self._browse_add_favourite)

        self.btn_remove_fav = QPushButton("Remove Selected ❌")
        self.btn_remove_fav.setToolTip("Remove the selected directory from your favourites list.")
        self.btn_remove_fav.setStyleSheet("background-color: #c0392b; color: white; font-weight: bold;")
        self.btn_remove_fav.clicked.connect(self._remove_selected_favourite)

        fav_buttons_layout.addWidget(self.btn_add_fav_browse)
        fav_buttons_layout.addWidget(self.btn_remove_fav)
        fav_content_layout.addLayout(fav_buttons_layout)

        fav_dir_layout.addLayout(fav_content_layout)

        fav_manual_layout = QHBoxLayout()
        self.fav_path_input = QLineEdit()
        self.fav_path_input.setPlaceholderText("Or paste/type absolute folder path here...")

        self.btn_add_fav_path = QPushButton("Add Path ➕")
        self.btn_add_fav_path.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold;")
        self.btn_add_fav_path.clicked.connect(self._add_manual_favourite)

        fav_manual_layout.addWidget(self.fav_path_input, 1)
        fav_manual_layout.addWidget(self.btn_add_fav_path)
        fav_dir_layout.addLayout(fav_manual_layout)

        return fav_dir_groupbox

    def _build_bulk_update_tab(self) -> QGroupBox:
        bulk_groupbox = QGroupBox("Bulk Find and Replace / Pattern Update")
        bulk_layout = QFormLayout(bulk_groupbox)
        bulk_layout.setContentsMargins(15, 15, 15, 15)
        bulk_layout.setSpacing(12)

        bulk_desc = QLabel(
            "Bulk update any config fields/settings paths, tab configurations, "
            "or startup preference profiles matching a pattern or substring."
        )
        bulk_desc.setStyleSheet("color: #aaa; font-size: 11px;")
        bulk_desc.setWordWrap(True)
        bulk_layout.addRow(bulk_desc)

        self.bulk_search_input = QLineEdit()
        self.bulk_search_input.setPlaceholderText("e.g. data")
        self.bulk_search_input.setToolTip("Enter the substring or pattern to match")
        bulk_layout.addRow("Find / Pattern:", self.bulk_search_input)

        self.bulk_replace_input = QLineEdit()
        self.bulk_replace_input.setPlaceholderText("e.g. Data")
        self.bulk_replace_input.setToolTip("Enter the replacement string")
        bulk_layout.addRow("Replace With:", self.bulk_replace_input)

        self.bulk_regex_check = QCheckBox("Use Regular Expressions")
        self.bulk_regex_check.setToolTip("Interpret the find pattern as a regular expression")
        bulk_layout.addRow("", self.bulk_regex_check)

        # Targets
        target_label = QLabel("<b>Targets:</b>")
        bulk_layout.addRow(target_label)

        self.bulk_target_vault = QCheckBox("Secure Vault (Preferences, Tab default configurations, Startup profiles)")
        self.bulk_target_vault.setChecked(True)
        bulk_layout.addRow("", self.bulk_target_vault)

        self.bulk_target_qsettings = QCheckBox("QSettings (Last/Recent directories, Splitters, Window settings)")
        self.bulk_target_qsettings.setChecked(True)
        bulk_layout.addRow("", self.bulk_target_qsettings)

        # Actions
        btn_layout = QHBoxLayout()
        self.btn_bulk_preview = QPushButton("Preview Changes")
        self.btn_bulk_preview.clicked.connect(self._preview_bulk_update)
        self.btn_bulk_preview.setStyleSheet("background-color: #34495e; color: white; font-weight: bold;")

        self.btn_bulk_apply = QPushButton("Apply Bulk Update")
        self.btn_bulk_apply.clicked.connect(self._apply_bulk_update)
        self.btn_bulk_apply.setStyleSheet("background-color: #e74c3c; color: white; font-weight: bold;")

        btn_layout.addWidget(self.btn_bulk_preview)
        btn_layout.addWidget(self.btn_bulk_apply)
        bulk_layout.addRow("", btn_layout)

        return bulk_groupbox

    # ---------------------------------------------------------------------
    # --- Credential Management Methods ---
    # ---------------------------------------------------------------------

    def _refresh_credentials_list(self):
        """Clears and repopulates the list widget from self.vault_manager.api_credentials."""
        self.credentials_list.clear()
        if self.vault_manager and hasattr(self.vault_manager, "api_credentials"):
            for key in sorted(self.vault_manager.api_credentials.keys()):
                self.credentials_list.addItem(key)

    def _export_credentials_to_backup(self):
        """Exports unencrypted versions of loaded credentials to the backup directory."""
        if not self.vault_manager:
            QMessageBox.warning(self, "Export Failed", "Vault manager is not available.")
            return

        if not hasattr(self.vault_manager, "api_credentials") or not self.vault_manager.api_credentials:
            QMessageBox.information(
                self,
                "Export Credentials",
                "No credentials loaded in current vault session.",
            )
            return

        backup_dir = ROOT_DIR / "backup"
        try:
            backup_dir.mkdir(parents=True, exist_ok=True)
            exported_files = []

            # 1. Export all loaded api_credentials from vault memory
            for key, val in self.vault_manager.api_credentials.items():
                dest_file = backup_dir / f"{key}.json"
                with open(dest_file, "w", encoding="utf-8") as f:
                    json.dump(val, f, indent=4)
                exported_files.append(dest_file.name)

            # 2. Also copy token.json if present in API_DIR
            token_src = Path(API_DIR) / "token.json"
            if token_src.exists():
                token_dst = backup_dir / "token.json"
                shutil.copy2(token_src, token_dst)
                if "token.json" not in exported_files:
                    exported_files.append("token.json")

            summary_msg = "Successfully exported the following credentials to backup directory:\n\n"
            summary_msg += "\n".join(f"  • {name}" for name in sorted(exported_files))
            summary_msg += f"\n\nPath: {backup_dir}"

            QMessageBox.information(self, "Export Success", summary_msg)
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", f"Failed to export credentials: {e}")

    def _import_credential(self):
        """Selects a new JSON credential file to encrypt and load into the vault."""
        if not self.vault_manager or not self.vault_manager.secret_key:
            QMessageBox.warning(self, "Import Failed", "Vault manager or security key is not available.")
            return

        # 1. Browse for JSON file
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import JSON Credential File", str(Path.home()), "JSON (*.json)"
        )
        if not file_path:
            return

        # 2. Read and validate JSON content
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                json_content = f.read()
            # Validate JSON
            api_data = json.loads(json_content)
        except Exception as e:
            QMessageBox.critical(self, "Import Error", f"Failed to read or parse JSON file: {e}")
            return

        # 3. Prompt user for alias/name
        default_alias = Path(file_path).stem
        alias, ok = QInputDialog.getText(
            self,
            "Credential Alias",
            "Enter a name/alias for this credential:",
            QLineEdit.EchoMode.Normal,
            default_alias,
        )
        if not ok or not alias.strip():
            return
        alias = alias.strip()

        # 4. Encrypt and save to API_DIR
        try:
            api_dir_path = Path(API_DIR)
            api_dir_path.mkdir(parents=True, exist_ok=True)
            enc_file_path = str(api_dir_path / f"{alias}.json.enc")
            raw_json_path = str(api_dir_path / f"{alias}.json")

            # Encrypt
            SecureJsonVault = self.vault_manager.SecureJsonVault
            secret_key = self.vault_manager.secret_key
            temp_file_vault = SecureJsonVault(secret_key, enc_file_path)
            temp_file_vault.saveData(json_content)

            # Copy raw json (matching app startup behavior where it auto-encrypts JSONs)
            with open(raw_json_path, "w", encoding="utf-8") as f:
                f.write(json_content)

            # 5. Load in-memory
            self.vault_manager.api_credentials[alias] = api_data
            self._refresh_credentials_list()

            QMessageBox.information(
                self,
                "Success",
                f"Credential '{alias}' imported and encrypted successfully.",
            )
        except Exception as e:
            QMessageBox.critical(self, "Import Failed", f"Failed to encrypt and save credential: {e}")

    def _edit_credential(self):
        """Opens a dialog to view, edit, and save the selected credential's JSON."""
        selected_items = self.credentials_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Edit Error", "Please select a credential from the list first.")
            return

        alias = selected_items[0].text()
        if not self.vault_manager or alias not in self.vault_manager.api_credentials:
            QMessageBox.warning(self, "Edit Error", f"Credential '{alias}' not found in memory.")
            return

        # Get current data
        current_data = self.vault_manager.api_credentials[alias]
        try:
            current_json_str = json.dumps(current_data, indent=4)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to serialize credential data: {e}")
            return

        # Create Dialog
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Edit Credential - {alias}")
        dialog.setMinimumSize(500, 400)

        layout = QVBoxLayout(dialog)

        info_label = QLabel(f"Editing JSON values for: <b>{alias}</b>")
        layout.addWidget(info_label)

        editor = QTextEdit()
        editor.setPlainText(current_json_str)
        editor.setStyleSheet("font-family: monospace;")
        layout.addWidget(editor)

        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        layout.addWidget(button_box)

        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_json_str = editor.toPlainText().strip()
            if not new_json_str:
                QMessageBox.warning(self, "Validation Error", "Credential JSON cannot be empty.")
                return

            try:
                new_data = json.loads(new_json_str)
            except json.JSONDecodeError as e:
                QMessageBox.critical(self, "JSON Error", f"Invalid JSON format. Changes not saved.\n{e}")
                return

            # Now save it back
            try:
                api_dir_path = Path(API_DIR)
                api_dir_path.mkdir(parents=True, exist_ok=True)
                enc_file_path = str(api_dir_path / f"{alias}.json.enc")
                raw_json_path = str(api_dir_path / f"{alias}.json")

                # Encrypt and save
                SecureJsonVault = self.vault_manager.SecureJsonVault
                secret_key = self.vault_manager.secret_key
                temp_file_vault = SecureJsonVault(secret_key, enc_file_path)
                temp_file_vault.saveData(new_json_str)

                # Write raw json matching import behavior
                with open(raw_json_path, "w", encoding="utf-8") as f:
                    f.write(new_json_str)

                # Update in memory
                self.vault_manager.api_credentials[alias] = new_data

                QMessageBox.information(
                    self,
                    "Success",
                    f"Credential '{alias}' updated and saved successfully.",
                )
            except Exception as e:
                QMessageBox.critical(self, "Save Error", f"Failed to save credential '{alias}': {e}")

    def _delete_credential(self):
        """Delete the selected credential from the vault and disk."""
        selected_items = self.credentials_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Delete Error", "Please select a credential from the list first.")
            return

        alias = selected_items[0].text()

        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete the credential '{alias}'?\n"
            "This will delete its encrypted (.json.enc) and unencrypted (.json) source files from the API directory.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            # 1. Delete files on disk
            enc_file_path = Path(API_DIR) / f"{alias}.json.enc"
            raw_json_path = Path(API_DIR) / f"{alias}.json"

            if enc_file_path.exists():
                enc_file_path.unlink()
            if raw_json_path.exists():
                raw_json_path.unlink()

            # 2. Remove from session memory
            if alias in self.vault_manager.api_credentials:  # pyrefly: ignore [missing-attribute]
                del self.vault_manager.api_credentials[alias]  # pyrefly: ignore [missing-attribute]

            # 3. Refresh list
            self._refresh_credentials_list()

            QMessageBox.information(self, "Success", f"Credential '{alias}' deleted successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Delete Failed", f"Failed to delete credential: {e}")

    def _browse_add_favourite(self):
        """Opens a directory dialog and adds the selected path to the favourites list."""
        dir_path = QFileDialog.getExistingDirectory(self, "Select Favourite Directory")
        if dir_path:
            dir_path = os.path.abspath(dir_path)
            items = [self.fav_list_widget.item(i).text() for i in range(self.fav_list_widget.count())]
            if dir_path not in items:
                self.fav_list_widget.addItem(dir_path)
            else:
                QMessageBox.information(self, "Already Exists", "This directory is already in your favourites.")

    def _remove_selected_favourite(self):
        """Removes the selected item from the favourites list widget."""
        selected_items = self.fav_list_widget.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Selection Required", "Please select a favourite directory to remove.")
            return
        for item in selected_items:
            self.fav_list_widget.takeItem(self.fav_list_widget.row(item))

    def _add_manual_favourite(self):
        """Validates and adds the manually typed path to the list widget."""
        path = self.fav_path_input.text().strip()
        if not path:
            QMessageBox.warning(self, "Path Required", "Please enter a directory path.")
            return

        abs_path = os.path.abspath(path)
        if not os.path.isdir(abs_path):
            QMessageBox.warning(self, "Invalid Directory", f"The directory does not exist:\n{abs_path}")
            return

        items = [self.fav_list_widget.item(i).text() for i in range(self.fav_list_widget.count())]
        if abs_path not in items:
            self.fav_list_widget.addItem(abs_path)
            self.fav_path_input.clear()
        else:
            QMessageBox.information(self, "Already Exists", "This directory is already in your favourites.")

    def _show_bulk_update_preview_dialog(self, changes: list) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Bulk Update Preview")
        dialog.setMinimumSize(600, 400)
        layout = QVBoxLayout(dialog)

        info_label = QLabel(f"The following {len(changes)} change(s) would be made:")
        info_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(info_label)

        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setPlainText("\n".join(changes))
        layout.addWidget(text_edit)

        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        btn_box.accepted.connect(dialog.accept)
        layout.addWidget(btn_box)

        dialog.exec()

    def _preview_bulk_update(self):
        search = self.bulk_search_input.text()
        replace = self.bulk_replace_input.text()
        use_regex = self.bulk_regex_check.isChecked()

        if not search:
            QMessageBox.warning(self, "Warning", "Please enter a search pattern.")
            return

        changes: list = []

        # 1. Preview Vault Data
        if self.bulk_target_vault.isChecked() and self.vault_manager:
            try:
                creds = self.vault_manager.load_account_credentials()
                dry_run_replace(search, replace, use_regex, changes, creds, "Vault")
            except Exception as e:
                changes.append(f"Error reading vault: {e}")

        # 2. Preview QSettings
        if self.bulk_target_qsettings.isChecked():
            for key in AppSettings.all_keys():
                val = AppSettings.get(key)
                if isinstance(val, (str, list, dict)):
                    dry_run_replace(search, replace, use_regex, changes, val, f"QSettings/{key}")

        if not changes:
            QMessageBox.information(self, "Preview", "No matching fields/values found to update.")
            return

        self._show_bulk_update_preview_dialog(changes)

    def _apply_bulk_update(self):
        search = self.bulk_search_input.text()
        replace = self.bulk_replace_input.text()
        use_regex = self.bulk_regex_check.isChecked()
        if not search:
            QMessageBox.warning(self, "Warning", "Please enter a search pattern.")
            return

        reply = QMessageBox.question(
            self,
            "Confirm Bulk Update",
            f"Are you sure you want to perform the bulk find & replace for pattern '{search}' with '{replace}'?\n\nThis will modify the settings and configurations.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        vault_count = 0
        qsettings_count = 0

        # 1. Update Vault
        if self.bulk_target_vault.isChecked() and self.vault_manager:
            try:
                creds = self.vault_manager.load_account_credentials()
                updated_creds, vault_count = recursive_replace(search, replace, use_regex, creds)
                if vault_count > 0 and not self._save_vault_data(updated_creds):
                    QMessageBox.critical(self, "Error", "Failed to save updated data back to secure vault.")
                    return
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to update secure vault: {e}")
                return

        # 2. Update QSettings
        if self.bulk_target_qsettings.isChecked():
            try:
                for key in AppSettings.all_keys():
                    val = AppSettings.get(key)
                    if isinstance(val, (str, list, dict)):
                        new_val, count = recursive_replace(search, replace, use_regex, val)
                        if count > 0:
                            AppSettings.set(key, new_val)
                            qsettings_count += count
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to update QSettings: {e}")
                return

        total_updates = vault_count + qsettings_count
        if total_updates > 0:
            QMessageBox.information(
                self,
                "Success",
                f"Bulk update completed successfully!\n\n"
                f"- Secure Vault fields updated: {vault_count}\n"
                f"- QSettings fields updated: {qsettings_count}\n\n"
                f"Settings window will now reload to display changes.",
            )
            # Trigger a reload in the UI to refresh loaded configs/values!
            self.reload_settings(show_msg=False)
        else:
            QMessageBox.information(self, "Information", "No matching fields/values were found to update.")


__all__ = ["_CredentialsMixin"]
