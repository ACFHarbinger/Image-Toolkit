"""Sidecar handler for a media download plan (#909)."""

from __future__ import annotations

from typing import Any

from middleware.src.services.media_loader.plan import plan_download


def handle_media_plan(params: dict[str, Any]) -> dict[str, Any]:
    return plan_download(str(params["url"]), str(params["destination"]))
