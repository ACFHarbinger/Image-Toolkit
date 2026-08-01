"""Keyboard Shortcuts tab (GUI/UX §2.29), KDE System Settings-style layout.

Left: a list of "functionalities" (shortcut scopes -- Gallery, Preview,
General, ...), each with an icon, mirroring KDE's Shortcuts module where you
select an application/service before editing its bindings. Right: every
action belonging to the selected scope, each showing its default shortcut
(togglable) plus any number of custom shortcuts, with an "+ Add..." button --
mirroring KDE's per-action "Default shortcut" / "Custom shortcuts" columns.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QKeySequenceEdit,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ...utils.manager.shortcut_manager import SHORTCUT_REGISTRY, get_registry

# Icons shown next to each functionality/scope in the left-hand list --
# same emoji-prefix idiom already used for the settings window's own tab
# titles (see manager.py), rather than bundling separate icon assets.
_SCOPE_ICONS = {
    "General": "🖥️",
    "Gallery": "🖼️",
    "Preview": "🔍",
}
_DEFAULT_SCOPE_ICON = "🔧"


class _ShortcutsMixin:
    """Builds and manages the Keyboard Shortcuts tab."""

    def _build_shortcuts_groupbox(self) -> QGroupBox:
        """Build the shortcuts scope-list + per-scope action editor + action buttons."""
        grp = QGroupBox("Keyboard Shortcuts")
        grp.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        # "Far more height" -- fill the whole tab instead of shrinking to
        # content, matching a KDE Shortcuts-module-sized editor rather than
        # a short embedded table.
        grp.setMinimumHeight(560)
        vbox = QVBoxLayout(grp)
        vbox.setContentsMargins(10, 10, 10, 10)

        info = QLabel(
            "Select a functionality on the left, then toggle its default shortcut or add/remove "
            "custom shortcuts on the right. Changes take effect on next app launch (preview window "
            "shortcuts apply when a new preview is opened)."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #aaa; font-size: 10px;")
        vbox.addWidget(info)

        user_qss_path = str(Path.home() / ".image-toolkit" / "user_theme.qss")
        qss_hint = QLabel(
            f"<b>Custom QSS override (§2.31):</b> create <code>{user_qss_path}</code> "
            "to append your own QSS rules on top of the active theme."
        )
        qss_hint.setWordWrap(True)
        qss_hint.setStyleSheet("color: #aaa; font-size: 10px; margin-bottom: 6px;")
        vbox.addWidget(qss_hint)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        reg = get_registry()
        scopes = sorted({e["scope"] for e in SHORTCUT_REGISTRY})

        # --- Left: functionality (scope) list, KDE "Applications/Services" style ---
        self._shortcut_scope_list = QListWidget()
        self._shortcut_scope_list.setMinimumWidth(190)
        self._shortcut_scope_list.setMaximumWidth(260)
        for scope in scopes:
            icon = _SCOPE_ICONS.get(scope, _DEFAULT_SCOPE_ICON)
            item = QListWidgetItem(f"{icon}  {scope}")
            item.setData(Qt.ItemDataRole.UserRole, scope)
            self._shortcut_scope_list.addItem(item)
        splitter.addWidget(self._shortcut_scope_list)

        # --- Right: one page per scope, kept alive in a QStackedWidget so
        # switching scopes never discards unsaved edits on another page ---
        self._shortcut_stack = QStackedWidget()
        self._shortcut_row_widgets: dict[str, dict] = {}
        self._shortcut_scope_pages: dict[str, int] = {}
        for scope in scopes:
            page = self._build_shortcut_scope_page(scope, reg)
            self._shortcut_scope_pages[scope] = self._shortcut_stack.addWidget(page)
        splitter.addWidget(self._shortcut_stack)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        vbox.addWidget(splitter, 1)

        self._shortcut_scope_list.currentItemChanged.connect(self._on_shortcut_scope_changed)
        if self._shortcut_scope_list.count():
            self._shortcut_scope_list.setCurrentRow(0)

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

    def _on_shortcut_scope_changed(self, current: QListWidgetItem, _previous: QListWidgetItem) -> None:
        if current is None:
            return
        scope = current.data(Qt.ItemDataRole.UserRole)
        self._shortcut_stack.setCurrentIndex(self._shortcut_scope_pages[scope])

    def _build_shortcut_scope_page(self, scope: str, reg) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.setSpacing(12)

        entries = [e for e in SHORTCUT_REGISTRY if e["scope"] == scope]
        for entry in entries:
            layout.addWidget(self._build_shortcut_action_row(entry, reg))

        scroll.setWidget(container)
        return scroll

    def _build_shortcut_action_row(self, entry: dict, reg) -> QGroupBox:
        """One action's editor: default-shortcut toggle + custom-shortcut pills."""
        action_id = entry["id"]
        box = QGroupBox(entry["description"])

        v = QVBoxLayout(box)

        # --- Default shortcut row ---
        default_row = QHBoxLayout()
        default_row.addWidget(QLabel("Default shortcut:"))
        default_check = QCheckBox()
        default_check.setChecked(reg.is_default_enabled(action_id))
        default_row.addWidget(default_check)
        default_label = QLabel(f"<b>{entry['default']}</b>" if entry["default"] else "<i>(none)</i>")
        default_row.addWidget(default_label)
        default_row.addStretch()
        v.addLayout(default_row)

        # --- Custom shortcuts row ---
        v.addWidget(QLabel("Custom shortcuts:"))
        custom_row_widget = QWidget()
        custom_flow = QHBoxLayout(custom_row_widget)
        custom_flow.setContentsMargins(0, 0, 0, 0)
        custom_flow.setSpacing(6)
        v.addWidget(custom_row_widget)

        add_btn = QPushButton("+ Add...")
        add_btn.setToolTip("Capture a new custom shortcut for this action")
        add_btn.clicked.connect(lambda: self._add_custom_shortcut(action_id))
        custom_flow.addWidget(add_btn)
        custom_flow.addStretch()

        self._shortcut_row_widgets[action_id] = {
            "default_check": default_check,
            "custom_flow": custom_flow,
            "add_btn": add_btn,
        }

        for key_str in reg.get_custom_keys(action_id):
            self._add_custom_shortcut_pill(action_id, key_str)

        return box

    def _add_custom_shortcut_pill(self, action_id: str, key_str: str) -> None:
        """Insert one "key text + delete button" pill into action_id's custom row."""
        widgets = self._shortcut_row_widgets[action_id]
        flow = widgets["custom_flow"]

        pill = QWidget()
        pill.setProperty("shortcut_key", key_str)
        pill_layout = QHBoxLayout(pill)
        pill_layout.setContentsMargins(0, 0, 0, 0)
        pill_layout.setSpacing(2)

        chip = QPushButton(key_str)
        chip.setEnabled(False)
        chip.setStyleSheet(
            "QPushButton { padding: 3px 10px; border-radius: 9px; background: #3e3e42; color: white; }"
            "QPushButton:disabled { color: white; }"
        )
        del_btn = QPushButton("🗑")
        del_btn.setFixedWidth(26)
        del_btn.setToolTip("Remove this custom shortcut")

        def _remove_pill() -> None:
            # setParent(None) detaches it from the layout immediately (unlike
            # deleteLater() alone, which only schedules destruction for the
            # next event loop iteration -- callers reading the layout's
            # contents right after a removal, e.g. _collect_shortcut_custom_keys(),
            # would otherwise still see it).
            flow.removeWidget(pill)
            pill.setParent(None)
            pill.deleteLater()

        del_btn.clicked.connect(_remove_pill)

        pill_layout.addWidget(chip)
        pill_layout.addWidget(del_btn)

        insert_index = flow.indexOf(widgets["add_btn"])
        flow.insertWidget(insert_index, pill)

    def _add_custom_shortcut(self, action_id: str) -> None:
        dlg = QDialog(self)
        dlg.setWindowTitle("Add Custom Shortcut")
        dlg.setMinimumWidth(320)
        layout = QVBoxLayout(dlg)
        layout.addWidget(QLabel("Press the new key combination:"))
        editor = QKeySequenceEdit()
        layout.addWidget(editor)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        layout.addWidget(buttons)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        seq = editor.keySequence()
        key_str = seq.toString()
        if not key_str:
            return

        existing = self._collect_shortcut_custom_keys(action_id)
        if key_str in existing:
            QMessageBox.information(self, "Duplicate Shortcut", f"'{key_str}' is already a custom shortcut for this action.")
            return

        self._add_custom_shortcut_pill(action_id, key_str)

    def _collect_shortcut_custom_keys(self, action_id: str) -> list[str]:
        widgets = self._shortcut_row_widgets[action_id]
        flow = widgets["custom_flow"]
        keys = []
        for i in range(flow.count()):
            item = flow.itemAt(i)
            w = item.widget() if item else None
            key = w.property("shortcut_key") if w is not None else None
            if key:
                keys.append(key)
        return keys

    def _save_shortcuts(self) -> None:
        reg = get_registry()
        new_state: dict[str, dict] = {}
        # Keyed by (scope, key_str) -- scopes are independent widget/window
        # contexts (Gallery vs. Preview vs. General), each with its own
        # keyPressEvent handler querying only its own scope's bindings, so
        # the same key string reused across two different scopes (e.g.
        # Gallery's "Left"/"Right" nav vs. Preview's "Left"/"Right" nav) is
        # never actually ambiguous at runtime and must not be flagged.
        active_keys: dict[tuple[str, str], list[str]] = {}

        for entry in SHORTCUT_REGISTRY:
            action_id = entry["id"]
            widgets = self._shortcut_row_widgets.get(action_id)
            if not widgets:
                continue
            default_enabled = widgets["default_check"].isChecked()
            custom_keys = self._collect_shortcut_custom_keys(action_id)
            new_state[action_id] = {"default_enabled": default_enabled, "custom": custom_keys}

            keys = list(custom_keys)
            if default_enabled and entry["default"]:
                keys.insert(0, entry["default"])
            active_keys[(entry["scope"], action_id)] = keys

        # Conflict detection: any key string bound to more than one action
        # WITHIN THE SAME SCOPE.
        key_to_actions: dict[tuple[str, str], list[str]] = {}
        for (scope, action_id), keys in active_keys.items():
            for key_str in keys:
                key_to_actions.setdefault((scope, key_str), []).append(action_id)
        conflicts = [
            f"{scope}: {key_str}: {' ↔ '.join(actions)}"
            for (scope, key_str), actions in key_to_actions.items()
            if len(actions) > 1
        ]

        if conflicts:
            msg = "Conflicting shortcuts detected:\n" + "\n".join(conflicts) + "\n\nSave anyway?"
            reply = QMessageBox.question(
                self,
                "Shortcut Conflict",
                msg,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        reg.save(new_state)
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
        for action_id, widgets in self._shortcut_row_widgets.items():
            widgets["default_check"].setChecked(True)
            flow = widgets["custom_flow"]
            for i in reversed(range(flow.count())):
                item = flow.itemAt(i)
                w = item.widget() if item else None
                if w is not None and w.property("shortcut_key") is not None:
                    # See _add_custom_shortcut_pill()'s _remove_pill(): detach
                    # immediately, don't rely on deleteLater() alone.
                    flow.removeWidget(w)
                    w.setParent(None)
                    w.deleteLater()
        QMessageBox.information(self, "Reset", "All shortcuts reset to defaults.")


__all__ = ["_ShortcutsMixin"]
