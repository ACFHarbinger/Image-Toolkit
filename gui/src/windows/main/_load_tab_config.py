"""Meta+S load-a-saved-configuration-into-the-current-tab dialog
(``general.load_tab_config`` in shortcut_manager.py).

Reads from the same ``tab_configurations`` vault store that
``_save_tab_config.py`` (Ctrl+S) writes to and the Settings window's "Tab
Default Configuration Management" section manages -- this is the missing
"quick load" counterpart to Ctrl+S's "quick save."

New feature, not code motion.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QVBoxLayout,
)


class _LoadTabConfigMixin:
    """Meta+S: pick a saved configuration for the active tab and apply it."""

    def _open_load_tab_config_dialog(self) -> None:
        active_category = self.command_combo.currentText()
        active_tab_index = self.tabs.currentIndex()
        active_tab_name = self.tabs.tabText(active_tab_index) if active_tab_index >= 0 else None

        if not active_category or not active_tab_name:
            QMessageBox.warning(self, "Load Configuration", "No active tab to load a configuration for.")
            return

        tab_instance = self.all_tabs.get(active_category, {}).get(active_tab_name)
        if tab_instance is None or not hasattr(tab_instance, "set_config") or not callable(tab_instance.set_config):
            QMessageBox.warning(
                self,
                "Load Configuration",
                f"'{active_tab_name}' does not support loading a configuration.",
            )
            return

        if not self.vault_manager:
            QMessageBox.critical(self, "Load Configuration", "Vault manager is not available.")
            return

        tab_class_name = type(tab_instance).__name__
        try:
            creds = self.vault_manager.load_account_credentials()
        except Exception as e:
            QMessageBox.critical(self, "Load Configuration", f"Failed to read saved configurations:\n{e}")
            return

        saved_configs = creds.get("tab_configurations", {}).get(tab_class_name, {})
        if not saved_configs:
            QMessageBox.information(
                self,
                "Load Configuration",
                f"No saved configurations found for '{active_tab_name}'.",
            )
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("Load Tab Configuration")
        dlg.setMinimumWidth(360)
        layout = QVBoxLayout(dlg)
        layout.addWidget(QLabel(f"Select a saved configuration to load into '{active_tab_name}':"))

        list_widget = QListWidget()
        for name in sorted(saved_configs.keys()):
            list_widget.addItem(QListWidgetItem(name))
        list_widget.setCurrentRow(0)
        layout.addWidget(list_widget)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        layout.addWidget(buttons)

        list_widget.itemDoubleClicked.connect(lambda _item: dlg.accept())

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        item = list_widget.currentItem()
        if item is None:
            return

        self._load_tab_config_into(tab_instance, saved_configs[item.text()], item.text())

    def _load_tab_config_into(self, tab_instance, config_data: dict, config_name: str) -> None:
        try:
            tab_instance.set_config(config_data)
        except Exception as e:
            QMessageBox.critical(self, "Load Configuration", f"Failed to apply configuration '{config_name}':\n{e}")
            return

        if hasattr(self, "show_status"):
            self.show_status(f"Loaded configuration '{config_name}'.")


__all__ = ["_LoadTabConfigMixin"]
