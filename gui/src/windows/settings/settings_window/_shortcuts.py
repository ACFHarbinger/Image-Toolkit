"""Keyboard Shortcuts tab (GUI/UX §2.29).

Extracted from ``settings_window.py`` -- pure code motion, no logic change.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QKeySequenceEdit,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ....utils.shortcut_manager import SHORTCUT_REGISTRY, get_registry


class _ShortcutsMixin:
    """Builds and manages the Keyboard Shortcuts tab."""

    def _build_shortcuts_groupbox(self) -> QGroupBox:
        """Build the shortcuts table + action buttons groupbox."""
        grp = QGroupBox("Keyboard Shortcuts")
        grp.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        vbox = QVBoxLayout(grp)
        vbox.setContentsMargins(10, 10, 10, 10)

        # Info label
        info = QLabel(
            "Rebind any action by clicking its key cell. Changes take effect on next app launch "
            "(preview window shortcuts apply when a new preview is opened)."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #aaa; font-size: 10px;")
        vbox.addWidget(info)

        # Also show the user_theme.qss hint here as a bonus
        user_qss_path = str(Path.home() / ".image-toolkit" / "user_theme.qss")
        qss_hint = QLabel(
            f"<b>Custom QSS override (§2.31):</b> create <code>{user_qss_path}</code> "
            "to append your own QSS rules on top of the active theme."
        )
        qss_hint.setWordWrap(True)
        qss_hint.setStyleSheet("color: #aaa; font-size: 10px; margin-bottom: 6px;")
        vbox.addWidget(qss_hint)

        # Build table
        reg = get_registry()
        entries = reg.get_all()

        self._shortcut_table = QTableWidget(len(entries), 3)
        self._shortcut_table.setHorizontalHeaderLabels(["Scope", "Action", "Binding"])
        self._shortcut_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._shortcut_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._shortcut_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._shortcut_table.verticalHeader().setVisible(False)
        self._shortcut_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._shortcut_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self._shortcut_table.setAlternatingRowColors(True)

        self._shortcut_editors: dict[str, QKeySequenceEdit] = {}

        for row, entry in enumerate(entries):
            scope_item = QTableWidgetItem(entry["scope"])
            scope_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            desc_item = QTableWidgetItem(entry["description"])
            desc_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self._shortcut_table.setItem(row, 0, scope_item)
            self._shortcut_table.setItem(row, 1, desc_item)

            editor = QKeySequenceEdit(QKeySequence(entry["current"]))
            editor.setToolTip(f"Default: {entry['default']}")
            self._shortcut_editors[entry["id"]] = editor
            self._shortcut_table.setCellWidget(row, 2, editor)

        vbox.addWidget(self._shortcut_table)

        # Buttons row
        btn_row = QHBoxLayout()
        btn_save_kb = QPushButton("Save Shortcuts")
        btn_save_kb.setToolTip("Write shortcut overrides to ~/.image-toolkit/keybindings.json")
        btn_save_kb.clicked.connect(self._save_shortcuts)
        btn_reset_kb = QPushButton("Reset All to Defaults")
        btn_reset_kb.setToolTip("Clear all overrides and delete keybindings.json")
        btn_reset_kb.clicked.connect(self._reset_shortcuts)
        btn_row.addWidget(btn_save_kb)
        btn_row.addWidget(btn_reset_kb)
        btn_row.addStretch()
        vbox.addLayout(btn_row)
        return grp

    def _save_shortcuts(self) -> None:
        reg = get_registry()
        defaults = {e["id"]: e["default"] for e in SHORTCUT_REGISTRY}
        overrides: dict[str, str] = {}
        conflicts: list[str] = []
        for action_id, editor in self._shortcut_editors.items():
            seq = editor.keySequence()
            key_str = seq.toString() if not seq.isEmpty() else ""
            if key_str and key_str != defaults.get(action_id, ""):
                # Conflict detection: same binding as another action
                for other_id, other_editor in self._shortcut_editors.items():
                    if other_id == action_id:
                        continue
                    if other_editor.keySequence().toString() == key_str:
                        conflicts.append(f"{action_id} ↔ {other_id} (both: {key_str})")
            if key_str:
                overrides[action_id] = key_str

        if conflicts:
            msg = "Conflicting shortcuts detected:\n" + "\n".join(conflicts)
            msg += "\n\nSave anyway?"
            reply = QMessageBox.question(
                self,
                "Shortcut Conflict",
                msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        reg.save(overrides)
        QMessageBox.information(self, "Saved", "Shortcuts saved. Changes take effect on next app launch.")

    def _reset_shortcuts(self) -> None:
        reply = QMessageBox.question(
            self,
            "Reset Shortcuts",
            "Reset all shortcuts to defaults and delete keybindings.json?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        get_registry().reset()
        defaults = {e["id"]: e["default"] for e in SHORTCUT_REGISTRY}
        for action_id, editor in self._shortcut_editors.items():
            editor.setKeySequence(QKeySequence(defaults.get(action_id, "")))
        QMessageBox.information(self, "Reset", "All shortcuts reset to defaults.")


__all__ = ["_ShortcutsMixin"]
