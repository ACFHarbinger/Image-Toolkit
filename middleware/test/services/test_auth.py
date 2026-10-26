"""The sidecar vault session reports lock state and never opens library.db (#1106)."""

from __future__ import annotations

import builtins
import hashlib
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


def test_live_vault_refuses_password_change_without_library_rekey(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("middleware.src.constants.update_cryptographic_values", lambda _account: None)
    class Manager:
        def __init__(self) -> None:
            self.calls: list[tuple[str, str]] = []

        def update_account_password(self, account_name: str, new_raw_pass: str) -> None:
            self.calls.append((account_name, new_raw_pass))

        def shutdown(self) -> None:
            return None

    manager = Manager()
    live = LiveVault("ada", manager, [])
    with pytest.raises(RuntimeError, match="library rekeying"):
        live.update_account_password("ada", "next")
    assert manager.calls == []
    with pytest.raises(RuntimeError, match="locked"):
        live.update_account_password("other", "next")
    live.shutdown()
    with pytest.raises(RuntimeError, match="locked"):
        live.update_account_password("ada", "later")


def test_live_vault_confirms_only_the_stored_password() -> None:
    salt = "salt"
    pepper = "pepper"
    digest = hashlib.sha256(("old-secret" + salt + pepper).encode("utf-8")).hexdigest()

    class Manager:
        PEPPER = pepper

        def load_account_credentials(self) -> dict[str, str]:
            return {"account_name": "ada", "hashed_password": digest, "salt": salt}

        def update_account_password(self, account_name: str, new_raw_pass: str) -> None:
            raise AssertionError("confirm must not re-key")

        def shutdown(self) -> None:
            return None

    live = LiveVault("ada", Manager(), [])
    assert live.confirm_password("old-secret") is True
    assert live.confirm_password("not-the-password") is False
    live.shutdown()
    assert live.confirm_password("old-secret") is False


_PATH_NAMES = ("KEYSTORE_FILE", "VAULT_FILE", "PEPPER_FILE")


def test_failed_unlock_restores_the_previous_account_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    import middleware.src.constants as udef
    import middleware.src.constants.crypto as crypto

    for name in _PATH_NAMES:
        monkeypatch.setattr(udef, name, f"/kept/ada/{name}")
        monkeypatch.setattr(crypto, name, f"/kept/ada/{name}")

    def retarget(account: str) -> None:
        for name in _PATH_NAMES:
            value = f"/other/{account}/{name}"
            setattr(udef, name, value)
            setattr(crypto, name, value)

    class Manager:
        def load_keystore(self, *_args: object) -> None:
            raise FileNotFoundError("missing")

        def shutdown(self) -> None:
            return None

    class Api:
        def is_unlocked(self, _handle: object) -> bool:
            return False

    monkeypatch.setattr(udef, "update_cryptographic_values", retarget)
    monkeypatch.setattr("middleware.src.services.auth.session.VaultManager", Manager)
    monkeypatch.setattr("middleware.src.services.auth.session._load_vault_api", lambda: Api())
    with pytest.raises(VaultOpenError, match="not found"):
        open_live_session("bee", "nope")
    for name in _PATH_NAMES:
        assert getattr(udef, name) == f"/kept/ada/{name}"
        assert getattr(crypto, name) == f"/kept/ada/{name}"


def test_refused_password_update_leaves_account_paths_untouched(monkeypatch: pytest.MonkeyPatch) -> None:
    import middleware.src.constants as udef

    monkeypatch.setattr(udef, "KEYSTORE_FILE", "/other/bee/keystore")
    bound: list[str] = []

    def retarget(account: str) -> None:
        bound.append(account)
        udef.KEYSTORE_FILE = f"/live/{account}/keystore"

    monkeypatch.setattr(udef, "update_cryptographic_values", retarget)

    class Manager:
        def __init__(self) -> None:
            self.path = ""

        def update_account_password(self, account_name: str, new_raw_pass: str) -> None:
            del account_name, new_raw_pass
            self.path = udef.KEYSTORE_FILE

        def shutdown(self) -> None:
            return None

    manager = Manager()
    live = LiveVault("ada", manager, [])
    with pytest.raises(RuntimeError, match="library rekeying"):
        live.update_account_password("ada", "next")
    assert bound == []
    assert manager.path == ""
    assert udef.KEYSTORE_FILE == "/other/bee/keystore"
    with pytest.raises(RuntimeError, match="locked"):
        live.update_account_password("bee", "later")
    assert bound == []
