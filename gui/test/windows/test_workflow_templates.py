from unittest.mock import patch

import pytest
from gui.src.windows.main.main_window import MainWindow
from gui.test.fixtures.mock_vault_manager import MockVaultManager, cleanup_recovery_files
from PySide6.QtWidgets import QApplication

pytestmark = pytest.mark.gui


class TestWorkflowTemplates:
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

    def test_ctrl_shift_m_triggers_workflow_templates(self, q_app):
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QKeyEvent

        window, _vault = self._make_window(q_app)
        with patch.object(window, "_open_workflow_templates_dialog") as mock_open:
            event = QKeyEvent(
                QKeyEvent.Type.KeyPress,
                Qt.Key.Key_M,
                Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier,
            )
            window.keyPressEvent(event)
            mock_open.assert_called_once()

    def test_save_and_load_workflow_templates(self, q_app):
        window, _vault = self._make_window(q_app)
        assert window._load_workflow_templates() == {}

        templates = {"MyFlow": {"steps": [{"category": "Convert", "tab_name": "Convert", "config_name": None}]}}
        assert window._save_workflow_templates(templates) is True
        assert window._load_workflow_templates() == templates

    def test_run_workflow_template_applies_config_and_activates_last_tab(self, q_app):
        active_category = None
        active_tab_name = None

        class _FakeTab:
            def __init__(self):
                self.applied = None

            def set_config(self, config):
                self.applied = config

        window, _vault = self._make_window(q_app)
        active_category = window.command_combo.currentText()
        active_tab_name = window.tabs.tabText(window.tabs.currentIndex())

        fake_tab = _FakeTab()
        # pyrefly: ignore [unsupported-operation]
        window.all_tabs[active_category][active_tab_name] = fake_tab

        creds = window.vault_manager.load_account_credentials()
        creds["tab_configurations"] = {"_FakeTab": {"MyConfig": {"some_key": "some_value"}}}
        window.vault_manager.save_data(__import__("json").dumps(creds))

        templates = {
            "MyFlow": {
                "steps": [
                    {"category": active_category, "tab_name": active_tab_name, "config_name": "MyConfig"},
                ]
            }
        }
        window._save_workflow_templates(templates)

        with patch.object(window, "_select_tab_by_name") as mock_select:
            window._run_workflow_template("MyFlow")
            QApplication.processEvents()
            assert fake_tab.applied == {"some_key": "some_value"}
            assert window.command_combo.currentText() == active_category
            mock_select.assert_called_once_with(active_tab_name)

    def test_run_workflow_template_missing_name_warns(self, q_app):
        from unittest.mock import patch as _patch

        window, _vault = self._make_window(q_app)
        with _patch("gui.src.windows.main._workflow_templates.QMessageBox") as mock_box:
            window._run_workflow_template("DoesNotExist")
            mock_box.warning.assert_called_once()
