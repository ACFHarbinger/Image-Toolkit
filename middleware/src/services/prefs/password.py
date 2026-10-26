"""Master-password gate for the settings window (#1112).

The change is refused unless the caller passes the current password and the
vault session confirms it. This module does not open a vault, hash a
password, or touch ``auth.status``.
"""

from __future__ import annotations

from typing import Any

LOCKED = "C++ vault session locked"
MISMATCH = "current password does not match"


def _refused(reason: str) -> dict[str, Any]:
    return {"success": False, "credentials_changed": False, "reason": reason}


def set_master_password(
    account: str,
    current_password: str,
    new_password: str,
    session: Any | None,
) -> dict[str, Any]:
    """Delegate a password change after the session confirms the current one."""
    if not isinstance(account, str) or not account.strip():
        raise ValueError("account is required")
    if not isinstance(new_password, str) or not new_password.strip():
        return {"success": True, "credentials_changed": False, "reason": ""}
    current = current_password if isinstance(current_password, str) else ""
    updater = getattr(session, "update_account_password", None) if session is not None else None
    confirm = getattr(session, "confirm_password", None) if session is not None else None
    if not current.strip() or not callable(updater) or not callable(confirm):
        return _refused(LOCKED)
    try:
        matches = confirm(current)
    except Exception:
        return _refused(LOCKED)
    if matches is not True:
        return _refused(MISMATCH)
    updater(account.strip(), new_password)
    return {"success": True, "credentials_changed": True, "reason": ""}
