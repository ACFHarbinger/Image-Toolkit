"""Sidecar handlers for the convert capability (#894)."""

from __future__ import annotations

from typing import Any

from middleware.src.services.convert.commands import BatchConvertCommand, ConvertSingleCommand
from middleware.src.services.convert.service import ConvertService


def handle_convert(params: dict[str, Any]) -> dict[str, Any]:
    """Dispatch convert.convert onto ConvertService."""
    result = ConvertService().convert_single(
        ConvertSingleCommand(
            input_path=params["input_path"],
            output_path=params["output_path"],
            output_format=params.get("output_format", "png"),
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


def handle_convert_batch(params: dict[str, Any]) -> dict[str, Any]:
    """Dispatch convert.convert_batch onto ConvertService."""
    formats = params.get("input_formats", ["webp", "png", "jpg", "jpeg"])
    result = ConvertService().convert_batch(
        BatchConvertCommand(
            input_dir=params["input_dir"],
            output_dir=params["output_dir"],
            output_format=params.get("output_format", "png"),
            input_formats=tuple(formats),
            quality=params.get("quality", 95),
            recursive=params.get("recursive", False),
            overwrite=params.get("overwrite", True),
        )
    )
    return {
        "total_discovered": result.total_discovered,
        "succeeded": result.succeeded,
        "failed": result.failed,
        "output_paths": list(result.output_paths),
        "elapsed_seconds": result.elapsed_seconds,
        "errors": list(result.errors),
    }
