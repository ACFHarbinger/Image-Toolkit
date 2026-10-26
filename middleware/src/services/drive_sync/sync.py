"""Drive synchronization execution engine (#908 / #1109)."""

from __future__ import annotations

import os
import time
from typing import Any

from middleware.src.services.drive_sync.plan import plan_sync

_SUPPORTED_PROVIDERS = {"google_drive", "dropbox", "onedrive"}


def execute_drive_sync(
    provider: str,
    paths: list[str],
    remote_folder: str = "ImageToolkit",
    dry_run: bool = False,
    vault_session: Any | None = None,
    syncer: Any | None = None,
) -> dict[str, Any]:
    """Execute sync for the given paths to the cloud provider."""
    t0 = time.monotonic()

    # Validation via plan rules
    try:
        plan_sync(provider, paths)
    except ValueError as exc:
        return {
            "success": False,
            "provider": provider,
            "synced_count": 0,
            "elapsed_seconds": round(time.monotonic() - t0, 4),
            "errors": [str(exc)],
        }

    valid_paths: list[str] = []
    missing_paths: list[str] = []
    for p in paths:
        if os.path.exists(p):
            valid_paths.append(p)
        else:
            missing_paths.append(f"Path does not exist: {p}")

    if missing_paths and not valid_paths:
        return {
            "success": False,
            "provider": provider,
            "synced_count": 0,
            "elapsed_seconds": round(time.monotonic() - t0, 4),
            "errors": missing_paths,
        }

    if syncer is not None:
        try:
            count = syncer(provider, valid_paths, remote_folder=remote_folder, dry_run=dry_run)
            return {
                "success": True,
                "provider": provider,
                "synced_count": int(count),
                "elapsed_seconds": round(time.monotonic() - t0, 4),
                "errors": missing_paths,
            }
        except Exception as exc:
            return {
                "success": False,
                "provider": provider,
                "synced_count": 0,
                "elapsed_seconds": round(time.monotonic() - t0, 4),
                "errors": [str(exc)] + missing_paths,
            }

    if dry_run:
        return {
            "success": True,
            "provider": provider,
            "synced_count": len(valid_paths),
            "elapsed_seconds": round(time.monotonic() - t0, 4),
            "errors": missing_paths,
        }

    # Vault credentials check
    has_credentials = False
    if vault_session is not None:
        try:
            cred_key = f"cloud_{provider}_token"
            has_secret = hasattr(vault_session, "get_secret") and vault_session.get_secret(cred_key)
            has_unlock = hasattr(vault_session, "is_unlocked") and vault_session.is_unlocked()
            if has_secret or has_unlock:
                has_credentials = True
        except Exception:
            has_credentials = False

    if not has_credentials:
        return {
            "success": False,
            "provider": provider,
            "synced_count": 0,
            "elapsed_seconds": round(time.monotonic() - t0, 4),
            "errors": [f"Provider {provider} requires authenticated vault session credentials"] + missing_paths,
        }

    # A vault session is not an upload. Without an injected syncer nothing is sent.
    return {
        "success": False,
        "provider": provider,
        "synced_count": 0,
        "elapsed_seconds": round(time.monotonic() - t0, 4),
        "errors": ["provider upload is unavailable"] + missing_paths,
    }
