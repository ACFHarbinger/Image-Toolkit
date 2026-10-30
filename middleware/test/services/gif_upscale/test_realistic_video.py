"""SeedVR2, FlashVSR, and DOVE stay offline and mix a clip in time."""

from __future__ import annotations

import importlib
from pathlib import Path

import numpy as np
import pytest
import torch
from middleware.src.services.media.gif_upscale.base import AlgorithmError
from middleware.src.services.media.gif_upscale.registry import get_algorithm, list_algorithms

_IDS = ("seedvr2", "flashvsr", "dove")
_FILES = {
    "seedvr2": "SeedVR2_3B.pth",
    "flashvsr": "FlashVSR_v1.1.pth",
    "dove": "DOVE_SRx4.pth",
}
_VRAM = {"seedvr2": 12000, "flashvsr": 10000, "dove": 11000}
_OWNERS = {
    "seedvr2": "gif-upscale-seedvr2",
    "flashvsr": "gif-upscale-flashvsr",
    "dove": "gif-upscale-dove",
}


def _module(algorithm_id: str):
    return importlib.import_module(f"middleware.src.services.media.gif_upscale.neural.{algorithm_id}")


def _offline_empty(monkeypatch: pytest.MonkeyPatch, cache: Path) -> None:
    monkeypatch.setenv("IMAGE_TOOLKIT_GIF_UPSCALE_WEIGHTS_POLICY", "offline")
    monkeypatch.setenv("IMAGE_TOOLKIT_GIF_UPSCALE_CACHE", str(cache))


def test_import_does_not_call_hf_hub_download(monkeypatch: pytest.MonkeyPatch) -> None:
    import huggingface_hub

    called: list[object] = []

    def _trap(*args: object, **kwargs: object) -> None:
        called.append(args)
        raise AssertionError("hf_hub_download was called")

    monkeypatch.setattr(huggingface_hub, "hf_hub_download", _trap)
    for algorithm_id in _IDS:
        module = _module(algorithm_id)
        text = Path(module.__file__ or "").read_text(encoding="utf-8")
        assert "hf_hub_download" not in text
        assert "huggingface_hub" not in text
        assert "urllib" not in text
        assert "diffusers" not in text
        assert "flash_attn" not in text
        assert "pure-torch temporal shell" in text
    assert called == []


def test_offline_empty_cache_marks_all_three_unavailable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _offline_empty(monkeypatch, tmp_path / "empty")
    rows = {row["id"]: row for row in list_algorithms()}
    for algorithm_id in _IDS:
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
        assert row["vram_mb_estimate"] == _VRAM[algorithm_id]
        assert row["license"] == "Apache-2.0"
        assert row["weights_sha256"] is None


def test_cached_weights_stay_available_without_a_vram_guess(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    cache.mkdir()
    _offline_empty(monkeypatch, cache)
    for algorithm_id, filename in _FILES.items():
        (cache / filename).write_bytes(b"present")
        available, reason = get_algorithm(algorithm_id).spec.available()
        assert available is True
        assert reason == ""
        (cache / filename).unlink()


@pytest.mark.parametrize("algorithm_id", _IDS)
def test_temporal_forward_mixes_neighbors(algorithm_id: str) -> None:
    torch.manual_seed(0)
    model = _module(algorithm_id).TemporalShell(channels=8, n_blocks=1)
    model.eval()
    base = torch.zeros(3, 3, 8, 8)
    base[1] = 0.25
    changed = base.clone()
    changed[0] = 1
    changed[2] = 1
    assert torch.equal(base[1], changed[1])
    with torch.no_grad():
        original = model(base)
        mixed = model(changed)
    assert original.shape == (3, 3, 32, 32)
    assert mixed.shape == (3, 3, 32, 32)
    assert not torch.equal(original[1], mixed[1])


@pytest.mark.parametrize("algorithm_id", _IDS)
def test_state_dict_strict_round_trip(algorithm_id: str, tmp_path: Path) -> None:
    module = _module(algorithm_id)
    torch.manual_seed(1)
    model = module.TemporalShell(channels=8, n_blocks=1)
    path = tmp_path / "tiny.pth"
    torch.save(model.state_dict(), path)
    blob = torch.load(path, map_location="cpu", weights_only=True)
    fresh = module.TemporalShell(channels=8, n_blocks=1)
    fresh.load_state_dict(blob, strict=True)
    for key, value in model.state_dict().items():
        assert torch.equal(value, fresh.state_dict()[key])
    broken = {key: value.clone() for key, value in blob.items() if key != "temporal.weight"}
    with pytest.raises(RuntimeError):
        module.TemporalShell(channels=8, n_blocks=1).load_state_dict(broken, strict=True)


def test_missing_weights_raise_and_do_not_fall_back(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _offline_empty(monkeypatch, tmp_path / "empty")

    def _admit(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("lease acquired without weights")

    monkeypatch.setattr("middleware.src.comfy_matrix.try_admit", _admit)
    frame = np.zeros((4, 4, 4), dtype=np.float32)
    for algorithm_id in _IDS:
        with pytest.raises(AlgorithmError, match=algorithm_id):
            get_algorithm(algorithm_id).upscale([frame], 4.0, {})


def test_shell_upscale_is_4x_and_releases_the_lease(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    cache.mkdir()
    module = _module("seedvr2")
    torch.manual_seed(2)
    torch.save(module.TemporalShell(channels=8, n_blocks=1).state_dict(), cache / _FILES["seedvr2"])
    _offline_empty(monkeypatch, cache)
    monkeypatch.setattr(module, "_cuda_ready", lambda: False)
    seen: list[tuple[str, str, float]] = []

    def _admit(owner: str, *_args: object, estimated_gb: float | None = None, kind: str | None = None) -> None:
        del kind
        seen.append(("admit", owner, float(estimated_gb or 0.0)))
        return None

    def _release(owner: str, *_args: object, **_kwargs: object) -> None:
        seen.append(("release", owner, 0.0))

    monkeypatch.setattr("middleware.src.comfy_matrix.try_admit", _admit)
    monkeypatch.setattr("middleware.src.comfy_matrix.gpu_lease.release", _release)
    frame = np.zeros((8, 8, 4), dtype=np.float32)
    frame[:, :, :3] = 0.2
    frame[:, :, 3] = 1
    frame[0, 0, 3] = 0
    output = module.upscale([frame, frame, frame], 4.0, {})
    assert len(output) == 3
    assert output[0].shape == (32, 32, 4)
    assert output[0].dtype == np.float32
    assert output[0][0, 0, 3] == 0
    assert output[0][4, 4, 3] == 1
    assert seen == [("admit", _OWNERS["seedvr2"], 12000 / 1024.0), ("release", _OWNERS["seedvr2"], 0.0)]


def test_mismatched_checkpoint_refuses_and_releases(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    cache = tmp_path / "cache"
    cache.mkdir()
    torch.save({"dit.blocks.0.weight": torch.zeros(1)}, cache / _FILES["dove"])
    _offline_empty(monkeypatch, cache)
    module = _module("dove")
    monkeypatch.setattr(module, "_cuda_ready", lambda: False)
    released: list[str] = []
    monkeypatch.setattr("middleware.src.comfy_matrix.try_admit", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        "middleware.src.comfy_matrix.gpu_lease.release",
        lambda owner, *_args, **_kwargs: released.append(owner),
    )
    frame = np.zeros((4, 4, 4), dtype=np.float32)
    with pytest.raises(AlgorithmError, match="dove"):
        module.upscale([frame], 4.0, {})
    assert released == [_OWNERS["dove"]]
