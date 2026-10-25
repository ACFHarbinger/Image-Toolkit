"""Sidecar handler for horizontal and vertical concatenation (#903)."""

from __future__ import annotations

from typing import Any

from middleware.src.services.merge.concatenate import concatenate


def handle_concatenate(params: dict[str, Any]) -> dict[str, Any]:
    return concatenate(
        [str(path) for path in params["paths"]],
        str(params["output_path"]),
        str(params["direction"]),
        int(params["spacing"]),
        str(params["align"]),
    )
