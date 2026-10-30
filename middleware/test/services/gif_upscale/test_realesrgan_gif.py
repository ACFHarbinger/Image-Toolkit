"""Real-ESRGAN registry rows do not download or run a network in this test."""

from __future__ import annotations

from middleware.src.services.media.gif_upscale.registry import list_algorithms
from middleware.src.services.media.subtabs import resample
from PIL import Image


def test_family_is_listed_and_offline_anime_does_not_run(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("IMAGE_TOOLKIT_GIF_UPSCALE_WEIGHTS_POLICY", "offline")
    monkeypatch.setattr(
        "middleware.src.services.media.gif_upscale.neural.realesrgan._local_checkpoint",
        lambda: None,
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


def test_offline_passes_the_gif_cache_file_and_skips_the_hub(tmp_path, monkeypatch) -> None:
    import numpy as np
    from middleware.src.services.media.gif_upscale.neural.realesrgan import _upscale_anime

    cache = tmp_path / "weights"
    cache.mkdir()
    checkpoint = cache / "RealESRGAN_x4plus_anime_6B.pth"
    checkpoint.write_bytes(b"local-weights")
    monkeypatch.setenv("IMAGE_TOOLKIT_GIF_UPSCALE_WEIGHTS_POLICY", "offline")
    monkeypatch.setenv("IMAGE_TOOLKIT_GIF_UPSCALE_CACHE", str(cache))
    seen: dict[str, object] = {}

    class _Wrapper:
        def __init__(self, *args, **kwargs) -> None:
            del args
            seen.update(kwargs)

        def upscale(self, image):
            return np.zeros((image.shape[0] * 4, image.shape[1] * 4, 3), dtype=np.uint8)

    def _hub(*_args, **_kwargs):
        raise AssertionError("offline load contacted Hugging Face")

    monkeypatch.setattr("middleware.src.models.wrappers.esrgan_wrapper.ESRGANWrapper", _Wrapper)
    monkeypatch.setattr("huggingface_hub.hf_hub_download", _hub)
    monkeypatch.setattr("middleware.src.comfy_matrix.try_admit", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("middleware.src.comfy_matrix.gpu_lease.release", lambda *_args, **_kwargs: None)

    frames = _upscale_anime([np.zeros((2, 2, 4), dtype=np.float32)], 4.0, {})
    assert frames[0].shape == (8, 8, 4)
    assert seen["checkpoint_path"] == str(checkpoint)
    assert seen["local_files_only"] is True
