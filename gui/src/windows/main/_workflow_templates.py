"""Ctrl+Shift+M workflow-template picker/builder (New Features §4.13, Option C).

A "workflow template" is an ordered list of (category, tab_name, config_name)
steps: applying a saved per-tab configuration (from the same
``tab_configurations`` vault store the Settings window's "Tab Default
Configuration Management" section already reads/writes) to each named tab in
turn, then switching to the tab named in the *last* step -- e.g. "set the
Convert tab to my HighRes preset, set Delete tab to its ConfirmAll preset,
then switch to Delete." No scripting/eval (Option B, explicitly skipped per
the roadmap's recommendation) -- this is state setup across multiple tabs in
one action, not operation-sequence playback.

New, not code motion.
"""

from __future__ import annotations

import json

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)


class _WorkflowTemplatesMixin:
    """Build, save, and run cross-tab workflow templates."""

    # ------------------------------------------------------------------
    # Vault I/O
    # ------------------------------------------------------------------
    def _load_workflow_templates(self) -> dict:
        if not self.vault_manager:
            return {}
        try:
            creds = self.vault_manager.load_account_credentials()
            return creds.get("workflow_templates", {})
        except Exception:
            return {}

    def _save_workflow_templates(self, templates: dict) -> bool:
        if not self.vault_manager:
            QMessageBox.critical(self, "Workflow Templates", "Vault manager is not available.")
            return False
        try:
            creds = self.vault_manager.load_account_credentials()
            creds["workflow_templates"] = templates
            self.vault_manager.save_data(json.dumps(creds))
            self.cached_creds = creds
            return True
        except Exception as e:
            QMessageBox.critical(self, "Workflow Templates", f"Failed to save workflow templates:\n{e}")
            return False

    # ------------------------------------------------------------------
    # Picker / run
    # ------------------------------------------------------------------
    def _open_workflow_templates_dialog(self) -> None:
        """Ctrl+Shift+M: list saved workflow templates with Run/New/Delete."""
        templates = self._load_workflow_templates()

        dlg = QDialog(self)
        dlg.setWindowTitle("Workflow Templates")
        dlg.setMinimumWidth(360)
        layout = QVBoxLayout(dlg)

        list_widget = QListWidget()
        for name in sorted(templates.keys()):
            list_widget.addItem(QListWidgetItem(name))
        layout.addWidget(list_widget)

        btn_row = QHBoxLayout()
        btn_run = QPushButton("▶ Run")
        btn_new = QPushButton("＋ New…")
        btn_delete = QPushButton("🗑 Delete")
        btn_row.addWidget(btn_run)
        btn_row.addWidget(btn_new)
        btn_row.addWidget(btn_delete)
        layout.addLayout(btn_row)

        def _run() -> None:
            item = list_widget.currentItem()
            if item is None:
                return
            name = item.text()
            dlg.accept()
            self._run_workflow_template(name)

        def _new() -> None:
            dlg.accept()
            self._open_workflow_template_builder()

        def _delete() -> None:
            item = list_widget.currentItem()
            if item is None:
                return
            name = item.text()
            fresh = self._load_workflow_templates()
            fresh.pop(name, None)
            if self._save_workflow_templates(fresh):
                list_widget.takeItem(list_widget.row(item))

        btn_run.clicked.connect(_run)
        btn_new.clicked.connect(_new)
        btn_delete.clicked.connect(_delete)
        list_widget.itemDoubleClicked.connect(lambda _item: _run())

        dlg.exec()

    def _run_workflow_template(self, name: str) -> None:
        templates = self._load_workflow_templates()
        steps = templates.get(name, {}).get("steps", [])
        if not steps:
            QMessageBox.warning(self, "Workflow Templates", f"Template '{name}' has no steps.")
            return

        creds = self.vault_manager.load_account_credentials() if self.vault_manager else {}
        tab_configurations = creds.get("tab_configurations", {})

        last_category, last_tab_name = None, None
        for step in steps:
            category = step.get("category")
            tab_name = step.get("tab_name")
            config_name = step.get("config_name")
            tab_instance = self.all_tabs.get(category, {}).get(tab_name)
            if tab_instance is None:
                continue
            if config_name and hasattr(tab_instance, "set_config"):
                config_data = tab_configurations.get(type(tab_instance).__name__, {}).get(config_name)
                if config_data is not None:
                    tab_instance.set_config(config_data)
            last_category, last_tab_name = category, tab_name

        if last_category and last_tab_name:
            self.command_combo.setCurrentText(last_category)
            QTimer.singleShot(0, lambda: self._select_tab_by_name(last_tab_name))

    # ------------------------------------------------------------------
    # Builder
    # ------------------------------------------------------------------
    def _open_workflow_template_builder(self) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle("New Workflow Template")
        dlg.setMinimumWidth(460)
        layout = QVBoxLayout(dlg)

        layout.addWidget(
            QLabel(
                "Add one or more steps. Each step optionally applies a saved\n"
                "configuration to a tab; the LAST step's tab is what the\n"
                "workflow switches to when it finishes running."
            )
        )

        step_row = QHBoxLayout()
        category_combo = QComboBox()
        category_combo.addItems(sorted(self.all_tabs.keys()))
        tab_combo = QComboBox()
        config_combo = QComboBox()
        step_row.addWidget(category_combo)
        step_row.addWidget(tab_combo)
        step_row.addWidget(config_combo)
        layout.addLayout(step_row)

        creds = self.vault_manager.load_account_credentials() if self.vault_manager else {}
        tab_configurations = creds.get("tab_configurations", {})

        def _refresh_tab_combo(category: str) -> None:
            tab_combo.blockSignals(True)
            tab_combo.clear()
            tab_combo.addItems(sorted(self.all_tabs.get(category, {}).keys()))
            tab_combo.blockSignals(False)
            _refresh_config_combo(tab_combo.currentText())

        def _refresh_config_combo(tab_name: str) -> None:
            config_combo.clear()
            config_combo.addItem("(no config — just switch here)")
            category = category_combo.currentText()
            tab_instance = self.all_tabs.get(category, {}).get(tab_name)
            if tab_instance is not None:
                class_name = type(tab_instance).__name__
                config_combo.addItems(sorted(tab_configurations.get(class_name, {}).keys()))

        category_combo.currentTextChanged.connect(_refresh_tab_combo)
        tab_combo.currentTextChanged.connect(_refresh_config_combo)
        _refresh_tab_combo(category_combo.currentText())

        add_btn = QPushButton("Add Step ↓")
        layout.addWidget(add_btn)

        steps_list = QListWidget()
        layout.addWidget(steps_list)
        steps: list[dict] = []

        def _add_step() -> None:
            category = category_combo.currentText()
            tab_name = tab_combo.currentText()
            config_choice = config_combo.currentText()
            if not category or not tab_name:
                return
            config_name = None if config_choice.startswith("(no config") else config_choice
            steps.append({"category": category, "tab_name": tab_name, "config_name": config_name})
            label = f"{tab_name} ({category})" + (f" → {config_name}" if config_name else "")
            steps_list.addItem(QListWidgetItem(label))

        def _remove_step() -> None:
            row = steps_list.currentRow()
            if row < 0:
                return
            steps_list.takeItem(row)
            steps.pop(row)

        add_btn.clicked.connect(_add_step)

        remove_btn = QPushButton("Remove Selected Step")
        remove_btn.clicked.connect(_remove_step)
        layout.addWidget(remove_btn)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        layout.addWidget(buttons)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        if not steps:
            QMessageBox.warning(self, "Workflow Templates", "No steps were added; template not saved.")
            return

        name, ok = QInputDialog.getText(self, "Save Workflow Template", "Template name:")
        name = name.strip()
        if not ok or not name:
            return

        templates = self._load_workflow_templates()
        templates[name] = {"steps": steps}
        self._save_workflow_templates(templates)


__all__ = ["_WorkflowTemplatesMixin"]
