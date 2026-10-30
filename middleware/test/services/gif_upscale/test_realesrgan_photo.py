"""Realistic Real-ESRGAN rows stay offline and do not download or run the 23-block net."""

from __future__ import annotations

import importlib

import torch
from middleware.src.models.wrappers.esrgan_wrapper import RRDBNet
from middleware.src.services.media.gif_upscale.neural.realesrgan_photo import (
    RRDBNetX2,
    SRVGGNetCompact,
)
from middleware.src.services.media.gif_upscale.registry import list_algorithms

_IDS = ("realesrgan-x4plus", "realesrgan-x2plus", "realesrgan-general-x4v3")
_FILES = {
    "realesrgan-x4plus": "RealESRGAN_x4plus.pth",
    "realesrgan-x2plus": "RealESRGAN_x2plus.pth",
    "realesrgan-general-x4v3": "realesr-general-x4v3.pth",
}


def _offline_cache(monkeypatch, cache) -> None:
    monkeypatch.setenv("IMAGE_TOOLKIT_GIF_UPSCALE_WEIGHTS_POLICY", "offline")
    monkeypatch.setenv("IMAGE_TOOLKIT_GIF_UPSCALE_CACHE", str(cache))


def test_photo_ids_are_listed_and_unavailable_without_files(tmp_path, monkeypatch) -> None:
    _offline_cache(monkeypatch, tmp_path)
    rows = {row["id"]: row for row in list_algorithms()}
    expected = {
        "realesrgan-x4plus": ([4.0], 2500),
        "realesrgan-x2plus": ([2.0], 2500),
        "realesrgan-general-x4v3": ([4.0], 800),
    }
    for algorithm_id, (scales, vram) in expected.items():
        row = rows[algorithm_id]
        assert row["available"] is False
        reason = row["reason"]
        assert algorithm_id in reason
        assert _FILES[algorithm_id] in reason
        assert "offline" in reason
        assert row["content"] == "realistic"
        assert row["kind"] == "neural"
        assert row["family"] == "realesrgan"
        assert row["containers"] == ["gif", "still"]
        assert row["supports_downscale"] is False
        assert row["needs_gpu"] is True
        assert row["license"] == "BSD-3-Clause"
        assert row["weights_sha256"] is None
        assert row["supports_scale"] == scales
        assert row["vram_mb_estimate"] == vram


def test_on_demand_missing_file_is_not_cached_and_not_fetched(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("IMAGE_TOOLKIT_GIF_UPSCALE_WEIGHTS_POLICY", "on_demand")
    monkeypatch.setenv("IMAGE_TOOLKIT_GIF_UPSCALE_CACHE", str(tmp_path))
    rows = {row["id"]: row for row in list_algorithms()}
    for algorithm_id in _IDS:
        assert rows[algorithm_id]["available"] is False
        assert "weights are not cached" in rows[algorithm_id]["reason"]


def test_tiny_networks_scale_an_8px_frame() -> None:
    sample = torch.rand(1, 3, 8, 8)
    with torch.no_grad():
        times_four = RRDBNet(num_feat=64, num_block=1, num_grow_ch=32)(sample)
        times_two = RRDBNetX2(num_block=1)(sample)
        general = SRVGGNetCompact(num_feat=64, num_conv=2, upscale=4)(sample)
    assert times_four.shape == (1, 3, 32, 32)
    assert times_two.shape == (1, 3, 16, 16)
    assert general.shape == (1, 3, 32, 32)
    assert torch.isfinite(times_four).all()
    assert torch.isfinite(times_two).all()
    assert torch.isfinite(general).all()


def test_cached_state_dict_marks_the_row_available(tmp_path, monkeypatch) -> None:
    _offline_cache(monkeypatch, tmp_path)
    torch.save(RRDBNet(num_block=1).state_dict(), tmp_path / _FILES["realesrgan-x4plus"])
    torch.save(RRDBNetX2(num_block=1).state_dict(), tmp_path / _FILES["realesrgan-x2plus"])
    torch.save(SRVGGNetCompact(num_conv=2).state_dict(), tmp_path / _FILES["realesrgan-general-x4v3"])
    rows = {row["id"]: row for row in list_algorithms()}
    for algorithm_id in _IDS:
        assert rows[algorithm_id]["available"] is True
        assert rows[algorithm_id]["reason"] == ""


def test_import_does_not_call_huggingface(monkeypatch, tmp_path) -> None:
    _offline_cache(monkeypatch, tmp_path)

    def boom(*_args, **_kwargs):
        raise AssertionError("huggingface_hub.hf_hub_download was called")

    monkeypatch.setattr("huggingface_hub.hf_hub_download", boom)
    module = importlib.import_module("middleware.src.services.media.gif_upscale.neural.realesrgan_photo")
    assert module.RRDBNetX2 is RRDBNetX2
    rows = {row["id"]: row for row in list_algorithms()}
    assert rows["realesrgan-x4plus"]["available"] is False
