"""Sidecar handler for the video probe (#905)."""

from __future__ import annotations

from typing import Any

from middleware.src.services.extractor.probe import probe_video


def handle_probe(params: dict[str, Any]) -> dict[str, Any]:
    return probe_video(str(params["path"]))
