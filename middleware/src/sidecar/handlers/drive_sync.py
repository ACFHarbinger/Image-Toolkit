"""Sidecar handler for a cloud sync plan (#908)."""

from __future__ import annotations

from typing import Any

from middleware.src.services.drive_sync.plan import plan_sync


def handle_drive_plan(params: dict[str, Any]) -> dict[str, Any]:
    return plan_sync(str(params["provider"]), [str(path) for path in params["paths"]])
