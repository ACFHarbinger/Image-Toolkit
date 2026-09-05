"""Runtime-shell session recovery contracts (#516)."""

from __future__ import annotations

import json
import sys
import types


def _mixin(monkeypatch):
    asp = types.ModuleType("asp_backend")
    core = types.ModuleType("asp_backend.core")
    config = types.ModuleType("asp_backend.core.config")
    config.asp_schema = lambda: ()
    config.get_asp = lambda _key: ""
    monkeypatch.setitem(sys.modules, "asp_backend", asp)
    monkeypatch.setitem(sys.modules, "asp_backend.core", core)
    monkeypatch.setitem(sys.modules, "asp_backend.core.config", config)
    from gui.src.windows.main import _runtime_shell

    return _runtime_shell.ShellNavMode, _runtime_shell._RuntimeShellMixin


def test_runtime_session_restores_active_module_and_navigation_mode(monkeypatch):
    ShellNavMode, mixin = _mixin(monkeypatch)
    activated: list[str] = []
    modes: list[ShellNavMode] = []
    window = types.SimpleNamespace(
        cached_creds={
            "preferences": {"restore_last_tab": True},
            "session_recovery_data": {
                "runtime_shell": {"active_module_id": "ml.training", "nav_mode": "top_bar"}
            },
        },
        module_catalog=types.SimpleNamespace(get=lambda module_id: object() if module_id == "ml.training" else None),
        shell_layout_manager=types.SimpleNamespace(
            set_nav_mode=modes.append,
            activate_module=activated.append,
        ),
    )

    mixin._restore_runtime_shell_session(window)

    assert modes == [ShellNavMode.TOP_BAR]
    assert activated == ["ml.training"]


def test_runtime_session_saves_without_overwriting_legacy_payload(monkeypatch):
    _mode, mixin = _mixin(monkeypatch)
    saved: list[dict] = []

    class Vault:
        is_guest = False

        def load_account_credentials(self):
            return {"session_recovery_data": {"active_category": "System Tools"}}

        def save_data(self, payload):
            saved.append(json.loads(payload))

    window = types.SimpleNamespace(
        vault_manager=Vault(),
        cached_creds={"preferences": {"restore_last_tab": True}},
        module_runtime=types.SimpleNamespace(active_module_id="stitch.canvas"),
        shell_layout_manager=types.SimpleNamespace(nav_mode=types.SimpleNamespace(value="rail")),
    )

    mixin._save_runtime_shell_session(window)

    assert saved[0]["session_recovery_data"]["active_category"] == "System Tools"
    assert saved[0]["session_recovery_data"]["runtime_shell"] == {
        "active_module_id": "stitch.canvas",
        "nav_mode": "rail",
    }
