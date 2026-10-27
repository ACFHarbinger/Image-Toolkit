"""Sidecar-owned C++ vault session (#1106).

The password is passed to the opener and is not stored or returned.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from middleware.src.services.auth.session import VaultOpenError, open_live_session
from middleware.src.services.auth.status import auth_status

NOT_OPENED = "C++ vault session was not opened."
OPENED = "C++ vault session open."

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


class VaultHub:
    def __init__(self, opener: Opener | None = None) -> None:
        self._opener = opener or open_live_session
        self.session: Any | None = None

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
        _bind_prefs_vault(opened)
        _bind_library_vault(opened)
        return {"success": True, "account": cleaned, "message": OPENED}

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
        session.shutdown()
        self.session = None
        _bind_prefs_vault(None)
        _bind_library_vault(None)
        return {"success": True, "account": cleaned}
