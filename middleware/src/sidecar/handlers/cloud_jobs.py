"""Sidecar handler for the cloud.jobs header badge (#847)."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from middleware.src.services.cloud_jobs.badge import summary_result

BadgeRows = Iterable[tuple[str, float]]
BadgeSource = Callable[[], BadgeRows]


def handle_summary(source: BadgeSource | None) -> dict[str, Any]:
    """Return the badge. A missing source stays unavailable rather than reading a key."""
    if source is None:
        return summary_result(None)
    return summary_result(source())
