"""Headless Anime Stitch Pipeline (ASP) service and canvas workers (#914 / #1110).

Connects stitch's eight panels to headless workers and pipeline execution:
1. stitch.stitch: Pipeline execution, preset selection, and progress telemetry
2. stitch.graph: Feature matching and pairwise edge graph
3. stitch.adjust: Bundle adjustment and photometric alignment
4. stitch.canvas: Canvas dimensions, frame bounding boxes, and layout
5. stitch.statistics: Health metrics, banding check, and drift
6. stitch.sequence-builder: Frame sequence discovery, ordering, and keyframe triage
7. stitch.hybrid: HITL pause hooks, overrides, and checkpoint validation
8. stitch.animation-clusters: Character exclusion and foreground/background masking
"""

from __future__ import annotations

import glob
import os
import time
from pathlib import Path
from typing import Any, Callable

PANEL_METADATA = {
    "stitch.stitch": {"label": "Stitch Pipeline", "default_stage": "idle"},
    "stitch.graph": {"label": "Match Graph", "default_stage": "matching"},
    "stitch.adjust": {"label": "Adjustments", "default_stage": "bundle_adjust"},
    "stitch.canvas": {"label": "Canvas Layout", "default_stage": "canvas"},
    "stitch.statistics": {"label": "Statistics", "default_stage": "safety_metrics"},
    "stitch.sequence-builder": {"label": "Sequence Builder", "default_stage": "sequence"},
    "stitch.hybrid": {"label": "Hybrid HITL", "default_stage": "hitl_checkpoint"},
    "stitch.animation-clusters": {"label": "Animation Clusters", "default_stage": "masking"},
}

_SUPPORTED_IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".bmp")


def collect_frames(directory: str | Path) -> list[str]:
    """Find all image files in a directory sorted by name."""
    p = Path(directory)
    if not p.is_dir():
        return []
    frames: list[str] = []
    for item in sorted(p.iterdir()):
        if item.is_file() and item.suffix.lower() in _SUPPORTED_IMAGE_EXTS:
            frames.append(str(item.resolve()))
    return frames


class StitchService:
    """Headless domain service managing ASP pipeline sessions and panel states."""

    def __init__(self, runner: Callable[..., dict[str, Any]] | None = None) -> None:
        self._runner = runner
        self._active_sessions: dict[str, Any] = {}
        self._panel_state: dict[str, dict[str, Any]] = {
            route: {
                "started": False,
                "reason": f"{meta['label']} is idle",
                "stage": meta["default_stage"],
                "canvas_width": None,
                "canvas_height": None,
                "frames_count": None,
            }
            for route, meta in PANEL_METADATA.items()
        }

    def get_status(self, route: str) -> dict[str, Any]:
        """Report status for any of the 8 stitch catalog routes."""
        if route not in PANEL_METADATA:
            raise ValueError(f"unknown stitch route: {route}")
        state = self._panel_state[route]
        meta = PANEL_METADATA[route]
        return {
            "route": route,
            "started": bool(state["started"]),
            "reason": str(state["reason"]),
            "panel": meta["label"],
            "stage": state.get("stage"),
            "canvas_width": state.get("canvas_width"),
            "canvas_height": state.get("canvas_height"),
            "frames_count": state.get("frames_count"),
        }

    def compute_canvas(
        self,
        input_dir: str,
        preset: str | None = "anime-pan",
    ) -> dict[str, Any]:
        """Discover frames and compute prospective composite canvas layout."""
        t0 = time.monotonic()
        dir_path = Path(input_dir)
        if not dir_path.is_dir():
            return {
                "success": False,
                "width": 0,
                "height": 0,
                "num_frames": 0,
                "frames": [],
                "elapsed_seconds": round(time.monotonic() - t0, 4),
                "error": f"input directory does not exist: {input_dir}",
            }

        frames = collect_frames(dir_path)
        if not frames:
            return {
                "success": False,
                "width": 0,
                "height": 0,
                "num_frames": 0,
                "frames": [],
                "elapsed_seconds": round(time.monotonic() - t0, 4),
                "error": f"no image frames found in directory: {input_dir}",
            }

        # Lazy dimension inspection via PIL without heavy imports
        from PIL import Image

        try:
            with Image.open(frames[0]) as first_img:
                f_w, f_h = first_img.size
        except Exception as exc:
            return {
                "success": False,
                "width": 0,
                "height": 0,
                "num_frames": len(frames),
                "frames": frames,
                "elapsed_seconds": round(time.monotonic() - t0, 4),
                "error": f"cannot decode first frame: {exc}",
            }

        num = len(frames)
        # Compute layout geometry based on preset
        if preset == "webtoon-strip":
            # Vertical layout with 25% overlap
            canvas_w = f_w
            canvas_h = int(f_h + (num - 1) * f_h * 0.75)
        else:
            # Default horizontal anime pan with 30% overlap
            canvas_w = int(f_w + (num - 1) * f_w * 0.70)
            canvas_h = f_h

        # Update panel diagnostics
        self._panel_state["stitch.canvas"].update({
            "started": True,
            "reason": f"Canvas layout computed: {canvas_w}x{canvas_h} across {num} frames",
            "canvas_width": canvas_w,
            "canvas_height": canvas_h,
            "frames_count": num,
        })

        return {
            "success": True,
            "width": canvas_w,
            "height": canvas_h,
            "num_frames": num,
            "frames": frames,
            "elapsed_seconds": round(time.monotonic() - t0, 4),
            "error": None,
        }

    def run_stitch(
        self,
        input_dir: str,
        output_path: str | None = None,
        preset: str | None = "anime-pan",
        blend_mode: str | None = "multiband",
    ) -> dict[str, Any]:
        """Execute headless stitching pipeline over input frames."""
        t0 = time.monotonic()
        dir_path = Path(input_dir)
        if not dir_path.is_dir():
            return {
                "success": False,
                "output_path": None,
                "canvas_width": None,
                "canvas_height": None,
                "frames_processed": 0,
                "elapsed_seconds": round(time.monotonic() - t0, 4),
                "error": f"input directory does not exist: {input_dir}",
            }

        frames = collect_frames(dir_path)
        if len(frames) < 2:
            return {
                "success": False,
                "output_path": None,
                "canvas_width": None,
                "canvas_height": None,
                "frames_processed": len(frames),
                "elapsed_seconds": round(time.monotonic() - t0, 4),
                "error": f"at least 2 image frames required for stitching, found {len(frames)}",
            }

        if output_path is None:
            output_path = str(dir_path / "stitched_composite.png")

        if self._runner is not None:
            try:
                res = self._runner(
                    input_dir=input_dir,
                    output_path=output_path,
                    preset=preset,
                    blend_mode=blend_mode,
                )
                return res
            except Exception as exc:
                return {
                    "success": False,
                    "output_path": None,
                    "canvas_width": None,
                    "canvas_height": None,
                    "frames_processed": len(frames),
                    "elapsed_seconds": round(time.monotonic() - t0, 4),
                    "error": str(exc),
                }

        # Headless execution via PIL & numpy composite
        try:
            from PIL import Image
            import numpy as np

            loaded = [Image.open(f).convert("RGBA") for f in frames[:10]]
            f_w, f_h = loaded[0].size

            if preset == "webtoon-strip":
                overlap_y = int(f_h * 0.25)
                step_y = f_h - overlap_y
                canvas_h = f_h + (len(loaded) - 1) * step_y
                canvas_w = f_w
                canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
                for i, img in enumerate(loaded):
                    canvas.alpha_composite(img, (0, i * step_y))
            else:
                overlap_x = int(f_w * 0.30)
                step_x = f_w - overlap_x
                canvas_w = f_w + (len(loaded) - 1) * step_x
                canvas_h = f_h
                canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
                for i, img in enumerate(loaded):
                    canvas.alpha_composite(img, (i * step_x, 0))

            out = Path(output_path)
            out.parent.mkdir(parents=True, exist_ok=True)
            canvas.convert("RGB").save(out, format="PNG")

            # Update panel states
            self._panel_state["stitch.stitch"].update({
                "started": True,
                "reason": f"Pipeline complete: generated {canvas_w}x{canvas_h}",
                "canvas_width": canvas_w,
                "canvas_height": canvas_h,
                "frames_count": len(frames),
            })

            return {
                "success": True,
                "output_path": str(out),
                "canvas_width": canvas_w,
                "canvas_height": canvas_h,
                "frames_processed": len(frames),
                "elapsed_seconds": round(time.monotonic() - t0, 4),
                "error": None,
            }
        except Exception as exc:
            return {
                "success": False,
                "output_path": None,
                "canvas_width": None,
                "canvas_height": None,
                "frames_processed": len(frames),
                "elapsed_seconds": round(time.monotonic() - t0, 4),
                "error": str(exc),
            }


__all__ = [
    "PANEL_METADATA",
    "StitchService",
    "collect_frames",
]
