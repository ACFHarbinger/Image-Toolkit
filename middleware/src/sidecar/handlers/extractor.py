"""Sidecar handler for the video probe (#905)."""

from __future__ import annotations

from typing import Any

from middleware.src.services.extractor.actions import cut_sheet, extract_range, snapshot_frame
from middleware.src.services.extractor.probe import probe_video


def handle_probe(params: dict[str, Any]) -> dict[str, Any]:
    return probe_video(str(params["path"]))


def handle_snapshot(params: dict[str, Any]) -> dict[str, Any]:
    return snapshot_frame(str(params["path"]), float(params["time_seconds"]), str(params["output_path"]))


def handle_extract_range(params: dict[str, Any]) -> dict[str, Any]:
    return extract_range(
        str(params["path"]),
        float(params["start_seconds"]),
        float(params["end_seconds"]),
        str(params["output_path"]),
    )


def handle_cut_sheet(params: dict[str, Any]) -> dict[str, Any]:
    return cut_sheet(
        str(params["path"]),
        str(params["output_dir"]),
        str(params["arrangement"]),
        int(params["frame_width"]),
        int(params["frame_height"]),
        int(params["offset_x"]),
        int(params["offset_y"]),
        int(params["spacing"]),
        bool(params["include_partial"]),
    )
