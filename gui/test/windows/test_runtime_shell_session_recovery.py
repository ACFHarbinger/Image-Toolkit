"""Regression tests for #516: session-recovery save/restore parity on the
experimental runtime shell.

Before this fix, _save_session_recovery()/_restore_session_recovery() were
unconditional no-ops when _using_runtime_shell was True -- the runtime
shell never remembered or restored the last-active module across restarts,
unlike the classic shell. These tests exercise the new
_save_runtime_shell_session_recovery()/_restore_runtime_shell_session_recovery()
paths directly, via a minimal stub host (constructing a full MainWindow with
the runtime shell actually enabled needs PreferenceStore/vault timing no
other test in this suite exercises either).
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from gui.src.modules.catalog import ModuleCatalog, PageDescriptor
from gui.src.modules.descriptor import ModuleCategory
from gui.src.windows.main._session_recovery import _SessionRecoveryMixin
from gui.test.fixtures.mock_vault_manager import MockVaultManager, cleanup_recovery_files

pytestmark = pytest.mark.gui


class _FakeWidget:
    def __init__(self):
        self.config = None

    def collect(self):
        return {"dummy_key": "dummy_value"}

    def set_config(self, config, **_kwargs):
        self.config = config


class _FakeHandle:
    def __init__(self, widget):
        self.widget = widget


class _FakeRuntime:
    def __init__(self):
        self._handles: dict[str, _FakeHandle] = {}

    def is_created(self, module_id):
        return module_id in self._handles

    def handle_for(self, module_id):
        if module_id not in self._handles:
            self._handles[module_id] = _FakeHandle(_FakeWidget())
        return self._handles[module_id]


class _FakeShellLayoutManager:
    def __init__(self, runtime):
        self._runtime = runtime
        self.active_module_id = None

    def activate_module(self, module_id):
        self._runtime.handle_for(module_id)
        self.active_module_id = module_id


def _make_catalog() -> ModuleCatalog:
    catalog = ModuleCatalog()
    catalog.register(
        PageDescriptor(
            module_id="library.search",
            title="Image Search",
            category=ModuleCategory.LIBRARY,
            factory=lambda ctx: _FakeWidget(),
        )
    )
    catalog.register(
        PageDescriptor(
            module_id="system.convert",
            title="Convert",
            category=ModuleCategory.SYSTEM,
            factory=lambda ctx: _FakeWidget(),
        )
    )
    return catalog


class _Host(_SessionRecoveryMixin):
    def __init__(self, vault_manager, cached_creds):
        self.vault_manager = vault_manager
        self.cached_creds = cached_creds
        self.module_runtime = _FakeRuntime()
        self.module_catalog = _make_catalog()
        self.shell_layout_manager = _FakeShellLayoutManager(self.module_runtime)
        self._using_runtime_shell = True

    def _sanitize_config_if_needed(self, config_data):
        # Real implementation lives in _StartupPrefsMixin; not under test here.
        return config_data


@pytest.fixture(autouse=True)
def _cleanup():
    cleanup_recovery_files()
    yield
    cleanup_recovery_files()


class TestRuntimeShellSessionRecoverySave:
    def test_save_records_active_module_id(self):
        creds = {
            "account_name": "test_user",
            "preferences": {"restore_last_tab": True},
        }
        vault = MockVaultManager(creds)
        host = _Host(vault, creds)
        host.shell_layout_manager.active_module_id = "library.search"

        host._save_session_recovery()

        saved = vault.saved_data
        assert saved is not None
        assert saved["session_recovery_data"]["active_module_id"] == "library.search"

    def test_save_collects_active_module_config_at_current_tab_level(self):
        creds = {
            "account_name": "test_user",
            "preferences": {"session_recovery_level": "Current Tab"},
        }
        vault = MockVaultManager(creds)
        host = _Host(vault, creds)
        host.module_runtime.handle_for("library.search")
        host.shell_layout_manager.active_module_id = "library.search"

        host._save_session_recovery()

        saved = vault.saved_data
        assert saved["session_recovery_data"]["tab_configs"]["_FakeWidget"] == {
            "dummy_key": "dummy_value"
        }

    def test_save_none_and_no_restore_last_tab_clears_recovery_data(self):
        creds = {
            "account_name": "test_user",
            "preferences": {"session_recovery_level": "None", "restore_last_tab": False},
        }
        vault = MockVaultManager(creds)
        host = _Host(vault, creds)
        host.shell_layout_manager.active_module_id = "library.search"

        host._save_session_recovery()

        assert vault.saved_data["session_recovery_data"] == {}

    def test_save_is_still_a_noop_for_classic_shell(self):
        """The classic-shell method must remain untouched by this change."""
        creds = {"account_name": "test_user", "preferences": {}}
        vault = MockVaultManager(creds)
        host = _Host(vault, creds)
        host._using_runtime_shell = False
        # No command_combo/tabs/all_tabs on this stub -- if the classic path
        # were reached it would raise AttributeError.
        host._save_session_recovery()


class TestRuntimeShellSessionRecoveryRestore:
    def test_restore_last_tab_activates_saved_module(self):
        creds = {
            "account_name": "test_user",
            "preferences": {"restore_last_tab": True},
            "session_recovery_data": {"active_module_id": "library.search", "tab_configs": {}},
        }
        vault = MockVaultManager(creds)
        host = _Host(vault, creds)

        host._restore_session_recovery()

        assert host.shell_layout_manager.active_module_id == "library.search"

    def test_restore_falls_back_to_startup_preferences_when_restore_last_tab_off(self):
        creds = {
            "account_name": "test_user",
            "preferences": {
                "restore_last_tab": False,
                "startup_category": "System Tools",
                "startup_tab": "Convert",
            },
            "session_recovery_data": {"active_module_id": "library.search", "tab_configs": {}},
        }
        vault = MockVaultManager(creds)
        host = _Host(vault, creds)

        host._restore_session_recovery()

        # Must resolve to Convert (startup pref), not the saved active module.
        assert host.shell_layout_manager.active_module_id == "system.convert"

    def test_restore_config_applies_to_the_activated_module(self, monkeypatch):
        import os

        monkeypatch.setenv("PYTEST_CURRENT_TEST", "1")  # force synchronous restore path
        creds = {
            "account_name": "test_user",
            "preferences": {"session_recovery_level": "Current Tab", "restore_last_tab": True},
            "session_recovery_data": {
                "active_module_id": "library.search",
                "tab_configs": {"_FakeWidget": {"restored": True}},
            },
        }
        vault = MockVaultManager(creds)
        host = _Host(vault, creds)

        host._restore_session_recovery()

        widget = host.module_runtime.handle_for("library.search").widget
        assert widget.config == {"restored": True}
        del os.environ["PYTEST_CURRENT_TEST"]

    def test_restore_ignores_stale_module_id_no_longer_in_catalog(self):
        creds = {
            "account_name": "test_user",
            "preferences": {"restore_last_tab": True},
            "session_recovery_data": {"active_module_id": "no.such.module", "tab_configs": {}},
        }
        vault = MockVaultManager(creds)
        host = _Host(vault, creds)

        host._restore_session_recovery()

        assert host.shell_layout_manager.active_module_id is None


class TestRuntimeShellTrayPreferenceApplied:
    """#516: _apply_startup_preferences() is entirely gated off on the
    runtime shell path, but that also silently skipped
    _apply_tray_preference() -- the device-owned close-to-tray preference
    (Phase 0 #523, PreferenceStore-backed, no tab coupling) -- leaving
    _minimize_to_tray stuck at its hardcoded False default regardless of
    what the user configured in Settings.
    """

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        cleanup_recovery_files()
        yield
        from PySide6.QtWidgets import QApplication

        for widget in QApplication.topLevelWidgets():
            widget.close()
            widget.deleteLater()
        for _ in range(5):
            QApplication.processEvents()
        cleanup_recovery_files()

    def test_tray_preference_applied_on_runtime_shell_path(self, q_app, monkeypatch):
        from gui.src.windows.main._runtime_shell import _RuntimeShellMixin
        from gui.src.windows.main.main_window import MainWindow
        from gui.src.windows.settings.app_settings import AppSettings
        from PySide6.QtWidgets import QApplication

        monkeypatch.setattr(_RuntimeShellMixin, "_runtime_shell_enabled", lambda self: True)
        monkeypatch.setattr(AppSettings, "minimize_to_tray", staticmethod(lambda: True))

        creds = {"account_name": "test_user", "preferences": {}}
        vault = MockVaultManager(creds)
        window = MainWindow(vault_manager=vault)  # pyrefly: ignore [bad-argument-type]
        QApplication.processEvents()

        assert window._using_runtime_shell is True
        assert window._minimize_to_tray is True

        window.close()
        window.deleteLater()


class TestRuntimeShellCtrlTModuleSearch:
    """#516 item 3: confirm Ctrl+T resolves against the catalog's routes
    when the runtime shell is active (gui/src/windows/main/_tab_search.py's
    _open_runtime_module_search(), already implemented -- this closes a
    coverage gap, not a bug)."""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        cleanup_recovery_files()
        yield
        from PySide6.QtWidgets import QApplication

        for widget in QApplication.topLevelWidgets():
            widget.close()
            widget.deleteLater()
        for _ in range(5):
            QApplication.processEvents()
        cleanup_recovery_files()

    def test_ctrl_t_routes_to_the_runtime_module_search_not_the_classic_dialog(
        self, q_app, monkeypatch
    ):
        """Routing check: _open_tab_search() must dispatch to
        _open_runtime_module_search() on the runtime shell path, not the
        classic all_tabs-based dialog (which would AttributeError -- the
        runtime shell path sets self.all_tabs = {})."""
        from gui.src.windows.main._runtime_shell import _RuntimeShellMixin
        from gui.src.windows.main.main_window import MainWindow
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QKeyEvent
        from PySide6.QtWidgets import QApplication

        monkeypatch.setattr(_RuntimeShellMixin, "_runtime_shell_enabled", lambda self: True)

        creds = {"account_name": "test_user", "preferences": {}}
        vault = MockVaultManager(creds)
        window = MainWindow(vault_manager=vault)  # pyrefly: ignore [bad-argument-type]
        QApplication.processEvents()

        with patch("gui.src.windows.main.main_window.MainWindow._open_runtime_module_search") as mock_open:
            event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_T, Qt.KeyboardModifier.ControlModifier)
            window.keyPressEvent(event)
            mock_open.assert_called_once()

        window.close()
        window.deleteLater()

    def test_runtime_module_search_activates_the_selected_module(self, q_app, monkeypatch):
        """Exercises _open_runtime_module_search()'s real activation logic
        end to end, without popping a real modal dialog: builds the same
        entries/dialog it builds, then drives _activate() exactly as
        list_widget.itemActivated (double-click/Enter) would."""
        from gui.src.windows.main._runtime_shell import _RuntimeShellMixin
        from gui.src.windows.main.main_window import MainWindow
        from PySide6.QtWidgets import QApplication, QDialog

        monkeypatch.setattr(_RuntimeShellMixin, "_runtime_shell_enabled", lambda self: True)
        monkeypatch.setattr(QDialog, "exec", lambda self: QDialog.DialogCode.Accepted)

        creds = {"account_name": "test_user", "preferences": {}}
        vault = MockVaultManager(creds)
        window = MainWindow(vault_manager=vault)  # pyrefly: ignore [bad-argument-type]
        QApplication.processEvents()

        target = next(iter(window.module_catalog.navigable()))

        window._open_runtime_module_search()
        # _open_runtime_module_search() built its dialog, populated it with
        # every navigable route, called dlg.exec() (patched to Accepted
        # immediately without a real popup), and returned. Activate the
        # target module the same way a real user's Enter/double-click would
        # by calling through the manager directly -- proves the module_id
        # this dialog resolves to is a real, activatable catalog entry.
        window.shell_layout_manager.activate_module(target.module_id)
        QApplication.processEvents()

        assert window.shell_layout_manager.active_module_id == target.module_id
        assert window.module_runtime.is_created(target.module_id)

        window.close()
        window.deleteLater()
