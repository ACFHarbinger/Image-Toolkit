"""The sidecar vault session reports lock state and never opens library.db (#1106)."""

from __future__ import annotations

import builtins
import sqlite3
from pathlib import Path

import pytest
from middleware.src.services.auth.session import LiveVault, VaultOpenError, open_live_session
from middleware.src.services.auth.status import LOCKED_REASON, OPEN_REASON, auth_status


class _Session:
    def __init__(self, account: str, *, open_: bool = True) -> None:
        self.account = account
        self.open = open_

    def shutdown(self) -> None:
        self.open = False


def _refuse_vault(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("vault path must not be touched")

    for name in ("read_text", "write_text", "read_bytes", "write_bytes", "open"):
        monkeypatch.setattr(Path, name, refuse)
    monkeypatch.setattr(sqlite3, "connect", refuse)

    real_import = builtins.__import__

    def guarded(name: str, globals=None, locals=None, fromlist=(), level: int = 0):  # noqa: ANN001
        lowered = name.lower()
        imported = tuple(fromlist or ())
        if "vault" in lowered or any("vault" in str(item).lower() for item in imported):
            raise AssertionError(name)
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", guarded)


def test_locked_result_does_not_touch_the_vault(monkeypatch: pytest.MonkeyPatch) -> None:
    _refuse_vault(monkeypatch)
    result = auth_status("  keeper  ")
    assert result == {"unlocked": False, "account": "keeper", "reason": LOCKED_REASON}


def test_open_session_is_reported_for_the_same_account(monkeypatch: pytest.MonkeyPatch) -> None:
    _refuse_vault(monkeypatch)
    session = _Session("keeper")
    assert auth_status(" keeper ", session) == {
        "unlocked": True,
        "account": "keeper",
        "reason": OPEN_REASON,
    }
    assert auth_status("other", session)["unlocked"] is False
    assert auth_status("other", session)["reason"] == LOCKED_REASON


def test_empty_account_raises_without_echoing_it() -> None:
    with pytest.raises(ValueError, match="^account is empty$") as exc_info:
        auth_status("  \n  ")
    assert "\n" not in str(exc_info.value)


def test_missing_native_module_does_not_open_a_session(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("VaultManager must not be constructed")

    monkeypatch.setattr("middleware.src.services.auth.session.VaultManager", refuse)
    monkeypatch.setattr("middleware.src.services.auth.session._load_vault_api", lambda: None)
    with pytest.raises(VaultOpenError, match="missing"):
        open_live_session("keeper", "secret")


def test_live_vault_delegates_password_change_only_while_open() -> None:
    class Manager:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str]] = []

        def update_account_password(self, account_name: str, new_raw_pass: str) -> None:
            self.calls.append((account_name, new_raw_pass))

        def shutdown(self) -> None:
            return None

    manager = Manager()
    live = LiveVault("ada", manager, [])
    live.update_account_password("ada", "next")
    assert manager.calls == [("ada", "next")]
    with pytest.raises(RuntimeError, match="locked"):
        live.update_account_password("other", "next")
    live.shutdown()
    with pytest.raises(RuntimeError, match="locked"):
        live.update_account_password("ada", "later")
