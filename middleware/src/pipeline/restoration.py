"""Frontend-facing dispatch for cancellable image restoration jobs."""

from __future__ import annotations

from typing import Any

from jobs import (
    RestorationResult,
    cpu_deblur_runner,
    cpu_masked_inpainting_runner,
    opencv_deblur_runner,
    opencv_masked_inpainting_runner,
    submit_restoration_job,
)
from jobs.base import JobHandle
from jobs.restoration import RestorationRunner


class RestorationPipeline:
    """Select a local restoration backend without exposing runner details to UIs."""

    def __init__(self, *, runners: dict[str, RestorationRunner] | None = None) -> None:
        self._runners = runners or {
            "deblur:pillow": cpu_deblur_runner,
            "deblur:opencv": opencv_deblur_runner,
            "masked_inpainting:pillow": cpu_masked_inpainting_runner,
            "masked_inpainting:opencv": opencv_masked_inpainting_runner,
        }

    def submit(
        self,
        operation: str,
        input_ref: str,
        *,
        backend: str = "pillow",
        options: dict[str, Any] | None = None,
    ) -> JobHandle[RestorationResult]:
        """Submit a preview job using an explicit operation/backend pair."""
        if operation not in {"deblur", "masked_inpainting"}:
            raise ValueError(f"unsupported restoration operation: {operation!r}")
        if backend not in {"pillow", "opencv"}:
            raise ValueError(f"unsupported restoration backend: {backend!r}")
        runner = self._runners.get(f"{operation}:{backend}")
        if runner is None:
            raise ValueError(f"no runner configured for {operation} with backend {backend}")
        parameters = dict(options or {})
        parameters["backend"] = backend
        return submit_restoration_job(operation, input_ref, options=parameters, runner=runner)

    def capabilities(self) -> dict[str, list[str]]:
        """Return operations and configured backends for UI capability discovery."""
        capabilities: dict[str, set[str]] = {}
        for key in self._runners:
            operation, backend = key.split(":", 1)
            capabilities.setdefault(operation, set()).add(backend)
        return {operation: sorted(backends) for operation, backends in sorted(capabilities.items())}
