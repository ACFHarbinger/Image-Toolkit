"""Ctrl+S save-current-tab-configuration dialog (GUI/UX §2.29,
``general.save_tab_config`` in shortcut_manager.py).

Extracted as its own mixin -- new feature, not code motion.
"""

from __future__ import annotations

import json

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QLineEdit, QMessageBox, QVBoxLayout


class _SaveTabConfigMixin:
    """Ctrl+S: capture the active tab's current config and save it as a named profile."""

    def _open_save_tab_config_dialog(self) -> None:
        active_category = self.command_combo.currentText()
        active_tab_index = self.tabs.currentIndex()
        active_tab_name = self.tabs.tabText(active_tab_index) if active_tab_index >= 0 else None

        if not active_category or not active_tab_name:
            QMessageBox.warning(self, "Save Configuration", "No active tab to save a configuration for.")
            return

        tab_instance = self.all_tabs.get(active_category, {}).get(active_tab_name)
        if tab_instance is None or not hasattr(tab_instance, "collect") or not callable(tab_instance.collect):
            QMessageBox.warning(
                self,
                "Save Configuration",
                f"'{active_tab_name}' does not support saving a configuration.",
            )
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("Save Tab Configuration")
        dlg.setMinimumWidth(360)
        layout = QVBoxLayout(dlg)
        layout.addWidget(QLabel(f"Save the current configuration of '{active_tab_name}' as:"))

        name_input = QLineEdit()
        name_input.setPlaceholderText("Configuration name...")
        layout.addWidget(name_input)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        layout.addWidget(buttons)

        name_input.returnPressed.connect(dlg.accept)
        name_input.setFocus()

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        config_name = name_input.text().strip()
        if not config_name:
            QMessageBox.warning(self, "Save Configuration", "Please enter a configuration name.")
            return

        self._save_tab_config_to_vault(tab_instance, config_name)

    def _save_tab_config_to_vault(self, tab_instance, config_name: str) -> None:
        """Captures *tab_instance*'s current config via .collect() and saves
        it into the vault's tab_configurations store -- the same store the
        Settings window's "Tab Default Configuration Management" section
        (settings_window/_tab_config_management.py) reads from/writes to,
        so a config saved here immediately shows up there too."""
        if not self.vault_manager:
            QMessageBox.critical(self, "Save Configuration", "Vault manager is not available.")
            return

        try:
            config_data = tab_instance.collect()
            tab_class_name = type(tab_instance).__name__

            creds = self.vault_manager.load_account_credentials()
            tab_configurations = creds.get("tab_configurations", {})
            tab_configurations.setdefault(tab_class_name, {})[config_name] = config_data
            creds["tab_configurations"] = tab_configurations

            self.vault_manager.save_data(json.dumps(creds))
            self.cached_creds = creds

            QMessageBox.information(
                self,
                "Save Configuration",
                f"Configuration '{config_name}' saved for {tab_class_name}.",
            )
        except Exception as e:
            QMessageBox.critical(self, "Save Configuration", f"Failed to save configuration:\n{e}")


__all__ = ["_SaveTabConfigMixin"]
