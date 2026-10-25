"""Sidecar handlers for the cloud.jobs capability (#847, #848, #849)."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from middleware.src.services.cloud_jobs.badge import summary_result
from middleware.src.services.cloud_jobs.jobs_service import job_detail, list_jobs
from middleware.src.services.cloud_jobs.projection import (
    CloudProjection,
    resources_result,
    spend_result,
    terminate_result,
)

BadgeRows = Iterable[tuple[str, float]]
BadgeSource = Callable[[], BadgeRows]

JobsData = list[dict[str, Any]]
JobsSource = Callable[[], JobsData]


def handle_summary(source: BadgeSource | None) -> dict[str, Any]:
    """Return the badge. A missing source stays unavailable rather than reading a key."""
    if source is None:
        return summary_result(None)
    return summary_result(source())


def handle_list(source: JobsSource | None, params: dict[str, Any]) -> dict[str, Any]:
    """List jobs filtered by params."""
    if source is None:
        return list_jobs(None, params)
    return list_jobs(source(), params)


def handle_detail(source: JobsSource | None, params: dict[str, Any]) -> dict[str, Any]:
    """Return detail for a job."""
    if source is None:
        return job_detail(None, params)
    return job_detail(source(), params)


def handle_resources(projection: CloudProjection | None) -> dict[str, Any]:
    return resources_result(projection)


def handle_spend(projection: CloudProjection | None) -> dict[str, Any]:
    return spend_result(projection)


def handle_terminate(projection: CloudProjection | None, params: dict[str, Any]) -> dict[str, Any]:
    resource_id = str(params.get("resource_id", ""))
    attached = projection is not None and projection.daemon_attached
    return terminate_result(resource_id, daemon_attached=attached)
