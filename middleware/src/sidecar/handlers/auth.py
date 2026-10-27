"""Sidecar handlers for the C++ vault session (#1106)."""

from __future__ import annotations

from typing import Any

from middleware.src.services.auth.hub import VaultHub


def handle_status(hub: VaultHub, params: dict[str, Any]) -> dict[str, Any]:
    return hub.status(str(params["account"]))


def handle_unlock(hub: VaultHub, params: dict[str, Any]) -> dict[str, Any]:
    return hub.unlock(str(params["account"]), str(params["password"]))


def handle_lock(hub: VaultHub, params: dict[str, Any]) -> dict[str, Any]:
    return hub.lock(str(params["account"]))
