"""Live C++ vault session status (#1106).

The account is checked after strip and is never copied into an error string.
A missing session is locked. This module does not open a database.
"""

from __future__ import annotations

from typing import Any, Protocol

LOCKED_REASON = "C++ vault session locked"
OPEN_REASON = "C++ vault session open"


class VaultSession(Protocol):
    account: str
    open: bool

    def shutdown(self) -> None: ...


def auth_status(account: str, session: VaultSession | None = None) -> dict[str, Any]:
    cleaned = account.strip()
    if not cleaned:
        raise ValueError("account is empty")
    if session is not None and session.open and session.account == cleaned:
        return {"unlocked": True, "account": cleaned, "reason": OPEN_REASON}
    return {"unlocked": False, "account": cleaned, "reason": LOCKED_REASON}
