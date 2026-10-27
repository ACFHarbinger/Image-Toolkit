"""Sidecar handlers for the settings window (#917, #1112).

Paths and the vault session are injected here. The default paths are the
home-directory store; tests bind ``tmp_path`` and never pass a session unless
they are exercising the password gate.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from middleware.src.services.prefs.describe import describe
from middleware.src.services.prefs.store import load_window, save_window

_prefs_path: Path | None = None
_keybindings_path: Path | None = None
_session: Any | None = None


def bind_prefs_paths(*, prefs: Path | None = None, keybindings: Path | None = None) -> None:
    """Point the sidecar store at explicit files. ``None`` restores the default."""
    global _prefs_path, _keybindings_path
    _prefs_path = prefs
    _keybindings_path = keybindings


def bind_vault_session(session: Any | None) -> None:
    """Inject the caller's vault session. The sidecar starts with none."""
    global _session
    _session = session


def handle_prefs_describe(params: dict[str, Any]) -> dict[str, Any]:
    account = params.get("account", "")
    if not isinstance(account, str):
        raise ValueError("account is required")
    return describe(account)


def handle_prefs_get(params: dict[str, Any]) -> dict[str, Any]:
    return load_window(params["account"], path=_prefs_path, keybindings=_keybindings_path)


def handle_prefs_set(params: dict[str, Any]) -> dict[str, Any]:
    return save_window(
        params["account"],
        params["profiles"],
        params["gallery"],
        params["logging"],
        shortcut=params.get("shortcut"),
        current_password=params.get("current_password") or "",
        new_password=params.get("new_password") or "",
        path=_prefs_path,
        keybindings=_keybindings_path,
        session=_session,
    )
