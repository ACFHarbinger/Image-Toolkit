import os
import pytest
from PySide6.QtWidgets import QApplication
from gui.src.windows.main.main_window import MainWindow

pytestmark = pytest.mark.gui


class MockVaultManager:
    def __init__(self, credentials):
        self.creds = credentials
        self.saved_data = None

    def load_account_credentials(self):
        return self.creds

    def save_data(self, json_string):
        import json
        self.saved_data = json.loads(json_string)
        self.creds = self.saved_data


def test_theme_toggle(q_app):
    vault = MockVaultManager({"account_name": "TestUser", "theme": "dark"})
    window = MainWindow(vault_manager=vault, dropdown=False)

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
