"""Sidecar handler for the locked auth status (#918)."""

from __future__ import annotations

from typing import Any

from middleware.src.services.auth.status import auth_status


def handle_status(params: dict[str, Any]) -> dict[str, Any]:
    return auth_status(str(params["account"]))
