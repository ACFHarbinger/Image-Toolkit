"""Regression tests for _RuntimeShellMixin (#536, Codex #538 combined review).

Covers the two HIGH findings from Codex's combined #533+#535+#536 review:
1. _create_runtime_shell() must not activate a module synchronously during
   construction -- it must defer to the next event-loop turn.
2. _quit_application()'s tray-Quit path must dispose the runtime shell the
   same way closeEvent() does, since it bypasses closeEvent entirely.
"""

from __future__ import annotations

import pytest
from gui.src.modules import ModuleCategory
from gui.src.modules.catalog import ModuleCatalog, PageDescriptor
from gui.src.preferences import PreferenceStore
from gui.src.windows.main._runtime_shell import _RuntimeShellMixin
from PySide6.QtWidgets import QApplication, QWidget

pytestmark = pytest.mark.gui


class _CountingHandle:
    def __init__(self, widget):
        self.widget = widget

    def activate(self, route_key=None):
        pass

    def deactivate(self):
        pass

    def dispose(self):
        pass


@pytest.fixture(autouse=True)
def _reset_preference_store():
    PreferenceStore.reset_instance()
    yield
    PreferenceStore.reset_instance()


@pytest.fixture
def stub_main_window(q_app, monkeypatch):
    """A bare object combining the mixin with the minimal attributes it reads."""
    from gui.src.modules.runtime import WidgetHandle
    from PySide6.QtWidgets import QLabel

    calls: dict[str, int] = {}

    def _fake_build_application_catalog(**_kwargs):
        catalog = ModuleCatalog()

        def factory(_ctx):
            calls["system.convert"] = calls.get("system.convert", 0) + 1
            return WidgetHandle(QLabel("Convert"))

        catalog.register(
            PageDescriptor(
                module_id="system.convert",
                title="Convert",
                category=ModuleCategory.SYSTEM,
                factory=factory,
            )
        )
        return catalog

    monkeypatch.setattr(
        "gui.src.windows.main._runtime_shell.build_application_catalog",
        _fake_build_application_catalog,
    )

    class _Stub(_RuntimeShellMixin, QWidget):
        def __init__(self):
            super().__init__()
            self.vault_manager = None
            self.cached_creds = {}

    stub = _Stub()
    stub._factory_calls = calls
    return stub


class TestRuntimeShellDeferredActivation:
    def test_construction_does_not_activate_synchronously(self, stub_main_window):
        stub_main_window._create_runtime_shell(dropdown=True, enable_manager=False)
        # HIGH #1: the factory must not have run yet -- activation is deferred
        # to the next event-loop turn, not called inline during construction.
        assert stub_main_window._factory_calls == {}
        assert stub_main_window.shell_layout_manager.stack.count() == 0

    def test_deferred_activation_runs_after_one_event_loop_turn(self, stub_main_window):
        stub_main_window._create_runtime_shell(dropdown=True, enable_manager=False)
        QApplication.processEvents()  # let the singleShot(0, ...) timer fire
        assert stub_main_window._factory_calls == {"system.convert": 1}
        assert stub_main_window.shell_layout_manager.active_module_id == "system.convert"


class TestRuntimeShellQuitDisposal:
    def test_dispose_runtime_shell_clears_stack_and_disposes_runtime(self, stub_main_window):
        stub_main_window._create_runtime_shell(dropdown=True, enable_manager=False)
        QApplication.processEvents()
        assert stub_main_window.shell_layout_manager.stack.count() == 1

        # HIGH #2: simulate what _quit_application must now do (dispose before
        # vault shutdown) rather than skipping runtime-shell cleanup entirely.
        stub_main_window._dispose_runtime_shell()

        assert stub_main_window.shell_layout_manager.stack.count() == 0
        assert not stub_main_window.module_runtime.is_created("system.convert")
