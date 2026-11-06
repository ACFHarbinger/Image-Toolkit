"""Sidecar handlers for the stitch capability (E-01 / #914 / #1110)."""

from __future__ import annotations

from typing import Any

from middleware.src.services.stitch.service import StitchService


def handle_stitch_status(service: StitchService | None, params: dict[str, Any]) -> dict[str, Any]:
    if service is None:
        service = StitchService()
    return service.get_status(str(params["route"]))


def handle_stitch_run(service: StitchService | None, params: dict[str, Any]) -> dict[str, Any]:
    if service is None:
        service = StitchService()
    return service.run_stitch(
        input_dir=str(params["input_dir"]),
        output_path=params.get("output_path"),
        preset=params.get("preset"),
        blend_mode=params.get("blend_mode"),
    )


def handle_stitch_canvas(service: StitchService | None, params: dict[str, Any]) -> dict[str, Any]:
    if service is None:
        service = StitchService()
    return service.compute_canvas(
        input_dir=str(params["input_dir"]),
        preset=params.get("preset"),
    )


__all__ = [
    "handle_stitch_canvas",
    "handle_stitch_run",
    "handle_stitch_status",
]
