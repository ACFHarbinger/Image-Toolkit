"""auth.status stays locked and does not open the vault (#918)."""

from __future__ import annotations

import builtins
import sqlite3
from pathlib import Path

import pytest
from middleware.src.services.auth.status import REASON, auth_status


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
    assert result == {"unlocked": False, "account": "keeper", "reason": REASON}


def test_empty_account_raises_without_echoing_it() -> None:
    with pytest.raises(ValueError, match="^account is empty$") as exc_info:
        auth_status("  \n  ")
    assert "\n" not in str(exc_info.value)
