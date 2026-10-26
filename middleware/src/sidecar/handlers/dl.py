"""Sidecar handler for the training-run inspect (#912)."""

from __future__ import annotations

from typing import Any

from middleware.src.services.dl.inspect import inspect_run


def handle_inspect(params: dict[str, Any]) -> dict[str, Any]:
    return inspect_run(str(params["run_dir"]))
