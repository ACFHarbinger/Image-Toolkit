"""Intra-file progress for one GIF resample."""

from __future__ import annotations

from middleware.src.services.media.gif_upscale.pipeline import resample_gif
from PIL import Image


def _animated(path, frames: int = 2) -> None:
    images = []
    for index in range(frames):
        color = (255, 0, 0) if index % 2 == 0 else (0, 0, 255)
        images.append(Image.new("RGB", (4, 2), color))
    images[0].save(
        path,
        format="GIF",
        save_all=True,
        append_images=images[1:],
        duration=40,
        loop=0,
    )
    for image in images:
        image.close()


def test_lanczos_gif_reports_decode_scale_and_encode(tmp_path) -> None:
    source = tmp_path / "clip.gif"
    output = tmp_path / "out.gif"
    _animated(source)
    events: list[tuple[str, int, int]] = []

    def progress(stage: str, done: int, total: int) -> None:
        events.append((stage, done, total))

    result = resample_gif(
        str(source),
        str(output),
        {"algorithm": "lanczos", "mode": "factor", "factor": 2, "progress": progress},
    )
    assert result["success"] is True
    stages = [stage for stage, _done, _total in events]
    assert "decode" in stages
    assert "encode" in stages
    assert stages.count("scale") > 1
    assert stages.index("decode") < stages.index("scale") < stages.index("encode")
    assert ("decode", 0, 1) in events and ("decode", 1, 1) in events
    assert all(total == 2 for _stage, _done, total in events if _stage == "scale")


def test_subtabs_resample_prints_progress_on_stderr(tmp_path, capsys) -> None:
    from middleware.src.services.media.subtabs import resample

    source = tmp_path / "clip.gif"
    output = tmp_path / "out.gif"
    _animated(source)
    result = resample(
        {
            "input_path": str(source),
            "output_path": str(output),
            "mode": "factor",
            "factor": 1,
            "algorithm": "lanczos",
        }
    )
    assert result["success"] is True
    lines = [line for line in capsys.readouterr().err.splitlines() if line.startswith("IT_PROGRESS\t")]
    stages = {line.split("\t")[1] for line in lines}
    assert {"decode", "scale", "encode"} <= stages
    assert sum(1 for line in lines if line.startswith("IT_PROGRESS\tscale\t")) > 1
