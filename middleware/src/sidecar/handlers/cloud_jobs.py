"""Sidecar handlers for Cloud Jobs resources and spend (#849)."""

from __future__ import annotations

from typing import Any

from middleware.src.services.cloud_jobs.projection import (
    CloudProjection,
    resources_result,
    spend_result,
    terminate_result,
)


def handle_resources(projection: CloudProjection | None) -> dict[str, Any]:
    return resources_result(projection)


def handle_spend(projection: CloudProjection | None) -> dict[str, Any]:
    return spend_result(projection)


def handle_terminate(projection: CloudProjection | None, params: dict[str, Any]) -> dict[str, Any]:
    resource_id = str(params.get("resource_id", ""))
    attached = projection is not None and projection.daemon_attached
    return terminate_result(resource_id, daemon_attached=attached)
