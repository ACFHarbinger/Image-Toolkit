"""Master-password gate for the settings window (#1112).

The change is refused unless the caller passes the current password and
injects a vault session object. This module does not open a vault, hash a
password, or touch ``auth.status``.
"""

from __future__ import annotations

from typing import Any

LOCKED = "C++ vault session locked"


def set_master_password(
    account: str,
    current_password: str,
    new_password: str,
    session: Any | None,
) -> dict[str, Any]:
    """Delegate a password change, or refuse when the C++ session is absent."""
    if not isinstance(account, str) or not account.strip():
        raise ValueError("account is required")
    if not isinstance(new_password, str) or not new_password.strip():
        return {"success": True, "credentials_changed": False, "reason": ""}
    current = current_password if isinstance(current_password, str) else ""
    updater = getattr(session, "update_account_password", None) if session is not None else None
    if not current.strip() or not callable(updater):
        return {"success": False, "credentials_changed": False, "reason": LOCKED}
    updater(account.strip(), new_password)
    return {"success": True, "credentials_changed": True, "reason": ""}
