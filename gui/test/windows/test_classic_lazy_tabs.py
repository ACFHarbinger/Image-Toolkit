"""R2.e / #566: classic shell constructs at most one category at startup."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from gui.src.windows.main._tab_registry import classic_factory_ids_for
from gui.src.windows.main.main_window import MainWindow
from gui.test.fixtures.mock_vault_manager import MockVaultManager, cleanup_recovery_files
from PySide6.QtWidgets import QApplication

pytestmark = pytest.mark.gui

SYSTEM_TOOLS_IDS = classic_factory_ids_for("System Tools")
LIBRARY_IDS = classic_factory_ids_for("Library Database")


@pytest.fixture(autouse=True)
def _cleanup_windows():
    cleanup_recovery_files()
    yield
    for widget in QApplication.topLevelWidgets():
        patcher = getattr(widget, "_itk_build_tab_patcher", None)
        if patcher is not None:
            patcher.stop()
        widget.close()
        widget.deleteLater()
    for _ in range(5):
        QApplication.processEvents()
    cleanup_recovery_files()


def _make_window(creds: dict | None = None):
    vault = MockVaultManager(creds or {"account_name": "test_user", "preferences": {}})
    constructed: list[str] = []
    from gui.src.modules import tab_factory as tab_factory_mod

    real_build = tab_factory_mod.build_tab

    def tracking_build(module_id, context):
        constructed.append(module_id)
        return real_build(module_id, context)

    patcher = patch("gui.src.modules.build_tab", side_effect=tracking_build)
    patcher.start()
    try:
        window = MainWindow(vault_manager=vault)  # pyrefly: ignore [bad-argument-type]
        QApplication.processEvents()
        window._itk_build_tab_patcher = patcher
    except Exception:
        patcher.stop()
        raise
    return window, constructed


def test_classic_startup_constructs_only_system_tools(q_app):
    window, constructed = _make_window()
    assert window.command_combo.currentText() == "System Tools"
    assert set(constructed) == set(SYSTEM_TOOLS_IDS)
    assert window._constructed_categories == {"System Tools"}
    assert window.convert_tab is not None
    assert window.search_tab is None
    assert window.train_tab is None
    assert window.stitch_tab is None


def test_switching_category_constructs_that_category_once(q_app):
    window, constructed = _make_window()
    window.command_combo.setCurrentText("Library Database")
    QApplication.processEvents()
    assert set(SYSTEM_TOOLS_IDS).issubset(set(constructed))
    assert set(LIBRARY_IDS).issubset(set(constructed))
    assert constructed.count("library.search") == 1
    window.command_combo.setCurrentText("Library Database")
    QApplication.processEvents()
    assert constructed.count("library.search") == 1
    assert window._constructed_categories == {"System Tools", "Library Database"}


def test_restore_last_tab_constructs_only_that_category(q_app):
    creds = {
        "account_name": "test_user",
        "preferences": {
            "session_recovery_level": "Current Tab",
            "restore_last_tab": True,
        },
        "session_recovery_data": {
            "active_category": "Library Database",
            "active_tab": "Image Search",
            "tab_configs": {},
        },
    }
    window, constructed = _make_window(creds)
    assert window.command_combo.currentText() == "Library Database"
    assert set(constructed) == set(LIBRARY_IDS)
    assert "system.convert" not in constructed
    assert window.search_tab is not None
    assert window.convert_tab is None
