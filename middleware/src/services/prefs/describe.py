"""Describe the settings window without opening a store (#917).

The account is stripped and then required. It is not echoed and it is not
used to touch the C++ vault session, ``~/.image-toolkit``, or a database.
"""

from __future__ import annotations

from typing import Any

SECTIONS: tuple[str, ...] = (
    "appearance",
    "profiles",
    "shortcuts",
    "tab_config",
    "credentials",
    "reset",
)
REASON = "credentials stay on the C++ vault session"


def describe(account: str) -> dict[str, Any]:
    if not isinstance(account, str) or not account.strip():
        raise ValueError("account is required")
    return {
        "sections": list(SECTIONS),
        "credentials_changed": False,
        "reason": REASON,
    }
