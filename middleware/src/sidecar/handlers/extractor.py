"""Sidecar handler for the video probe (#905)."""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

from middleware.src.bridge import BridgeAppError, Cancelled
from middleware.src.services.extractor.actions import cut_sheet, extract_range, snapshot_frame
from middleware.src.services.extractor.probe import probe_video
from middleware.src.sidecar.jobs import JobRegistry


def handle_probe(params: dict[str, Any]) -> dict[str, Any]:
    return probe_video(str(params["path"]))


def handle_snapshot(params: dict[str, Any], token: Any | None = None) -> dict[str, Any]:
    return snapshot_frame(
        str(params["path"]),
        float(params["time_seconds"]),
        str(params["output_path"]),
        raise_if_cancelled=_checkpoint(token),
    )


def handle_extract_range(params: dict[str, Any], token: Any | None = None) -> dict[str, Any]:
    return extract_range(
        str(params["path"]),
        float(params["start_seconds"]),
        float(params["end_seconds"]),
        str(params["output_path"]),
        raise_if_cancelled=_checkpoint(token),
    )


def _checkpoint(token: Any | None) -> Callable[[], None] | None:
    raise_if_cancelled = getattr(token, "raise_if_cancelled", None)
    return raise_if_cancelled if callable(raise_if_cancelled) else None


def start_extractor_snapshot(jobs: JobRegistry, params: dict[str, Any]) -> dict[str, Any]:
    """Queue extractor.snapshot and return its job id without blocking the reader."""
    return _start_file_job(jobs, "extractor.snapshot", params, handle_snapshot)


def start_extractor_extract_range(jobs: JobRegistry, params: dict[str, Any]) -> dict[str, Any]:
    """Queue extractor.extract_range and return its job id without blocking the reader."""
    return _start_file_job(jobs, "extractor.extract_range", params, handle_extract_range)


def _start_file_job(
    jobs: JobRegistry,
    kind: str,
    params: dict[str, Any],
    action: Callable[[dict[str, Any], Any], dict[str, Any]],
) -> dict[str, Any]:
    job_id, token = jobs.open_job(kind, params)

    def worker() -> None:
        try:
            token.raise_if_cancelled()
            result = action(params, token)
            token.raise_if_cancelled()
            jobs.transition(job_id, "completed", result=result)
        except Cancelled:
            return
        except Exception as exc:
            jobs.transition(job_id, "failed", error=_job_error(exc))

    threading.Thread(target=worker, name=f"{kind}-{job_id}", daemon=True).start()
    return {"job_id": job_id}


def _job_error(exc: Exception) -> dict[str, Any]:
    if isinstance(exc, BridgeAppError):
        return exc.envelope()
    return {
        "code": "extractor.failed",
        "retryable": False,
        "message_key": "extractor.errors.failed",
        "details": {"reason": type(exc).__name__},
    }


def handle_cut_sheet(params: dict[str, Any], token: Any | None = None) -> dict[str, Any]:
    return cut_sheet(
        str(params["path"]),
        str(params["output_dir"]),
        str(params["arrangement"]),
        int(params["frame_width"]),
        int(params["frame_height"]),
        int(params["offset_x"]),
        int(params["offset_y"]),
        int(params["spacing"]),
        bool(params["include_partial"]),
        raise_if_cancelled=_checkpoint(token),
    )


def start_extractor_cut_sheet(jobs: JobRegistry, params: dict[str, Any]) -> dict[str, Any]:
    return _start_file_job(jobs, "extractor.cut_sheet", params, handle_cut_sheet)
