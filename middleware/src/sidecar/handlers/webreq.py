"""Sidecar handlers for the webreq capability (B-02 / #907)."""

from __future__ import annotations

from typing import Any

from middleware.src.services.webreq.commands import (
    ActionItem,
    ExecuteCommand,
    RequestItem,
    SequenceCommand,
)
from middleware.src.services.webreq.service import WebRequestsService


def handle_webreq_execute(
    service: WebRequestsService | None,
    params: dict[str, Any],
) -> dict[str, Any]:
    """Dispatch webreq.execute onto WebRequestsService."""
    svc = service or WebRequestsService()
    cmd = ExecuteCommand(
        url=params["url"],
        method=params.get("method", "GET"),
        headers=params.get("headers") or {},
        body=params.get("body", ""),
        timeout_seconds=int(params.get("timeout_seconds", 15)),
    )
    res = svc.execute(cmd)
    return {
        "url": res.url,
        "status_code": res.status_code,
        "status_text": res.status_text,
        "headers": res.headers,
        "content_type": res.content_type,
        "body": res.body,
        "duration_ms": res.duration_ms,
        "error": res.error,
    }


def handle_webreq_sequence(
    service: WebRequestsService | None,
    params: dict[str, Any],
) -> dict[str, Any]:
    """Dispatch webreq.sequence onto WebRequestsService."""
    svc = service or WebRequestsService()
    raw_reqs = params.get("requests", [])
    raw_acts = params.get("actions", [])

    requests = [
        RequestItem(
            type=r.get("type", "GET"),
            param=r.get("param", ""),
            headers=r.get("headers") or {},
        )
        for r in raw_reqs
    ]
    actions = [
        ActionItem(
            type=a.get("type", "Print Response Status Code"),
            param=a.get("param", ""),
        )
        for a in raw_acts
    ]

    cmd = SequenceCommand(
        base_url=params["base_url"],
        requests=requests,
        actions=actions,
        timeout_seconds=int(params.get("timeout_seconds", 15)),
    )
    res = svc.sequence(cmd)
    return {
        "status": res.status,
        "base_url": res.base_url,
        "total_requests": res.total_requests,
        "completed_requests": res.completed_requests,
        "logs": res.logs,
        "items": [
            {
                "index": it.index,
                "url": it.url,
                "method": it.method,
                "status_code": it.status_code,
                "saved_path": it.saved_path,
                "error": it.error,
            }
            for it in res.items
        ],
        "message": res.message,
    }
