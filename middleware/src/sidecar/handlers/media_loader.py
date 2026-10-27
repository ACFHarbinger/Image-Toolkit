"""Sidecar handler for media download plan and execution (#909 / #1109)."""

from __future__ import annotations

from typing import Any

from middleware.src.services.media_loader.fetch import fetch_media
from middleware.src.services.media_loader.plan import plan_download


def handle_media_plan(params: dict[str, Any]) -> dict[str, Any]:
    return plan_download(str(params["url"]), str(params["destination"]))


def handle_media_fetch(params: dict[str, Any]) -> dict[str, Any]:
    return fetch_media(str(params["url"]), str(params["destination"]))
