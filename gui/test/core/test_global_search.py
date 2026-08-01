from unittest.mock import patch

import pytest
from gui.src.windows.main.main_window import MainWindow
from PySide6.QtWidgets import QApplication

from .test_main_window import MockVaultManager, cleanup_recovery_files

pytestmark = pytest.mark.gui


class TestGlobalSearch:
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
        return window, vault

    def test_ctrl_shift_f_triggers_global_search(self, q_app):
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QKeyEvent

        window, _vault = self._make_window(q_app)
        with patch.object(window, "_open_global_search") as mock_open:
            event = QKeyEvent(
                QKeyEvent.Type.KeyPress,
                Qt.Key.Key_F,
                Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier,
            )
            window.keyPressEvent(event)
            mock_open.assert_called_once()

    def test_iter_gallery_tabs_finds_convert_tab_subtabs(self, q_app):
        window, _vault = self._make_window(q_app)
        found_names = {name for _cat, name, _gallery in window._iter_gallery_tabs()}
        assert "Convert" in found_names or any(
            gallery is window.convert_tab.format_subtab
            for _cat, _name, gallery in window._iter_gallery_tabs()
        )

    def test_open_global_search_jumps_to_match(self, q_app):
        window, _vault = self._make_window(q_app)
        window.convert_tab.format_subtab.master_found_files = ["foo.jpg", "bar_target.jpg"]
        window.convert_tab.format_subtab.found_files = list(
            window.convert_tab.format_subtab.master_found_files
        )

        entries = list(window._iter_gallery_tabs())
        matched = [
            (cat, name, gallery)
            for cat, name, gallery in entries
            if gallery is window.convert_tab.format_subtab
        ]
        assert matched, "ConvertTab's format_subtab should be discoverable by global search"

        category, tab_name, gallery = matched[0]
        assert gallery.jump_to_path("bar_target.jpg") is True
        assert gallery.found_files == ["bar_target.jpg"]
