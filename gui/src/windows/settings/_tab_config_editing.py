"""Tab default configuration editing methods (populate/load/save/export/import/set).

Extracted from ``settings_window.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

import contextlib
import json
from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QMessageBox


class _TabConfigEditingMixin:
    """Owns the config-editor CRUD methods used by the Tab Default Configuration section."""

    def _populate_default_config(self, tab_display_name: str):
        """Populates the text editor with the default config from the selected tab display name."""
        self.config_name_input.clear()  # Clear config name
        tab_instance = self._get_tab_instance_by_display_name(tab_display_name)

        if tab_instance and hasattr(tab_instance, "get_default_config"):
            try:
                default_config = tab_instance.get_default_config()
                default_json = json.dumps(default_config, indent=4)
                self.default_config_editor.setText(default_json)
                self.default_config_editor.setPlaceholderText(
                    "Edit the default config below or create a new named config..."
                )
            except Exception as e:
                self.default_config_editor.clear()
                self.default_config_editor.setPlaceholderText(f"Error loading default config: {e}")
        else:
            self.default_config_editor.clear()
            self.default_config_editor.setPlaceholderText("This tab does not have a 'get_default_config' method.")

    def _refresh_config_dropdown(self, tab_display_name: str):
        """
        Populates the config dropdown based on the selected tab display name AND
        populates the editor with the default config for that tab.
        """

        with contextlib.suppress(RuntimeError):
            self.config_select_combo.currentTextChanged.disconnect(self._load_selected_tab_config)

        self.config_select_combo.clear()
        self.current_loaded_config_name = None

        if not tab_display_name:
            self.config_select_combo.setPlaceholderText("Select a Tab first.")
            self.config_name_input.clear()
            self.default_config_editor.clear()
            self.default_config_editor.setPlaceholderText("Select a Tab to see its default configuration...")
        else:
            # Get class name for config lookup
            instance = self._get_tab_instance_by_display_name(tab_display_name)
            tab_class_name = type(instance).__name__ if instance else ""

            # Populate the editor with the default config FIRST
            self._populate_default_config(tab_display_name)

            # Now, populate the dropdown with saved configs for this tab class
            configs = self.tab_defaults_config.get(tab_class_name, {})
            config_names = sorted(configs.keys())

            self.config_select_combo.addItems([""] + config_names)
            self.config_select_combo.setPlaceholderText("Load/Edit Existing Config...")

        # Reconnect the signal
        self.config_select_combo.currentTextChanged.connect(self._load_selected_tab_config)

    def _load_selected_tab_config(self, config_name: str):
        """
        Loads a selected configuration's JSON into the editor.
        If config_name is empty, it re-loads the default config.
        """
        tab_display_name = self.tab_select_combo.currentText()

        if not tab_display_name:
            self.config_name_input.clear()
            self.default_config_editor.clear()
            self.current_loaded_config_name = None
            return

        instance = self._get_tab_instance_by_display_name(tab_display_name)
        tab_class_name = type(instance).__name__ if instance else ""

        if not config_name:
            # User selected the blank placeholder, so load the default config
            self._populate_default_config(tab_display_name)
            self.current_loaded_config_name = None
            return

        # User selected a specific, saved config
        configs = self.tab_defaults_config.get(tab_class_name, {})
        config = configs.get(config_name, {})

        try:
            json_str = json.dumps(config, indent=4)
            self.default_config_editor.setText(json_str)
            self.config_name_input.setText(config_name)
            self.current_loaded_config_name = config_name
        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"Failed to load config '{config_name}': {e}")
            # On error, fall back to default
            self._populate_default_config(tab_display_name)
            self.current_loaded_config_name = None

    def _save_current_tab_config(self):
        """Parses the editor content and saves it as a new or updated named configuration."""
        tab_display_name = self.tab_select_combo.currentText()
        config_name = self.config_name_input.text().strip()
        json_text = self.default_config_editor.toPlainText().strip()

        if not tab_display_name or not config_name:
            QMessageBox.warning(
                self,
                "Input Error",
                "Please select a Tab and provide a Config Name.",
            )
            return

        instance = self._get_tab_instance_by_display_name(tab_display_name)
        tab_class_name = type(instance).__name__ if instance else ""

        if not json_text:
            QMessageBox.warning(self, "Input Error", "Configuration JSON cannot be empty.")
            return

        try:
            new_config = json.loads(json_text)
            if not isinstance(new_config, dict):
                raise ValueError("Configuration must be a valid JSON object.")

            if tab_class_name not in self.tab_defaults_config:
                self.tab_defaults_config[tab_class_name] = {}

            self.tab_defaults_config[tab_class_name][config_name] = new_config

            if self._save_tab_defaults_to_vault():
                QMessageBox.information(
                    self,
                    "Success",
                    f"Configuration '{config_name}' saved for {tab_display_name}.",
                )

                self._refresh_config_dropdown(tab_display_name)
                self.config_select_combo.setCurrentText(config_name)

        except json.JSONDecodeError as e:
            QMessageBox.critical(self, "JSON Error", f"Invalid JSON format:\n{e}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An unexpected error occurred during save: {e}")

    def _export_selected_tab_config(self):
        """Exports the configuration currently in the editor to a .json file.

        The file wraps the config with its tab class and name so importing on
        another machine can route it back to the right tab automatically.
        """
        tab_display_name = self.tab_select_combo.currentText()
        if not tab_display_name:
            QMessageBox.warning(self, "Export Error", "Please select a Tab first.")
            return

        config_name = (
            self.config_name_input.text().strip() or self.config_select_combo.currentText().strip() or "unnamed"
        )
        json_text = self.default_config_editor.toPlainText().strip()
        if not json_text:
            QMessageBox.warning(self, "Export Error", "There is no configuration JSON to export.")
            return
        try:
            config = json.loads(json_text)
            if not isinstance(config, dict):
                raise ValueError("Configuration must be a JSON object.")
        except (json.JSONDecodeError, ValueError) as e:
            QMessageBox.critical(self, "Export Error", f"The editor does not contain valid JSON:\n{e}")
            return

        instance = self._get_tab_instance_by_display_name(tab_display_name)
        tab_class_name = type(instance).__name__ if instance else tab_display_name

        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in config_name)
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Tab Configuration",
            str(Path.home() / f"{tab_class_name}_{safe_name}.json"),
            "JSON (*.json)",
        )
        if not file_path:
            return
        if not file_path.lower().endswith(".json"):
            file_path += ".json"

        payload = {
            "image_toolkit_tab_config": 1,
            "tab_class": tab_class_name,
            "tab_display_name": tab_display_name,
            "config_name": config_name,
            "config": config,
        }
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=4, ensure_ascii=False)
            QMessageBox.information(
                self,
                "Export Success",
                f"Configuration '{config_name}' for {tab_display_name} exported to:\n{file_path}",
            )
        except OSError as e:
            QMessageBox.critical(self, "Export Failed", f"Failed to write the file:\n{e}")

    def _import_tab_config_from_json(self):
        """Imports a configuration from a .json file and saves it to the vault.

        Accepts both the wrapped export format (which carries its own tab
        class and config name) and a plain config object (routed to the
        currently selected tab, named after the file).
        """
        file_path, _ = QFileDialog.getOpenFileName(self, "Import Tab Configuration", str(Path.home()), "JSON (*.json)")
        if not file_path:
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("The file must contain a JSON object.")
        except (OSError, json.JSONDecodeError, ValueError) as e:
            QMessageBox.critical(self, "Import Error", f"Failed to read or parse the JSON file:\n{e}")
            return

        if "image_toolkit_tab_config" in data:
            # Wrapped export format — self-describing.
            tab_class_name = str(data.get("tab_class", "")).strip()
            config_name = str(data.get("config_name", "")).strip() or Path(file_path).stem
            config = data.get("config")
            if not tab_class_name or not isinstance(config, dict):
                QMessageBox.critical(
                    self,
                    "Import Error",
                    "The file is missing its 'tab_class' or 'config' fields.",
                )
                return
            if tab_class_name not in self._get_all_tab_names_uncategorized():
                QMessageBox.critical(
                    self,
                    "Import Error",
                    f"The file targets unknown tab class '{tab_class_name}'.",
                )
                return
        else:
            # Plain config object — route to the currently selected tab.
            tab_display_name = self.tab_select_combo.currentText()
            if not tab_display_name:
                QMessageBox.warning(
                    self,
                    "Import Error",
                    "This file is a plain configuration object. Select the target Tab first, then import again.",
                )
                return
            instance = self._get_tab_instance_by_display_name(tab_display_name)
            tab_class_name = type(instance).__name__ if instance else ""
            config_name = Path(file_path).stem
            config = data

        # Confirm overwrite of an existing config with the same name.
        existing = self.tab_defaults_config.get(tab_class_name, {})
        if config_name in existing:
            reply = QMessageBox.question(
                self,
                "Overwrite Config?",
                f"A configuration named '{config_name}' already exists for {tab_class_name}. Overwrite it?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        self.tab_defaults_config.setdefault(tab_class_name, {})[config_name] = config
        if not self._save_tab_defaults_to_vault():
            return

        QMessageBox.information(
            self,
            "Import Success",
            f"Configuration '{config_name}' imported for {tab_class_name}.",
        )
        # If the imported tab is the one on screen, refresh and select it.
        current_display = self.tab_select_combo.currentText()
        current_instance = self._get_tab_instance_by_display_name(current_display)
        if current_instance and type(current_instance).__name__ == tab_class_name:
            self._refresh_config_dropdown(current_display)
            self.config_select_combo.setCurrentText(config_name)

    def _capture_and_save_current_config(self):
        """
        Captures the current values from the active tab instance,
        populates the JSON editor, and triggers the save workflow.
        """
        tab_display_name = self.tab_select_combo.currentText()
        if not tab_display_name:
            QMessageBox.warning(self, "Error", "Please select a Tab first.")
            return

        tab_instance = self._get_tab_instance_by_display_name(tab_display_name)
        if not tab_instance:
            QMessageBox.warning(self, "Error", "Could not find active tab instance to capture from.")
            return

        if not hasattr(tab_instance, "collect"):
            QMessageBox.warning(
                self,
                "Error",
                f"The tab '{tab_display_name}' does not support capturing current configuration (missing 'collect' method).",
            )
            return

        try:
            # Capture data from the live tab
            config_data = tab_instance.collect()

            # Populate editor
            json_str = json.dumps(config_data, indent=4)
            self.default_config_editor.setText(json_str)

            # If the user has already entered a name, we can try to save immediately.
            # If not, _save_current_tab_config will show the validation warning.
            self._save_current_tab_config()

        except Exception as e:
            QMessageBox.critical(self, "Capture Error", f"Failed to capture configuration: {e}")

    def _delete_selected_tab_config(self):
        """Deletes the currently selected configuration from the in-memory state and the vault."""
        tab_display_name = self.tab_select_combo.currentText()
        config_name = self.config_select_combo.currentText()

        if not tab_display_name or not config_name:
            QMessageBox.warning(
                self,
                "Delete Error",
                "Please select a tab and a configuration to delete.",
            )
            return

        instance = self._get_tab_instance_by_display_name(tab_display_name)
        tab_class_name = type(instance).__name__ if instance else ""

        reply = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Are you sure you want to PERMANENTLY delete the configuration '{config_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                if (
                    tab_class_name in self.tab_defaults_config
                    and config_name in self.tab_defaults_config[tab_class_name]
                ):
                    del self.tab_defaults_config[tab_class_name][config_name]

                    if not self.tab_defaults_config[tab_class_name]:
                        del self.tab_defaults_config[tab_class_name]

                    if self._save_tab_defaults_to_vault():
                        QMessageBox.information(self, "Success", f"Configuration '{config_name}' deleted.")
                        self.config_name_input.clear()
                        self.default_config_editor.clear()
                        self._refresh_config_dropdown(tab_display_name)

            except Exception as e:
                QMessageBox.critical(self, "Delete Error", f"Failed to delete configuration: {e}")

    def _set_selected_tab_config(self):
        """
        Applies the configuration currently loaded in the editor to the active
        instance of the selected tab in the MainWindow.
        """
        tab_display_name = self.tab_select_combo.currentText()
        config_name = self.config_name_input.text().strip()
        json_text = self.default_config_editor.toPlainText().strip()

        if not tab_display_name or not (config_name or json_text):
            QMessageBox.warning(
                self,
                "Set Error",
                "Please select a tab and ensure config JSON is loaded.",
            )
            return

        try:
            config_data = json.loads(json_text)

            target_tab_instance = self._get_tab_instance_by_display_name(tab_display_name)

            if not target_tab_instance:
                QMessageBox.critical(
                    self,
                    "Set Error",
                    f"Could not find active instance of tab: {tab_display_name}.",
                )
                return

            tab_class_name = type(target_tab_instance).__name__

            if hasattr(target_tab_instance, "set_config") and callable(target_tab_instance.set_config):
                target_tab_instance.set_config(config_data)

                config_display_name = f"'{config_name}'" if config_name else "'(Default)'"
                QMessageBox.information(
                    self,
                    "Success",
                    f"Configuration {config_display_name} applied to {tab_display_name}.",
                )
            else:
                QMessageBox.critical(
                    self,
                    "Set Error",
                    f"Target tab '{tab_display_name}' ({tab_class_name}) does not have a 'set_config' method.",
                )

        except json.JSONDecodeError as e:
            QMessageBox.critical(
                self,
                "JSON Error",
                f"Invalid JSON in editor. Cannot apply configuration:\n{e}",
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"An unexpected error occurred during configuration application: {e}",
            )


__all__ = ["_TabConfigEditingMixin"]
