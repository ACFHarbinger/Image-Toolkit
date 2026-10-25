"""Resources and spend for the cloud.jobs window (#849).

Rows are injected. This module does not open ``cloud_jobs.db`` and does not
call a provider. Terminate without a daemon lease is refused.
"""

from __future__ import annotations

import calendar
import time
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

TAG_JOB = "it-job-id"
TAG_EXPIRES = "it-expires-at"
KIND_ACTUAL = "actual"
KIND_RESERVED = "reserved"


@dataclass(frozen=True)
class CloudProjection:
    """Injected rows. ``None`` resources or spend means that half is unavailable."""

    resources: tuple[Mapping[str, object], ...] | None
    known_job_ids: frozenset[str]
    spend: tuple[Mapping[str, object], ...] | None
    now: float
    daemon_attached: bool = False


def project_resources(
    rows: Iterable[Mapping[str, object]],
    known_job_ids: frozenset[str],
    now: float,
) -> list[dict[str, object]]:
    """Mark a row orphan when its job tag is unknown or its expiry has passed."""
    projected: list[dict[str, object]] = []
    for row in rows:
        tags = _tags(row.get("tags"))
        job_id = tags.get(TAG_JOB, "")
        orphan = job_id == "" or job_id not in known_job_ids or _expired(tags.get(TAG_EXPIRES), now)
        projected.append(
            {
                "provider": str(row.get("provider", "")),
                "kind": str(row.get("kind", "")),
                "resource_id": str(row.get("resource_id", "")),
                "region": str(row.get("region", "")),
                "job_id": job_id,
                "orphan": orphan,
            }
        )
    return projected


def project_spend(
    entries: Iterable[Mapping[str, object]],
    now: float,
) -> dict[str, object]:
    """Month-to-date actual spend, open reservations, and actuals by provider."""
    start = _month_start(now)
    actual = 0.0
    reserved = 0.0
    by_provider: dict[str, float] = {}
    for entry in entries:
        amount = max(0.0, float(entry.get("amount_usd", 0.0)))
        kind = str(entry.get("kind", ""))
        if kind == KIND_RESERVED:
            reserved += amount
            continue
        if kind != KIND_ACTUAL:
            continue
        ts = float(entry.get("ts", 0.0))
        if ts < start:
            continue
        actual += amount
        provider = str(entry.get("provider", ""))
        by_provider[provider] = by_provider.get(provider, 0.0) + amount
    return {
        "available": True,
        "month_actual_usd": actual,
        "reserved_usd": reserved,
        "by_provider": [{"provider": name, "actual_usd": by_provider[name]} for name in sorted(by_provider)],
    }


def resources_result(projection: CloudProjection | None) -> dict[str, object]:
    if projection is None or projection.resources is None:
        return {"available": False, "resources": []}
    return {
        "available": True,
        "resources": project_resources(projection.resources, projection.known_job_ids, projection.now),
    }


def spend_result(projection: CloudProjection | None) -> dict[str, object]:
    if projection is None or projection.spend is None:
        return {"available": False, "month_actual_usd": 0.0, "reserved_usd": 0.0, "by_provider": []}
    return project_spend(projection.spend, projection.now)


def terminate_result(resource_id: str, *, daemon_attached: bool) -> dict[str, object]:
    """Refuse a terminate that has no daemon lease. No provider call is made."""
    if not daemon_attached:
        return {"accepted": False, "resource_id": resource_id, "reason": "no daemon lease"}
    return {
        "accepted": False,
        "resource_id": resource_id,
        "reason": "terminate is waiting on the daemon command path",
    }


def _tags(value: object) -> dict[str, str]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): str(item) for key, item in value.items()}


def _expired(raw: str | None, now: float) -> bool:
    if raw is None or raw == "":
        return False
    try:
        return float(raw) < now
    except ValueError:
        return True


def _month_start(now: float) -> float:
    clock = time.gmtime(now)
    return float(calendar.timegm((clock.tm_year, clock.tm_mon, 1, 0, 0, 0, 0, 0, 0)))
