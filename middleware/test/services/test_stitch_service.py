"""Tests for StitchService and sidecar handlers (#914 / #1110)."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from middleware.src.services.stitch.service import (
    PANEL_METADATA,
    StitchService,
    collect_frames,
)
from middleware.src.sidecar.server import SidecarServer
from PIL import Image


def _create_sample_frames(directory: Path, count: int = 3, w: int = 100, h: int = 80) -> list[Path]:
    directory.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for i in range(count):
        p = directory / f"frame_{i:03d}.png"
        img = Image.new("RGB", (w, h), color=(i * 40, 100, 150))
        img.save(p)
        paths.append(p)
    return paths


def test_collect_frames(tmp_path: Path) -> None:
    assert collect_frames(tmp_path) == []
    created = _create_sample_frames(tmp_path, count=4)
    found = collect_frames(tmp_path)
    assert len(found) == 4
    assert [Path(f).name for f in found] == [p.name for p in created]


@pytest.mark.parametrize("route", sorted(PANEL_METADATA.keys()))
def test_all_eight_panels_have_valid_status(route: str) -> None:
    service = StitchService()
    status = service.get_status(route)
    assert status["route"] == route
    assert status["started"] is False
    assert status["panel"] == PANEL_METADATA[route]["label"]
    assert status["stage"] == PANEL_METADATA[route]["default_stage"]


def test_unknown_route_raises() -> None:
    service = StitchService()
    with pytest.raises(ValueError, match="unknown stitch route"):
        service.get_status("stitch.invalid")


def test_compute_canvas_missing_dir(tmp_path: Path) -> None:
    service = StitchService()
    res = service.compute_canvas(str(tmp_path / "nonexistent"))
    assert res["success"] is False
    assert "does not exist" in res["error"]


def test_compute_canvas_empty_dir(tmp_path: Path) -> None:
    service = StitchService()
    res = service.compute_canvas(str(tmp_path))
    assert res["success"] is False
    assert "no image frames found" in res["error"]


def test_compute_canvas_presets(tmp_path: Path) -> None:
    _create_sample_frames(tmp_path, count=3, w=100, h=80)
    service = StitchService()

    # Anime pan (horizontal)
    pan = service.compute_canvas(str(tmp_path), preset="anime-pan")
    assert pan["success"] is True
    assert pan["num_frames"] == 3
    assert pan["height"] == 80
    assert pan["width"] > 100  # Horizontal expansion

    # Webtoon strip (vertical)
    strip = service.compute_canvas(str(tmp_path), preset="webtoon-strip")
    assert strip["success"] is True
    assert strip["num_frames"] == 3
    assert strip["width"] == 100
    assert strip["height"] > 80  # Vertical expansion


def _patch_pipeline(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    """Replace AnimeStitchPipeline so run_stitch never builds a montage."""
    seen: list[list[str]] = []

    class _Pipeline:
        def __init__(self, *args: object, **kwargs: object) -> None:
            del args, kwargs

        def run(self, frames: list[str], output_path: str):
            seen.append(list(frames))
            dest = Path(output_path)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b"\x89PNG\r\n")
            return type("Image", (), {"size": (8, 8)})()

    monkeypatch.setattr(
        "middleware.src.services.stitch.service._pipeline_class",
        lambda: _Pipeline,
    )
    return seen


def test_run_stitch_headless(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    frames_dir = tmp_path / "frames"
    created = _create_sample_frames(frames_dir, count=3, w=60, h=40)
    out_file = tmp_path / "out" / "stitched.png"
    seen = _patch_pipeline(monkeypatch)

    service = StitchService()
    result = service.run_stitch(str(frames_dir), output_path=str(out_file), preset="anime-pan")
    assert result["success"] is True
    assert result["frames_processed"] == len(list(frames_dir.iterdir()))
    assert seen == [[str(p.resolve()) for p in created]]
    assert out_file.is_file()
    assert out_file.stat().st_size > 0

    stat = service.get_status("stitch.stitch")
    assert stat["started"] is True
    assert stat["frames_count"] == 3


def test_run_stitch_headless_keeps_eleven_frames(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    frames_dir = tmp_path / "frames11"
    frames_dir.mkdir()
    created: list[Path] = []
    for i in range(11):
        path = frames_dir / f"frame_{i:03d}.png"
        path.write_bytes(b"")
        created.append(path)
    out_file = tmp_path / "out11.png"
    seen = _patch_pipeline(monkeypatch)

    result = StitchService().run_stitch(str(frames_dir), output_path=str(out_file))
    assert result["success"] is True
    assert result["frames_processed"] == 11
    assert seen == [[str(p.resolve()) for p in created]]


def test_sidecar_stitch_dispatch(tmp_path: Path) -> None:
    frames_dir = tmp_path / "frames"
    _create_sample_frames(frames_dir, count=2, w=50, h=50)

    def _runner(**kwargs: object) -> dict[str, object]:
        return {
            "success": True,
            "output_path": kwargs.get("output_path"),
            "canvas_width": 50,
            "canvas_height": 50,
            "frames_processed": 2,
            "elapsed_seconds": 0.0,
            "error": None,
        }

    server = SidecarServer(
        stdin=io.StringIO(),
        stdout=io.StringIO(),
        stitch_service=StitchService(runner=_runner),
    )
    server.handle_frame({
        "jsonrpc": "2.0",
        "id": "1",
        "method": "system.handshake",
        "params": {
            "protocol": "image-toolkit-bridge",
            "client": {"name": "test", "version": "1.0.0"},
        },
    })

    # Status
    status_res = server.handle_frame({
        "jsonrpc": "2.0",
        "id": "2",
        "method": "stitch.status",
        "params": {"route": "stitch.graph"},
    })
    assert status_res["result"]["route"] == "stitch.graph"
    assert status_res["result"]["panel"] == "Match Graph"

    # Canvas
    canvas_res = server.handle_frame({
        "jsonrpc": "2.0",
        "id": "3",
        "method": "stitch.canvas",
        "params": {"input_dir": str(frames_dir)},
    })
    assert canvas_res["result"]["success"] is True
    assert canvas_res["result"]["num_frames"] == 2

    # Run
    run_res = server.handle_frame({
        "jsonrpc": "2.0",
        "id": "4",
        "method": "stitch.run",
        "params": {
            "input_dir": str(frames_dir),
            "output_path": str(tmp_path / "comp.png"),
        },
    })
    assert run_res["result"]["success"] is True
    assert run_res["result"]["frames_processed"] == 2
