"""Account-switch disposal (#572 / DS-5): identity change only."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from gui.src.windows.main.main_window import MainWindow

pytestmark = pytest.mark.gui


class _Harness:
    """Minimal host for MainWindow._refresh_account_credentials."""

    def __init__(self) -> None:
        self.cached_creds = {"account_name": "alice"}
        self.vault_manager = MagicMock()
        self._using_runtime_shell = False
        self.all_tabs = {}
        self.disposed_for: list[str] = []

    def _dispose_modules_for_account_switch(self, account_id: str) -> None:
        self.disposed_for.append(account_id)


def test_same_account_refresh_does_not_dispose(monkeypatch, q_app):
    attach = MagicMock()
    monkeypatch.setattr(
        "gui.src.windows.main.main_window.PreferenceStore.instance",
        lambda: SimpleNamespace(attach_vault_credentials=attach),
    )
    host = _Harness()
    MainWindow._refresh_account_credentials(host, {"account_name": "alice"})
    assert host.disposed_for == []
    attach.assert_called_once()


def test_account_identity_change_disposes(monkeypatch, q_app):
    attach = MagicMock()
    monkeypatch.setattr(
        "gui.src.windows.main.main_window.PreferenceStore.instance",
        lambda: SimpleNamespace(attach_vault_credentials=attach),
    )
    host = _Harness()
    MainWindow._refresh_account_credentials(host, {"account_name": "bob"})
    assert host.disposed_for == ["bob"]
    assert host.cached_creds["account_name"] == "bob"


def test_classic_shell_clears_pixmap_caches(q_app):
    class _Cache:
        def __init__(self) -> None:
            self.cleared = False

        def clear(self) -> None:
            self.cleared = True

    cache = _Cache()
    tab = SimpleNamespace(
        cancel_loading=lambda: None,
        _initial_pixmap_cache=cache,
    )
    host = _Harness()
    host.all_tabs = {"core": {"convert": tab}}
    MainWindow._dispose_modules_for_account_switch(host, "bob")
    assert cache.cleared is True
