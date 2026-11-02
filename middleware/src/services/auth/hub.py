"""Sidecar-owned C++ vault session (#1106).

The password is passed to the opener and is not stored or returned.
"""

from __future__ import annotations

import shutil
import tempfile
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from middleware.src.services.auth.session import VaultOpenError, open_guest_session, open_live_session
from middleware.src.services.auth.status import auth_status

NOT_OPENED = "C++ vault session was not opened."
OPENED = "C++ vault session open."
GUEST_OPENED = "Guest session open. Settings are kept in memory only and are not saved."
GUEST_FAILED = "Failed to start the guest session."

Opener = Callable[[str, str], Any]


def _bind_prefs_vault(session: Any | None) -> None:
    """Publish the live session when the settings handler is on this tree.

    The shell branch can run without that module. A missing import must not
    fail unlock or lock.
    """
    try:
        from middleware.src.sidecar.handlers.prefs import bind_vault_session
    except ImportError:
        return
    bind_vault_session(session)


def _bind_library_vault(session: Any | None) -> None:
    """Attach library stores when the library lifecycle module is on this tree.

    The shell branch can run without that module. A missing import must not
    fail unlock or lock.
    """
    try:
        from middleware.src.services.library.lifecycle import bind_vault_session
    except ImportError:
        return
    bind_vault_session(session)


def _use_volatile_settings(active: bool, prefs_file: Path | None = None) -> None:
    """Guest sessions keep account-scope settings and window prefs out of the persistent stores.

    ``active`` swaps in memory (and a throwaway prefs file); ``False`` restores the defaults.
    A missing handler module (shell branch) is not an error.
    """
    try:
        from middleware.src.settings.adapters import MemoryStore, default_store
        from middleware.src.settings.scopes import SettingScope
        from middleware.src.sidecar.handlers import prefs as prefs_handler
        from middleware.src.sidecar.handlers.settings import settings_service
    except ImportError:
        return
    settings_service().attach_store(SettingScope.ACCOUNT, MemoryStore() if active else default_store(SettingScope.ACCOUNT))
    prefs_handler.bind_prefs_paths(prefs=prefs_file if active else None, keybindings=prefs_handler._keybindings_path)


class VaultHub:
    def __init__(self, opener: Opener | None = None, guest_opener: Callable[[str], Any] | None = None) -> None:
        self._opener = opener or open_live_session
        self._guest_opener = guest_opener or open_guest_session
        self.session: Any | None = None
        self._guest_dir: str | None = None

    def _drop_guest_files(self) -> None:
        if self._guest_dir is not None:
            shutil.rmtree(self._guest_dir, ignore_errors=True)
            self._guest_dir = None

    def status(self, account: str) -> dict[str, Any]:
        return auth_status(account, self.session)

    def unlock(self, account: str, password: str) -> dict[str, Any]:
        cleaned = account.strip()
        if not cleaned:
            raise ValueError("account is empty")
        if not password:
            raise ValueError("password is empty")
        try:
            opened = self._opener(cleaned, password)
        except VaultOpenError as exc:
            return {"success": False, "account": cleaned, "message": str(exc) or NOT_OPENED}
        except Exception:
            return {"success": False, "account": cleaned, "message": NOT_OPENED}
        if opened is None or not getattr(opened, "open", False) or getattr(opened, "account", None) != cleaned:
            if opened is not None and hasattr(opened, "shutdown"):
                opened.shutdown()
            return {"success": False, "account": cleaned, "message": NOT_OPENED}
        previous = self.session
        self.session = opened
        if previous is not None and previous is not opened:
            previous.shutdown()
        if getattr(previous, "is_guest", False):
            _use_volatile_settings(False)
            self._drop_guest_files()
        _bind_prefs_vault(opened)
        _bind_library_vault(opened)
        return {
            "success": True,
            "account": cleaned,
            "message": OPENED,
            "profiles": list(getattr(opened, "profiles", []) or []),
            "credentials": list(getattr(opened, "credential_keys", []) or []),
        }

    def guest(self, username: str | None = None) -> dict[str, Any]:
        """Open a volatile guest session. An empty name makes an anonymous ``guest_xxxxxxxx`` account."""
        name = (username or "").strip()
        anonymous = not name
        if anonymous:
            name = f"guest_{uuid.uuid4().hex[:8]}"
        try:
            opened = self._guest_opener(name)
        except Exception:
            return {"success": False, "account": name, "anonymous": anonymous, "message": GUEST_FAILED}
        previous = self.session
        self.session = opened
        if previous is not None and previous is not opened:
            previous.shutdown()
        self._drop_guest_files()
        self._guest_dir = tempfile.mkdtemp(prefix="itk-guest-")
        _use_volatile_settings(True, Path(self._guest_dir) / "window_prefs.json")
        _bind_prefs_vault(None)
        _bind_library_vault(None)
        return {"success": True, "account": name, "anonymous": anonymous, "message": GUEST_OPENED}

    def apply_profile(self, account: str, profile: str) -> dict[str, Any]:
        cleaned = account.strip()
        if not cleaned:
            raise ValueError("account is empty")
        session = self.session
        if session is None or not getattr(session, "open", False) or getattr(session, "account", None) != cleaned:
            return {"success": False, "account": cleaned, "profile": profile, "message": NOT_OPENED, "theme": "dark", "tab_configurations": {}}
        try:
            applied = session.apply_profile(profile)
        except ValueError as exc:
            return {"success": False, "account": cleaned, "profile": profile, "message": str(exc), "theme": "dark", "tab_configurations": {}}
        return {
            "success": True,
            "account": cleaned,
            "profile": profile,
            "message": f"Applied '{profile}'.",
            "theme": applied["theme"],
            "tab_configurations": applied["tab_configurations"],
        }

    def lock(self, account: str) -> dict[str, Any]:
        cleaned = account.strip()
        if not cleaned:
            raise ValueError("account is empty")
        session = self.session
        if session is None or not getattr(session, "open", False):
            self.session = None
            _bind_prefs_vault(None)
            _bind_library_vault(None)
            return {"success": True, "account": cleaned}
        if getattr(session, "account", None) != cleaned:
            return {"success": False, "account": cleaned}
        was_guest = bool(getattr(session, "is_guest", False))
        session.shutdown()
        self.session = None
        if was_guest:
            _use_volatile_settings(False)
            self._drop_guest_files()
        _bind_prefs_vault(None)
        _bind_library_vault(None)
        return {"success": True, "account": cleaned}
