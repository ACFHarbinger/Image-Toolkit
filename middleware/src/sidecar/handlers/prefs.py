"""Sidecar handler for the settings window (#917)."""

from __future__ import annotations

from typing import Any

from middleware.src.services.prefs.describe import describe


def handle_prefs_describe(params: dict[str, Any]) -> dict[str, Any]:
    account = params.get("account", "")
    if not isinstance(account, str):
        raise ValueError("account is required")
    return describe(account)
