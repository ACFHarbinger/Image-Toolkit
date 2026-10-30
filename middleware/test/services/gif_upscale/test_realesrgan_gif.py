"""Real-ESRGAN registry rows do not download or run a network in this test."""

from __future__ import annotations

from middleware.src.services.media.gif_upscale.registry import list_algorithms
from middleware.src.services.media.subtabs import resample
from PIL import Image


def test_family_is_listed_and_offline_anime_does_not_run(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("IMAGE_TOOLKIT_GIF_UPSCALE_WEIGHTS_POLICY", "offline")
    monkeypatch.setattr(
        "middleware.src.services.media.gif_upscale.neural.realesrgan._anime_cached",
        lambda: False,
    )
    rows = {row["id"]: row for row in list_algorithms()}
    assert rows["realesrgan-anime-6b"]["available"] is False
    assert "offline" in rows["realesrgan-anime-6b"]["reason"]
    assert rows["realesrgan-x4plus"]["available"] is False
    assert "23-block" in rows["realesrgan-x4plus"]["reason"]
    assert rows["realesrgan-x2plus"]["supports_scale"] == [2.0]
    assert "SRVGG" in rows["realesrgan-general-x4v3"]["reason"]
    assert rows["realesrgan-animevideov3"]["content"] == "anime"

    source = tmp_path / "clip.gif"
    Image.new("RGB", (4, 4), (20, 30, 40)).save(source, format="GIF")
    output = tmp_path / "out.gif"
    result = resample(
        {
            "input_path": str(source),
            "output_path": str(output),
            "factor": 4,
            "algorithm": "realesrgan-anime-6b",
        }
    )
    assert result["success"] is False
    assert "offline" in result["message"]
    assert not output.exists()
