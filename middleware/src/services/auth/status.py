"""Locked session status (#918).

The vault is not opened. Unlock stays on the C++ session. The account is
checked after strip and is never copied into an error string.
"""

from __future__ import annotations

from typing import Any

REASON = "unlock stays on the C++ session"


def auth_status(account: str) -> dict[str, Any]:
    cleaned = account.strip()
    if not cleaned:
        raise ValueError("account is empty")
    return {"unlocked": False, "account": cleaned, "reason": REASON}
