"""Jobs table and Detail service logic for Cloud Jobs (#848)."""

from __future__ import annotations

from typing import Any

from middleware.src.bridge.envelope import BridgeAppError


def list_jobs(
    jobs_data: list[dict[str, Any]] | None,
    params: dict[str, Any],
) -> dict[str, Any]:
    """List jobs with filtering by state, provider, kind, and text search."""
    if jobs_data is None:
        return {"jobs": []}

    state_filter = params.get("state")
    provider_filter = params.get("provider")
    kind_filter = params.get("kind")
    search_filter = params.get("search", "").lower()
    limit = params.get("limit", 500)

    filtered: list[dict[str, Any]] = []
    for item in jobs_data:
        if state_filter and item.get("state") != state_filter:
            continue
        if provider_filter and item.get("provider") != provider_filter:
            continue
        if kind_filter and item.get("kind") != kind_filter:
            continue
        if search_filter:
            title = str(item.get("title", "")).lower()
            job_id = str(item.get("job_id", "")).lower()
            if search_filter not in title and search_filter not in job_id:
                continue

        filtered.append(
            {
                "job_id": str(item["job_id"]),
                "kind": str(item.get("kind", "batch")),
                "title": str(item.get("title", "")),
                "state": str(item.get("state", "queued")),
                "provider": str(item.get("provider", "aws")),
                "created_at": float(item.get("created_at", 0.0)),
                "started_at": float(item["started_at"]) if item.get("started_at") is not None else None,
                "ended_at": float(item["ended_at"]) if item.get("ended_at") is not None else None,
                "cost_usd": float(item.get("cost_usd", 0.0)),
                "shards_total": int(item.get("shards_total", 1)),
                "shards_done": int(item.get("shards_done", 0)),
            }
        )
        if len(filtered) >= limit:
            break

    return {"jobs": filtered}


def job_detail(
    jobs_data: list[dict[str, Any]] | None,
    params: dict[str, Any],
) -> dict[str, Any]:
    """Read detailed job view: timeline events, logs, metrics, spend, outputs, daemon status."""
    job_id = params.get("job_id")
    if not job_id:
        raise BridgeAppError("bridge.invalid_request", details={"reason": "job_id is required"})

    if jobs_data is None:
        raise BridgeAppError("jobs.not_found", retryable=False, details={"job_id": job_id})

    matched = next((item for item in jobs_data if item.get("job_id") == job_id), None)
    if matched is None:
        raise BridgeAppError("jobs.not_found", retryable=False, details={"job_id": job_id})

    events = [
        {
            "id": int(ev.get("id", i + 1)),
            "ts": float(ev.get("ts", matched.get("created_at", 0.0))),
            "type": str(ev.get("type", "event")),
            "data": dict(ev.get("data", {})),
        }
        for i, ev in enumerate(matched.get("events", []))
    ]

    metrics = matched.get("metrics") or {}
    spend = matched.get("spend") or {}
    daemon = matched.get("daemon_status") or {}

    return {
        "job_id": str(matched["job_id"]),
        "kind": str(matched.get("kind", "batch")),
        "title": str(matched.get("title", "")),
        "state": str(matched.get("state", "queued")),
        "provider": str(matched.get("provider", "aws")),
        "created_at": float(matched.get("created_at", 0.0)),
        "started_at": float(matched["started_at"]) if matched.get("started_at") is not None else None,
        "ended_at": float(matched["ended_at"]) if matched.get("ended_at") is not None else None,
        "events": events,
        "outputs": [str(out) for out in matched.get("outputs", [])],
        "logs": [str(log) for log in matched.get("logs", [])],
        "metrics": {
            "gpu_util_pct": float(metrics.get("gpu_util_pct", 0.0)),
            "vram_used_mb": float(metrics.get("vram_used_mb", 0.0)),
            "peak_vcpu": float(metrics.get("peak_vcpu", 0.0)),
        },
        "spend": {
            "cost_so_far_usd": float(spend.get("cost_so_far_usd", matched.get("cost_usd", 0.0))),
            "reserved_usd": float(spend.get("reserved_usd", 0.0)),
            "max_spend_usd": float(spend.get("max_spend_usd", 10.0)),
        },
        "daemon_status": {
            "lease_owner": str(daemon.get("lease_owner", "cloud-daemon")),
            "wal_depth": int(daemon.get("wal_depth", 0)),
            "last_poll_ts": float(daemon.get("last_poll_ts", matched.get("created_at", 0.0))),
        },
    }
