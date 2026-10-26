"""Sidecar handlers for the convert capability (#894)."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from middleware.src.bridge import BridgeAppError, Cancelled
from middleware.src.services.base import CommandValidationError
from middleware.src.services.convert.commands import BatchConvertCommand, ConvertSingleCommand
from middleware.src.services.convert.handlers import SUPPORTED_FORMATS
from middleware.src.services.convert.selected import list_directory, run_selected
from middleware.src.services.convert.service import ConvertService
from middleware.src.sidecar.jobs import JobRegistry

_JPEG = frozenset({"jpg", "jpeg"})


def handle_convert(params: dict[str, Any]) -> dict[str, Any]:
    """Dispatch convert.convert onto ConvertService."""
    try:
        output_format = resolve_output_format(params["output_path"], params.get("output_format"))
    except CommandValidationError as exc:
        return _failed_single(params, str(exc))
    result = ConvertService().convert_single(
        ConvertSingleCommand(
            input_path=params["input_path"],
            output_path=params["output_path"],
            output_format=output_format,
            quality=params.get("quality", 95),
            overwrite=params.get("overwrite", True),
        )
    )
    return {
        "input_path": result.input_path,
        "output_path": result.output_path,
        "success": result.success,
        "size_bytes": result.size_bytes,
        "elapsed_seconds": result.elapsed_seconds,
        "error": result.error,
    }


def handle_list_dir(params: dict[str, Any]) -> dict[str, Any]:
    """List image and video files in one directory."""
    return list_directory(str(params["directory"]))


def start_convert_batch(jobs: JobRegistry, params: dict[str, Any]) -> dict[str, Any]:
    """Queue convert.convert_batch and return its job id without blocking the reader."""
    if _selected_batch(params):
        return _start_selected_batch(jobs, params)
    job_id, token = jobs.open_job("convert.batch", params)

    def worker() -> None:
        try:
            command = _batch_command(params)

            def checkpoint(done: int, total: int) -> None:
                token.raise_if_cancelled()
                jobs.transition(job_id, "running", progress={"done": done, "total": total})

            result = ConvertService().convert_batch(command, checkpoint=checkpoint)
            jobs.transition(
                job_id,
                "completed",
                progress={"done": result.total_discovered, "total": result.total_discovered},
                result={
                    "total_discovered": result.total_discovered,
                    "succeeded": result.succeeded,
                    "failed": result.failed,
                    "output_paths": list(result.output_paths),
                    "elapsed_seconds": result.elapsed_seconds,
                    "errors": list(result.errors),
                },
            )
        except Cancelled:
            return
        except Exception as exc:
            jobs.transition(job_id, "failed", error=_job_error(exc))

    threading.Thread(target=worker, name=f"convert-batch-{job_id}", daemon=True).start()
    return {"job_id": job_id}


def _selected_batch(params: dict[str, Any]) -> bool:
    action = params.get("action") or "convert"
    return "paths" in params or action != "convert"


def _start_selected_batch(jobs: JobRegistry, params: dict[str, Any]) -> dict[str, Any]:
    """Loop the selection on a worker thread and stop when the job is cancelled."""
    job_id, token = jobs.open_job("convert.batch", params)

    def worker() -> None:
        try:

            def before_file(done: int, total: int) -> None:
                token.raise_if_cancelled()
                jobs.transition(job_id, "running", progress={"done": done, "total": total})

            result = run_selected(params, before_file)
            jobs.transition(
                job_id,
                "completed",
                progress={"done": result["total_discovered"], "total": result["total_discovered"]},
                result=result,
            )
        except Cancelled:
            return
        except Exception as exc:
            jobs.transition(job_id, "failed", error=_job_error(exc))

    threading.Thread(target=worker, name=f"convert-selected-{job_id}", daemon=True).start()
    return {"job_id": job_id}


def resolve_output_format(output_path: str, explicit: str | None) -> str:
    """Use the requested format, or the output suffix when the request omits one.

    A suffix that names a different format than the request is rejected so PNG
    bytes are not written to a ``.jpg`` path.
    """
    suffix = Path(output_path).suffix.lower().lstrip(".")
    if explicit:
        fmt = explicit.lower().lstrip(".")
    elif suffix in SUPPORTED_FORMATS:
        fmt = suffix
    elif suffix:
        raise CommandValidationError(f"Unsupported output format .{suffix}", field="output_format")
    else:
        fmt = "png"
    if fmt not in SUPPORTED_FORMATS:
        raise CommandValidationError("Unsupported output format", field="output_format")
    if suffix in SUPPORTED_FORMATS and _family(fmt) != _family(suffix):
        raise CommandValidationError(
            f"Output format {fmt} does not match .{suffix}",
            field="output_format",
        )
    return fmt


def _batch_command(params: dict[str, Any]) -> BatchConvertCommand:
    formats = params.get("input_formats", ["webp", "png", "jpg", "jpeg"])
    output_format = params.get("output_format", "png")
    if not isinstance(output_format, str):
        raise CommandValidationError("Unsupported output format", field="output_format")
    output_format = output_format.lower().lstrip(".")
    if output_format not in SUPPORTED_FORMATS:
        raise CommandValidationError("Unsupported output format", field="output_format")
    return BatchConvertCommand(
        input_dir=params["input_dir"],
        output_dir=params["output_dir"],
        output_format=output_format,
        input_formats=tuple(formats),
        quality=params.get("quality", 95),
        recursive=params.get("recursive", False),
        overwrite=params.get("overwrite", True),
    )


def _family(fmt: str) -> str:
    return "jpeg" if fmt in _JPEG else fmt


def _failed_single(params: dict[str, Any], error: str) -> dict[str, Any]:
    return {
        "input_path": params.get("input_path", ""),
        "output_path": params.get("output_path", ""),
        "success": False,
        "size_bytes": 0,
        "elapsed_seconds": 0.0,
        "error": error,
    }


def _job_error(exc: Exception) -> dict[str, Any]:
    if isinstance(exc, BridgeAppError):
        return exc.envelope()
    details: dict[str, Any] = {"reason": type(exc).__name__}
    if isinstance(exc, CommandValidationError) and exc.details.get("field"):
        details["field"] = exc.details["field"]
    return {
        "code": "convert.failed",
        "retryable": False,
        "message_key": "convert.errors.failed",
        "details": details,
    }
