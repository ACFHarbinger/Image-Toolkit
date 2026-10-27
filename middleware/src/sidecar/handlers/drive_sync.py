"""Sidecar handler for cloud sync plan and execution (#908 / #1109)."""

from __future__ import annotations

from typing import Any

from middleware.src.services.drive_sync.plan import plan_sync
from middleware.src.services.drive_sync.sync import execute_drive_sync


def handle_drive_plan(params: dict[str, Any]) -> dict[str, Any]:
    return plan_sync(str(params["provider"]), [str(path) for path in params["paths"]])


def handle_drive_sync(params: dict[str, Any], vault_session: Any | None = None) -> dict[str, Any]:
    return execute_drive_sync(
        provider=str(params["provider"]),
        paths=[str(path) for path in params["paths"]],
        remote_folder=str(params.get("remote_folder") or "ImageToolkit"),
        dry_run=bool(params.get("dry_run", False)),
        vault_session=vault_session,
    )
