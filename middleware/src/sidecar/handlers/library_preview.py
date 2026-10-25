"""Sidecar handlers for library preview inspection (#895)."""

from __future__ import annotations

from typing import Any

from middleware.src.services.library_preview.preview import describe_paths, difference_map, frame_png


def handle_describe(params: dict[str, Any]) -> dict[str, Any]:
    return describe_paths([str(path) for path in params["paths"]])


def handle_frame(params: dict[str, Any]) -> dict[str, Any]:
    return frame_png(str(params["path"]))


def handle_difference(params: dict[str, Any]) -> dict[str, Any]:
    return difference_map(str(params["left"]), str(params["right"]), int(params["boost"]))
