"""Resources, spend, and terminate projections (#849)."""

from __future__ import annotations

import calendar
import time

from middleware.src.services.cloud_jobs.projection import (
    project_resources,
    project_spend,
    terminate_result,
)

NOW = 1_800_000_000.0


def _previous_month(now: float) -> float:
    clock = time.gmtime(now)
    year = clock.tm_year if clock.tm_mon > 1 else clock.tm_year - 1
    month = clock.tm_mon - 1 if clock.tm_mon > 1 else 12
    return float(calendar.timegm((year, month, 15, 0, 0, 0, 0, 0, 0)))


def test_unknown_and_expired_resources_are_orphans() -> None:
    rows = [
        {
            "provider": "gcp",
            "kind": "instance",
            "resource_id": "live",
            "region": "us-central1",
            "tags": {"it-job-id": "job-1", "it-expires-at": str(NOW + 10)},
        },
        {
            "provider": "gcp",
            "kind": "instance",
            "resource_id": "gone",
            "region": "us-central1",
            "tags": {"it-job-id": "missing"},
        },
        {
            "provider": "runpod",
            "kind": "volume",
            "resource_id": "old",
            "region": "",
            "tags": {"it-job-id": "job-1", "it-expires-at": str(NOW - 1)},
        },
    ]
    projected = project_resources(rows, frozenset({"job-1"}), NOW)
    assert [row["orphan"] for row in projected] == [False, True, True]
    assert projected[1]["resource_id"] == "gone"


def test_spend_keeps_this_month_and_open_reservations() -> None:
    result = project_spend(
        [
            {"kind": "actual", "amount_usd": 2.5, "provider": "gcp", "ts": NOW},
            {"kind": "actual", "amount_usd": 9.0, "provider": "gcp", "ts": _previous_month(NOW)},
            {"kind": "actual", "amount_usd": 1.0, "provider": "runpod", "ts": NOW},
            {"kind": "reserved", "amount_usd": 4.0, "provider": "gcp", "ts": NOW},
            {"kind": "actual", "amount_usd": -3.0, "provider": "gcp", "ts": NOW},
        ],
        NOW,
    )
    assert result == {
        "available": True,
        "month_actual_usd": 3.5,
        "reserved_usd": 4.0,
        "by_provider": [
            {"provider": "gcp", "actual_usd": 2.5},
            {"provider": "runpod", "actual_usd": 1.0},
        ],
    }


def test_terminate_without_a_daemon_is_refused() -> None:
    refused = terminate_result("inst-1", daemon_attached=False)
    assert refused == {"accepted": False, "resource_id": "inst-1", "reason": "no daemon lease"}
    waiting = terminate_result("inst-1", daemon_attached=True)
    assert waiting["accepted"] is False
    assert waiting["reason"] == "terminate is waiting on the daemon command path"
