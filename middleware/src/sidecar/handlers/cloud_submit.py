"""CloudJobService preview and submit for the Plan & cost sheet (#850).

No attached service means the call stays unavailable. This module does not
open the store or construct a provider on its own.
"""

from __future__ import annotations

from typing import Any

_UNAVAILABLE = "cloud submission is unavailable"
_ZERO = {
    "compute": 0.0,
    "startup": 0.0,
    "ipv4": 0.0,
    "storage": 0.0,
    "egress": 0.0,
    "retries": 0.0,
    "total": 0.0,
}


def unavailable_preview(reason: str = _UNAVAILABLE) -> dict[str, Any]:
    return {
        "available": False,
        "reason": reason,
        "job_id": "",
        "kind": "",
        "provider": "",
        "region": "",
        "mode": "",
        "storage": "",
        "data_class": "",
        "shards": 0,
        "staging_bytes": 0,
        "estimate_known": False,
        "estimate": dict(_ZERO),
        "price_age_days": None,
        "issues": [],
        "needs_ack": [],
        "capability_override": False,
    }


def handle_preview(service: Any, params: dict[str, Any]) -> dict[str, Any]:
    if service is None:
        return unavailable_preview()
    from middleware.src.cloud.spec import JobSpec

    sheet = service.preview(JobSpec.from_dict(params["spec"])).sheet()
    sheet["available"] = True
    sheet["reason"] = ""
    return sheet


def handle_submit(service: Any, params: dict[str, Any]) -> dict[str, Any]:
    if service is None:
        return {"accepted": False, "job_id": "", "reason": _UNAVAILABLE}
    from middleware.src.cloud.service import SubmissionRefused
    from middleware.src.cloud.spec import JobSpec

    try:
        job_id = service.submit(JobSpec.from_dict(params["spec"]), params.get("acknowledged") or ())
    except SubmissionRefused as exc:
        return {"accepted": False, "job_id": "", "reason": str(exc)}
    return {"accepted": True, "job_id": job_id, "reason": ""}
