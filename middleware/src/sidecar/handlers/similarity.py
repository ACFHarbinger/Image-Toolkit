"""Sidecar handler for average-hash comparison (#904)."""

from __future__ import annotations

from typing import Any

from middleware.src.services.similarity.compare import compare_paths


def handle_compare(params: dict[str, Any]) -> dict[str, Any]:
    return compare_paths([str(path) for path in params["paths"]], int(params["threshold"]))
