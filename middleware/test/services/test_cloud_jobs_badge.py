"""Header badge projection for #847. No store file and no provider calls."""

from __future__ import annotations

from middleware.src.services.cloud_jobs.badge import header_badge, summary_result


def test_running_count_and_reserved_spend() -> None:
    running, reserved = header_badge(
        [
            ("running", 1.5),
            ("provisioning", 2.25),
            ("queued", 4.0),
            ("settling", 0.25),
            ("succeeded", 9.0),
            ("failed", 3.0),
        ]
    )
    assert running == 2
    assert reserved == 8.0


def test_missing_projection_is_unavailable() -> None:
    assert summary_result(None) == {"running": 0, "reserved_usd": 0.0, "available": False}


def test_attached_projection_is_available() -> None:
    assert summary_result([("collecting", 0.5)]) == {
        "running": 1,
        "reserved_usd": 0.5,
        "available": True,
    }
