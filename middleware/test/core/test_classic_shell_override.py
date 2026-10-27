"""just python forces the classic tabbed shell without rewriting the preference."""

from __future__ import annotations

import os

from gui.src.windows.main._runtime_shell import MainRuntimeShellController

from middleware.src.app import _CLASSIC_SHELL_ENV, apply_classic_shell_override


def test_classic_shell_env_disables_runtime_shell(monkeypatch):
    import gui.src.windows.main._runtime_shell as runtime_shell

    original = runtime_shell.runtime_shell_enabled
    monkeypatch.setenv(_CLASSIC_SHELL_ENV, "1")
    try:
        assert apply_classic_shell_override() is True
        assert runtime_shell.runtime_shell_enabled(None) is False
        assert MainRuntimeShellController._runtime_shell_enabled(object()) is False
    finally:
        runtime_shell.runtime_shell_enabled = original


def test_classic_shell_override_is_opt_in(monkeypatch):
    import gui.src.windows.main._runtime_shell as runtime_shell

    original = runtime_shell.runtime_shell_enabled
    monkeypatch.delenv(_CLASSIC_SHELL_ENV, raising=False)
    try:
        assert apply_classic_shell_override() is False
        assert runtime_shell.runtime_shell_enabled is original
        assert os.environ.get(_CLASSIC_SHELL_ENV) is None
    finally:
        runtime_shell.runtime_shell_enabled = original
