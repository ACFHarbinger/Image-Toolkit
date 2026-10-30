"""HAT and SwinIR register as realistic neural GIF upscalers and do not download."""

from __future__ import annotations

import importlib
import sys

import numpy as np
import pytest
import torch
from middleware.src.services.media.gif_upscale.base import AlgorithmError
from middleware.src.services.media.gif_upscale.registry import _ALGORITHMS, list_algorithms

_TINY = {"embed_dim": 16, "depths": (1,), "num_heads": 2, "window_size": 4, "upscale": 4}
_MODULES = {
    "hat": "middleware.src.services.media.gif_upscale.neural.hat",
    "swinir": "middleware.src.services.media.gif_upscale.neural.swinir",
}


def _reload(algorithm_id: str):
    _ALGORITHMS.pop(algorithm_id, None)
    name = _MODULES[algorithm_id]
    sys.modules.pop(name, None)
    return importlib.import_module(name)


def test_import_does_not_call_hf_hub_download(monkeypatch) -> None:
    def boom(*_args, **_kwargs):
        raise AssertionError("hf_hub_download was called")

    monkeypatch.setattr("huggingface_hub.hf_hub_download", boom)
    for algorithm_id in _MODULES:
        _reload(algorithm_id)


def test_offline_empty_cache_lists_both_unavailable(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("IMAGE_TOOLKIT_GIF_UPSCALE_WEIGHTS_POLICY", "offline")
    monkeypatch.setenv("IMAGE_TOOLKIT_GIF_UPSCALE_CACHE", str(tmp_path / "empty"))
    rows = {row["id"]: row for row in list_algorithms()}
    expected_vram = {"hat": 4000, "swinir": 3000}
    for algorithm_id, vram in expected_vram.items():
        row = rows[algorithm_id]
        assert row["available"] is False
        assert algorithm_id in row["reason"]
        assert "offline" in row["reason"]
        assert row["content"] == "realistic"
        assert row["kind"] == "neural"
        assert row["containers"] == ["gif", "still"]
        assert row["supports_scale"] == [4.0]
        assert row["supports_downscale"] is False
        assert row["needs_gpu"] is True
        assert row["license"] == "Apache-2.0"
        assert row["weights_sha256"] is None
        assert row["vram_mb_estimate"] == vram


def test_tiny_forward_is_4x() -> None:
    hat = _reload("hat")
    swinir = _reload("swinir")
    image = torch.rand(1, 3, 8, 8)
    for net in (hat.HAT(**_TINY), swinir.SwinIR(**_TINY)):
        net.eval()
        with torch.inference_mode():
            out = net(image)
        assert out.shape == (1, 3, 32, 32)
        assert out.dtype == torch.float32
        assert torch.isfinite(out).all()


def test_shifted_window_and_pad_keep_scale() -> None:
    hat = _reload("hat")
    swinir = _reload("swinir")
    config = {"embed_dim": 16, "depths": (2,), "num_heads": (2,), "window_size": 4, "upscale": 4}
    image = torch.rand(1, 3, 6, 5)
    for net in (hat.HAT(**config), swinir.SwinIR(**config)):
        with torch.inference_mode():
            out = net(image)
        assert out.shape == (1, 3, 24, 20)
        assert torch.isfinite(out).all()


def test_saved_tiny_state_dict_reloads_strict(tmp_path) -> None:
    hat = _reload("hat")
    swinir = _reload("swinir")
    image = torch.rand(1, 3, 8, 8)
    for cls, name in ((hat.HAT, "hat"), (swinir.SwinIR, "swinir")):
        net = cls(**_TINY)
        path = tmp_path / f"{name}.pth"
        torch.save(net.state_dict(), path)
        restored = cls(**_TINY)
        restored.load_state_dict(torch.load(path, map_location="cpu", weights_only=True), strict=True)
        restored.eval()
        net.eval()
        with torch.inference_mode():
            assert torch.allclose(net(image), restored(image))


def test_missing_file_raises_and_does_not_admit(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("IMAGE_TOOLKIT_GIF_UPSCALE_WEIGHTS_POLICY", "offline")
    monkeypatch.setenv("IMAGE_TOOLKIT_GIF_UPSCALE_CACHE", str(tmp_path / "empty"))
    admitted: list[str] = []

    def _admit(owner, *_args, **_kwargs):
        admitted.append(owner)
        return None

    monkeypatch.setattr("middleware.src.comfy_matrix.try_admit", _admit)
    hat = _reload("hat")
    frame = np.zeros((4, 4, 4), dtype=np.float32)
    with pytest.raises(AlgorithmError, match="hat") as caught:
        hat.upscale([frame], 4.0, {})
    assert "offline" in str(caught.value)
    assert admitted == []


@pytest.mark.parametrize(
    ("algorithm_id", "class_name", "filename", "owner"),
    [
        ("hat", "HAT", "HAT_SRx4.pth", "gif-upscale-hat"),
        ("swinir", "SwinIR", "SwinIR_SRx4.pth", "gif-upscale-swinir"),
    ],
)
def test_upscale_loads_tiny_checkpoint_on_cpu(algorithm_id, class_name, filename, owner, tmp_path, monkeypatch) -> None:
    module = _reload(algorithm_id)
    monkeypatch.setattr(module.torch.cuda, "is_available", lambda: False)
    cache = tmp_path / "cache"
    cache.mkdir()
    monkeypatch.setenv("IMAGE_TOOLKIT_GIF_UPSCALE_CACHE", str(cache))
    monkeypatch.setenv("IMAGE_TOOLKIT_GIF_UPSCALE_WEIGHTS_POLICY", "offline")
    real = getattr(module, class_name)
    source = real(**_TINY).eval()
    torch.save(source.state_dict(), cache / filename)
    monkeypatch.setattr(module, class_name, lambda **_kwargs: real(**_TINY))

    seen: dict[str, object] = {}

    def _admit(name, *_args, **kwargs):
        seen["owner"] = name
        seen["estimated_gb"] = kwargs.get("estimated_gb")
        seen["kind"] = kwargs.get("kind")
        return None

    def _release(name, *_args, **_kwargs):
        seen["released"] = name

    monkeypatch.setattr("middleware.src.comfy_matrix.try_admit", _admit)
    monkeypatch.setattr("middleware.src.comfy_matrix.gpu_lease.release", _release)

    frame = np.zeros((8, 8, 4), dtype=np.float32)
    frame[:, :, :3] = 0.25
    frame[:, 4:, 3] = 1.0
    frames = module.upscale([frame, frame], 4, {})
    assert len(frames) == 2
    assert frames[0].shape == (32, 32, 4)
    assert frames[0].dtype == np.float32
    tensor = torch.from_numpy(frame[:, :, :3]).permute(2, 0, 1).unsqueeze(0)
    with torch.inference_mode():
        expected = source(tensor).squeeze(0).permute(1, 2, 0).numpy()
    np.clip(expected, 0.0, 1.0, out=expected)
    assert np.allclose(frames[0][:, :, :3], expected, atol=1e-5)
    alpha = np.repeat(np.repeat(frame[:, :, 3], 4, axis=0), 4, axis=1)
    assert np.allclose(frames[0][:, :, 3], alpha)
    assert seen["owner"] == owner
    assert seen["released"] == owner
    assert seen["kind"] == "generate"
    assert seen["estimated_gb"] == (4.0 if algorithm_id == "hat" else 3.0)


def test_key_mismatch_raises(tmp_path, monkeypatch) -> None:
    module = _reload("hat")
    monkeypatch.setattr(module.torch.cuda, "is_available", lambda: False)
    cache = tmp_path / "cache"
    cache.mkdir()
    monkeypatch.setenv("IMAGE_TOOLKIT_GIF_UPSCALE_CACHE", str(cache))
    monkeypatch.setenv("IMAGE_TOOLKIT_GIF_UPSCALE_WEIGHTS_POLICY", "offline")
    torch.save({"conv_first.weight": torch.zeros(1)}, cache / "HAT_SRx4.pth")
    real = module.HAT
    monkeypatch.setattr(module, "HAT", lambda **_kwargs: real(**_TINY))
    monkeypatch.setattr("middleware.src.comfy_matrix.try_admit", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("middleware.src.comfy_matrix.gpu_lease.release", lambda *_args, **_kwargs: None)
    frame = np.zeros((8, 8, 4), dtype=np.float32)
    with pytest.raises(AlgorithmError, match="hat weight key mismatch"):
        module.upscale([frame], 4.0, {})


def test_hub_cache_counts_as_present(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("IMAGE_TOOLKIT_GIF_UPSCALE_WEIGHTS_POLICY", "offline")
    monkeypatch.setenv("IMAGE_TOOLKIT_GIF_UPSCALE_CACHE", str(tmp_path / "empty"))
    home = tmp_path / "home"
    for algorithm_id, filename in (("hat", "HAT_SRx4.pth"), ("swinir", "SwinIR_SRx4.pth")):
        module = _reload(algorithm_id)
        dest = home / ".cache" / "huggingface" / "hub" / f"models--{algorithm_id}" / "snapshots" / "abc"
        dest.mkdir(parents=True, exist_ok=True)
        (dest / filename).write_bytes(b"local")
        monkeypatch.setattr(module.Path, "home", staticmethod(lambda root=home: root))
        ok, reason = module._available()
        assert ok is True
        assert reason == ""
