"""Cancellable job boundary for optional deblur/inpainting runtimes."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ..models import ModelUnavailable
from .base import CancelToken, JobHandle, JobProgress, ReportFn, submit_job


@dataclass(frozen=True)
class RestorationResult:
    operation: str
    input_ref: str
    output_ref: str
    metadata: dict[str, Any]


RestorationRunner = Callable[[str, dict[str, Any], CancelToken, ReportFn], str]


def submit_restoration_job(
    operation: str,
    input_ref: str,
    *,
    options: dict[str, Any] | None = None,
    runner: RestorationRunner | None = None,
) -> JobHandle[RestorationResult]:
    """Run an injected restoration backend using the shared job contract.

    The runner is deliberately injected: production code can provide an
    OpenCV/ONNX/PyTorch implementation, while tests and middleware-only
    installs remain deterministic and do not download model weights.
    """
    if operation not in {"deblur", "masked_inpainting"}:
        raise ValueError(f"unsupported restoration operation: {operation!r}")
    if not isinstance(input_ref, str) or not input_ref.strip():
        raise ValueError("input_ref must be a non-empty string")
    if operation == "masked_inpainting":
        values = options or {}
        if not values.get("mask_ref"):
            raise ValueError("masked_inpainting requires mask_ref")
        if values.get("permission_confirmed") is not True:
            raise PermissionError("confirm ownership or permission before removal")
    if runner is None:
        raise ModelUnavailable(
            f"no runtime runner configured for {operation}; install an optional restoration backend"
        )

    parameters = dict(options or {})

    def body(token: CancelToken, report: ReportFn) -> RestorationResult:
        output_ref = runner(input_ref, parameters, token, report)
        if not isinstance(output_ref, str) or not output_ref.strip():
            raise ValueError("restoration runner must return a non-empty output reference")
        report(JobProgress(1.0, f"{operation} complete", {"output_ref": output_ref}))
        return RestorationResult(operation, input_ref, output_ref, parameters)

    return submit_job(body)
