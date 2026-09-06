"""Regression: Ctrl+I (general.toggle_inspector) must go through the
shortcut registry like every other general.* binding in _lifecycle.py's
keyPressEvent, not a hardcoded key check alongside it.

Bug: #539's implementation added
``(event.key() == Qt.Key.Key_I and ... ControlModifier) or
get_registry().matches(event, "general.toggle_inspector")`` -- the
hardcoded half meant a user remapping general.toggle_inspector away from
Ctrl+I would still have Ctrl+I permanently wired in addition to their new
binding, unlike every sibling shortcut (general.global_search,
general.workflow_templates, general.save_tab_config,
general.load_tab_config), which rely solely on the registry.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from gui.src.utils.manager import shortcut_manager
from gui.src.windows.main.main_window import MainWindow
from gui.test.fixtures.mock_vault_manager import MockVaultManager, cleanup_recovery_files
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

pytestmark = pytest.mark.gui


@pytest.fixture(autouse=True)
def _isolated_keybindings(tmp_path, monkeypatch):
    monkeypatch.setattr(shortcut_manager, "_KEYBINDINGS_PATH", tmp_path / "keybindings.json")
    monkeypatch.setattr(shortcut_manager, "_registry", None)
    yield
    monkeypatch.setattr(shortcut_manager, "_registry", None)


class TestToggleInspectorShortcut:
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        cleanup_recovery_files()
        yield
        for widget in QApplication.topLevelWidgets():
            widget.close()
            widget.deleteLater()
        for _ in range(5):
            QApplication.processEvents()
        cleanup_recovery_files()

    def _make_window(self, q_app):
        creds = {"account_name": "test_user", "preferences": {}}
        vault = MockVaultManager(creds)
        window = MainWindow(vault_manager=vault)  # pyrefly: ignore [bad-argument-type]
        QApplication.processEvents()
        return window

    def test_default_ctrl_i_triggers_toggle(self, q_app):
        window = self._make_window(q_app)
        with patch.object(window, "_toggle_context_inspector") as mock_toggle:
            event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_I, Qt.KeyboardModifier.ControlModifier)
            window.keyPressEvent(event)
            mock_toggle.assert_called_once()

    def test_remapped_shortcut_no_longer_hardcoded_to_ctrl_i(self, q_app):
        """The core fix: once the user disables the default and assigns a
        different key, Ctrl+I must stop firing the toggle."""
        shortcut_manager.get_registry().save(
            {"general.toggle_inspector": {"default_enabled": False, "custom": ["Meta+I"]}}
        )
        window = self._make_window(q_app)

        with patch.object(window, "_toggle_context_inspector") as mock_toggle:
            ctrl_i = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_I, Qt.KeyboardModifier.ControlModifier)
            window.keyPressEvent(ctrl_i)
            mock_toggle.assert_not_called()

            meta_i = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_I, Qt.KeyboardModifier.MetaModifier)
            window.keyPressEvent(meta_i)
            mock_toggle.assert_called_once()
