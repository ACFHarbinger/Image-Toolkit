import json
from unittest.mock import patch

import pytest
from gui.src.windows.main.main_window import MainWindow
from PySide6.QtWidgets import QApplication

from .test_main_window import MockVaultManager, cleanup_recovery_files

pytestmark = pytest.mark.gui


class TestLoadTabConfig:
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

    def _make_window(self, q_app, preferences=None, extra_creds=None):
        creds = {"account_name": "test_user", "preferences": preferences or {}}
        if extra_creds:
            creds.update(extra_creds)
        vault = MockVaultManager(creds)
        window = MainWindow(vault_manager=vault)  # pyrefly: ignore [bad-argument-type]
        QApplication.processEvents()
        return window, vault

    def test_meta_s_triggers_load_tab_config(self, q_app):
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QKeyEvent

        window, _vault = self._make_window(q_app)
        with patch.object(window, "_open_load_tab_config_dialog") as mock_open:
            event = QKeyEvent(
                QKeyEvent.Type.KeyPress,
                Qt.Key.Key_S,
                Qt.KeyboardModifier.MetaModifier,
            )
            window.keyPressEvent(event)
            mock_open.assert_called_once()

    def test_no_configs_shows_info_message(self, q_app):
        window, _vault = self._make_window(q_app)

        class _FakeTab:
            def set_config(self, config):
                pass

        active_category = window.command_combo.currentText()
        active_tab_name = window.tabs.tabText(window.tabs.currentIndex())
        window.all_tabs[active_category][active_tab_name] = _FakeTab()

        with patch("gui.src.windows.main._load_tab_config.QMessageBox") as mock_box:
            window._open_load_tab_config_dialog()
            mock_box.information.assert_called_once()

    def test_tab_without_set_config_warns(self, q_app):
        window, _vault = self._make_window(q_app)

        class _NoConfigTab:
            pass

        active_category = window.command_combo.currentText()
        active_tab_name = window.tabs.tabText(window.tabs.currentIndex())
        window.all_tabs[active_category][active_tab_name] = _NoConfigTab()

        with patch("gui.src.windows.main._load_tab_config.QMessageBox") as mock_box:
            window._open_load_tab_config_dialog()
            mock_box.warning.assert_called_once()

    def test_load_tab_config_into_applies_config_and_shows_status(self, q_app):
        window, _vault = self._make_window(q_app)

        class _FakeTab:
            def __init__(self):
                self.applied = None

            def set_config(self, config):
                self.applied = config

        fake_tab = _FakeTab()
        with patch.object(window, "show_status") as mock_status:
            window._load_tab_config_into(fake_tab, {"some_key": "some_value"}, "MyConfig")
            assert fake_tab.applied == {"some_key": "some_value"}
            mock_status.assert_called_once_with("Loaded configuration 'MyConfig'.")

    def test_load_tab_config_into_handles_set_config_exception(self, q_app):
        window, _vault = self._make_window(q_app)

        class _BrokenTab:
            def set_config(self, config):
                raise RuntimeError("boom")

        with patch("gui.src.windows.main._load_tab_config.QMessageBox") as mock_box:
            window._load_tab_config_into(_BrokenTab(), {}, "MyConfig")
            mock_box.critical.assert_called_once()

    def test_open_dialog_end_to_end_selects_and_loads(self, q_app):
        window, _vault = self._make_window(q_app)

        class _FakeTab:
            def __init__(self):
                self.applied = None

            def set_config(self, config):
                self.applied = config

        active_category = window.command_combo.currentText()
        active_tab_name = window.tabs.tabText(window.tabs.currentIndex())
        fake_tab = _FakeTab()
        window.all_tabs[active_category][active_tab_name] = fake_tab

        creds = window.vault_manager.load_account_credentials()
        creds["tab_configurations"] = {"_FakeTab": {"MyConfig": {"some_key": "some_value"}}}
        window.vault_manager.save_data(json.dumps(creds))

        from PySide6.QtWidgets import QDialog

        with patch("gui.src.windows.main._load_tab_config.QDialog.exec", return_value=QDialog.DialogCode.Accepted):
            window._open_load_tab_config_dialog()

        assert fake_tab.applied == {"some_key": "some_value"}
