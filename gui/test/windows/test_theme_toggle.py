import pytest
from gui.src.windows.main.main_window import MainWindow
from gui.test.fixtures.mock_vault_manager import MockVaultManager, cleanup_recovery_files
from PySide6.QtWidgets import QApplication

pytestmark = pytest.mark.gui


class TestThemeToggle:
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
        vault = MockVaultManager({"account_name": "test_user", "theme": "dark"})
        window = MainWindow(vault_manager=vault, dropdown=False)  # pyrefly: ignore [bad-argument-type]
        QApplication.processEvents()
        return window, vault

    def test_theme_toggle(self, q_app):
        window, vault = self._make_window(q_app)

        assert window.current_theme == "dark"
        assert window._theme_toggle_btn.text() == "☀"

        # Toggle theme to light
        window._toggle_theme()
        assert window.current_theme == "light"
        assert window._theme_toggle_btn.text() == "🌙"
        assert vault.creds.get("theme") == "light"

        # Toggle back to dark
        window._toggle_theme()
        assert window.current_theme == "dark"
        assert window._theme_toggle_btn.text() == "☀"
        assert vault.creds.get("theme") == "dark"
