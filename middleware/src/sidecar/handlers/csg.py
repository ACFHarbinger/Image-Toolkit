"""Sidecar handlers for the csg capability (E-03 / #916).

Each request builds its frozen command and routes through the canonical
``CsgService`` (Phase C home). Validation errors answer
``csg.invalid_params``; a solver failure is a failed result, not a
bridge error. Tests monkeypatch the service factory — no CSG solver
runs, no subprocess spawns.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from middleware.src.services.base import CommandValidationError
from middleware.src.services.csg.commands import (
    ArapDeformCommand,
    ColorizeReferenceCommand,
    ColorizeScribbleCommand,
    TemporalPropagateCommand,
)


def csg_service() -> Any:
    """Canonical service bound to the in-repo CSG solver.

    A missing solver returns ``success=False`` with
    ``CSG solver is unavailable``. It does not report a finished image.
    """
    from middleware.src.services.csg.delegate import SubmoduleCsgDelegate
    from middleware.src.services.csg.service import CsgService

    return CsgService(csg_delegate=SubmoduleCsgDelegate())


def _invalid_params(field: str, message: str) -> Any:
    from middleware.src.bridge import BridgeAppError

    return BridgeAppError("csg.invalid_params", details={"field": field, "reason": message})


def _payload(result: Any) -> dict[str, Any]:
    def _jsonable(value: Any) -> Any:
        if isinstance(value, (list, tuple)):
            return [_jsonable(item) for item in value]
        if isinstance(value, dict):
            return {key: _jsonable(item) for key, item in value.items()}
        return value

    return {key: _jsonable(value) for key, value in asdict(result).items()}


def _points(value: Any, field: str) -> tuple[tuple[float, float], ...]:
    if not isinstance(value, (list, tuple)) or not value:
        raise _invalid_params(field, "expected at least one [x, y] pair")
    points: list[tuple[float, float]] = []
    for pair in value:
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            raise _invalid_params(field, "each point must be an [x, y] pair")
        points.append((float(pair[0]), float(pair[1])))
    return tuple(points)


def handle_colorize_scribble(service: Any, params: dict[str, Any]) -> dict[str, Any]:
    command = ColorizeScribbleCommand(
        lineart_path=str(params["lineart_path"]),
        scribble_path=str(params["scribble_path"]),
        output_path=params.get("output_path") or None,
        intensity=float(params.get("intensity", 1.0)),
        use_screentone=bool(params.get("use_screentone", False)),
    )
    return _payload(_run(service, "colorize_scribble", command))


def handle_colorize_reference(service: Any, params: dict[str, Any]) -> dict[str, Any]:
    command = ColorizeReferenceCommand(
        lineart_path=str(params["lineart_path"]),
        reference_path=str(params["reference_path"]),
        output_path=params.get("output_path") or None,
        epsilon=float(params.get("epsilon", 0.01)),
        max_iter=int(params.get("max_iter", 100)),
    )
    return _payload(_run(service, "colorize_reference", command))


def handle_arap_deform(service: Any, params: dict[str, Any]) -> dict[str, Any]:
    command = ArapDeformCommand(
        image_path=str(params["image_path"]),
        control_points=_points(params["control_points"], "control_points"),
        target_points=_points(params["target_points"], "target_points"),
        output_path=params.get("output_path") or None,
        mesh_resolution=int(params.get("mesh_resolution", 32)),
    )
    return _payload(_run(service, "arap_deform", command))


def handle_propagate_sequence(service: Any, params: dict[str, Any]) -> dict[str, Any]:
    frame_paths = params.get("frame_paths") or []
    if not frame_paths:
        raise _invalid_params("frame_paths", "at least one frame path is required")
    command = TemporalPropagateCommand(
        frame_paths=tuple(str(path) for path in frame_paths),
        keyframe_index=int(params.get("keyframe_index", 0)),
        keyframe_color_path=str(params.get("keyframe_color_path", "")),
        output_dir=params.get("output_dir") or None,
    )
    return _payload(_run(service, "propagate_sequence", command))


def _run(service: Any, method: str, command: Any) -> Any:
    try:
        return getattr(service, method)(command)
    except CommandValidationError as exc:
        raise _invalid_params(str(exc.details.get("field", "")), str(exc)) from exc


__all__ = [
    "csg_service",
    "handle_arap_deform",
    "handle_colorize_reference",
    "handle_colorize_scribble",
    "handle_propagate_sequence",
]
