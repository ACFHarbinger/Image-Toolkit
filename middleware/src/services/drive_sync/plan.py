"""Record a cloud sync plan without contacting a provider (#908)."""

from __future__ import annotations

from typing import Any

_PROVIDERS = {"google_drive", "dropbox", "onedrive"}
_MAX_PATHS = 32


def plan_sync(provider: str, paths: list[str]) -> dict[str, Any]:
    if provider not in _PROVIDERS:
        raise ValueError("unknown provider")
    if not 1 <= len(paths) <= _MAX_PATHS:
        raise ValueError("plan accepts 1 to 32 paths")
    if any(not path.strip() for path in paths):
        raise ValueError("path is empty")
    return {
        "submitted": False,
        "provider": provider,
        "count": len(paths),
        "reason": "sync is not sent",
    }
