"""DRCT and MambaIRv2: no download, offline without weights, tiny CPU forwards."""

from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path

import numpy as np
import pytest
import torch
from middleware.src.services.media.gif_upscale.base import AlgorithmError
from middleware.src.services.media.gif_upscale.registry import get_algorithm, list_algorithms
from PIL import Image

_BANNED = ("huggingface_hub", "urllib", "basicsr", "mamba_ssm", "causal_conv1d")


def _modules():
    drct = importlib.import_module("middleware.src.services.media.gif_upscale.neural.drct")
    mambair = importlib.import_module("middleware.src.services.media.gif_upscale.neural.mambair")
    return drct, mambair


def _tiny(cls, depth: int = 1):
    return cls(embed_dim=16, depths=(depth,), num_heads=2, window_size=4)


def _isolate_home(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("IMAGE_TOOLKIT_GIF_UPSCALE_WEIGHTS_POLICY", "offline")
    monkeypatch.setenv("IMAGE_TOOLKIT_GIF_UPSCALE_CACHE", str(tmp_path / "empty"))
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")


def test_import_does_not_call_hf_hub_download(monkeypatch) -> None:
    calls: list[str] = []

    def _boom(*_args, **_kwargs):
        calls.append("hf_hub_download")
        raise RuntimeError("hf_hub_download")

    fake = types.ModuleType("huggingface_hub")
    fake.hf_hub_download = _boom
    monkeypatch.setitem(sys.modules, "huggingface_hub", fake)
    _modules()
    assert calls == []


def test_offline_empty_cache_marks_both_unavailable(tmp_path, monkeypatch) -> None:
    _isolate_home(monkeypatch, tmp_path)
    rows = {row["id"]: row for row in list_algorithms()}
    expected = {"drct": 4500, "mambairv2": 5000}
    for algorithm_id, vram in expected.items():
        row = rows[algorithm_id]
        assert row["available"] is False
        assert "offline" in row["reason"]
        assert algorithm_id in row["reason"]
        assert row["content"] == "realistic"
        assert row["kind"] == "neural"
        assert row["family"] == algorithm_id
        assert row["supports_scale"] == [4.0]
        assert row["supports_downscale"] is False
        assert row["needs_gpu"] is True
        assert row["vram_mb_estimate"] == vram
        assert row["license"] == "Apache-2.0"
        assert row["weights_sha256"] is None
        assert row["containers"] == ["gif", "still"]


def test_cached_file_is_available_without_reading_it(tmp_path, monkeypatch) -> None:
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "DRCT_SRx4.pth").write_bytes(b"not-a-checkpoint")
    (cache / "MambaIRv2_SRx4.pth").write_bytes(b"not-a-checkpoint")
    monkeypatch.setenv("IMAGE_TOOLKIT_GIF_UPSCALE_WEIGHTS_POLICY", "offline")
    monkeypatch.setenv("IMAGE_TOOLKIT_GIF_UPSCALE_CACHE", str(cache))
    rows = {row["id"]: row for row in list_algorithms()}
    assert rows["drct"]["available"] is True
    assert rows["mambairv2"]["available"] is True
    assert rows["drct"]["reason"] == ""
    assert rows["mambairv2"]["reason"] == ""


def test_huggingface_hub_directory_counts_as_a_local_file(tmp_path, monkeypatch) -> None:
    home = tmp_path / "home"
    snapshot = home / ".cache" / "huggingface" / "hub" / "models--local" / "snapshots" / "abc"
    snapshot.mkdir(parents=True)
    (snapshot / "DRCT_SRx4.pth").write_bytes(b"x")
    (snapshot / "MambaIRv2_SRx4.pth").write_bytes(b"x")
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setenv("IMAGE_TOOLKIT_GIF_UPSCALE_CACHE", str(empty))
    monkeypatch.setenv("IMAGE_TOOLKIT_GIF_UPSCALE_WEIGHTS_POLICY", "offline")
    monkeypatch.setattr(Path, "home", lambda: home)
    rows = {row["id"]: row for row in list_algorithms()}
    assert rows["drct"]["available"] is True
    assert rows["mambairv2"]["available"] is True


@pytest.mark.parametrize("depth", [1, 2])
def test_tiny_forward_and_strict_state_dict_round_trip(depth: int) -> None:
    torch.manual_seed(0)
    sample = torch.rand(1, 3, 8, 8)
    drct, mambair = _modules()
    for cls in (drct.DRCT, mambair.MambaIRv2):
        model = _tiny(cls, depth)
        model.eval()
        with torch.no_grad():
            output = model(sample)
        assert output.shape == (1, 3, 32, 32)
        assert output.device.type == "cpu"
        assert torch.isfinite(output).all()
        restored = _tiny(cls, depth)
        restored.load_state_dict(model.state_dict(), strict=True)
        restored.eval()
        with torch.no_grad():
            again = restored(sample)
        assert torch.allclose(output, again)


def test_partial_windows_stay_four_times_the_input() -> None:
    drct, mambair = _modules()
    sample = torch.zeros(1, 3, 6, 5)
    for cls in (drct.DRCT, mambair.MambaIRv2):
        output = _tiny(cls)(sample)
        assert output.shape == (1, 3, 24, 20)


def test_strict_state_dict_mismatch_raises() -> None:
    drct, mambair = _modules()
    for module, cls in ((drct, drct.DRCT), (mambair, mambair.MambaIRv2)):
        model = _tiny(cls)
        state = dict(model.state_dict())
        state["not-a-parameter"] = torch.zeros(1)
        with pytest.raises(AlgorithmError, match="mismatch"):
            module._apply_state(model, state)


def test_params_ema_round_trips_through_the_checkpoint_reader(tmp_path) -> None:
    drct, mambair = _modules()
    for module, cls, filename in (
        (drct, drct.DRCT, "DRCT_SRx4.pth"),
        (mambair, mambair.MambaIRv2, "MambaIRv2_SRx4.pth"),
    ):
        model = _tiny(cls)
        path = tmp_path / filename
        torch.save({"params": {"nope": torch.zeros(1)}, "params_ema": model.state_dict()}, path)
        other = _tiny(cls)
        module._apply_state(other, module._read_state(path))
        with torch.no_grad():
            assert torch.allclose(model(torch.zeros(1, 3, 8, 8)), other(torch.zeros(1, 3, 8, 8)))


def test_missing_weights_raise_algorithm_error(tmp_path, monkeypatch) -> None:
    _isolate_home(monkeypatch, tmp_path)
    frame = np.zeros((8, 8, 4), dtype=np.float32)
    frame[..., 3] = 1
    for algorithm_id in ("drct", "mambairv2"):
        with pytest.raises(AlgorithmError, match="offline") as caught:
            get_algorithm(algorithm_id).upscale([frame], 4.0, {})
        assert algorithm_id in str(caught.value)


def test_non_4x_scale_is_refused() -> None:
    drct, mambair = _modules()
    frame = np.zeros((4, 4, 4), dtype=np.float32)
    for module in (drct, mambair):
        with pytest.raises(AlgorithmError, match="scale"):
            module.upscale([frame], 2.0, {})


def test_upscale_leases_and_keeps_nearest_alpha(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    drct, mambair = _modules()
    frame = np.zeros((8, 8, 4), dtype=np.float32)
    frame[..., :3] = 0.25
    frame[:, 0, 3] = 0
    frame[:, 1:, 3] = 1
    original = frame.copy()
    reference = _nearest(frame[:, :, 3], 32, 32)
    cases = (
        (drct, drct.DRCT, "gif-upscale-drct", 4.5, "DRCT_SRx4.pth"),
        (mambair, mambair.MambaIRv2, "gif-upscale-mambairv2", 5.0, "MambaIRv2_SRx4.pth"),
    )
    for module, cls, owner, vram_gb, filename in cases:
        weight = tmp_path / filename
        weight.write_bytes(b"unused")
        network = _tiny(cls)
        monkeypatch.setattr(module, "_checkpoint", lambda path=weight: path)
        monkeypatch.setattr(module, "_available", lambda: (True, ""))
        monkeypatch.setattr(module, "_load_model", lambda _path, net=network: net)
        seen: list[tuple] = []

        def _admit(name, *_args, owner=owner, bucket=seen, **kwargs):
            bucket.append(("admit", name, kwargs.get("estimated_gb"), kwargs.get("kind")))
            return None

        def _release(name, *_args, bucket=seen, **_kwargs):
            bucket.append(("release", name))

        monkeypatch.setattr("middleware.src.comfy_matrix.try_admit", _admit)
        monkeypatch.setattr("middleware.src.comfy_matrix.gpu_lease.release", _release)
        output = module.upscale([frame], 4.0, {})[0]
        assert output.shape == (32, 32, 4)
        assert output.dtype == np.float32
        assert np.isfinite(output).all()
        assert float(output[..., :3].min()) >= 0.0
        assert float(output[..., :3].max()) <= 1.0
        assert np.allclose(output[:, :, 3], reference)
        assert seen == [("admit", owner, vram_gb, "generate"), ("release", owner)]
        assert np.array_equal(frame, original)


def test_refused_lease_does_not_release(tmp_path, monkeypatch) -> None:
    drct, _mambair = _modules()
    weight = tmp_path / "DRCT_SRx4.pth"
    weight.write_bytes(b"unused")
    monkeypatch.setattr(drct, "_checkpoint", lambda: weight)
    monkeypatch.setattr(drct, "_available", lambda: (True, ""))
    released: list[str] = []
    monkeypatch.setattr("middleware.src.comfy_matrix.try_admit", lambda *_args, **_kwargs: "GPU busy")
    monkeypatch.setattr(
        "middleware.src.comfy_matrix.gpu_lease.release",
        lambda *_args, **_kwargs: released.append("released"),
    )
    frame = np.zeros((4, 4, 4), dtype=np.float32)
    with pytest.raises(AlgorithmError, match="busy"):
        drct.upscale([frame], 4.0, {})
    assert released == []


def test_sources_do_not_import_hub_or_cuda_kernels() -> None:
    drct, mambair = _modules()
    for module in (drct, mambair):
        text = Path(module.__file__).read_text(encoding="utf-8")
        imports = [
            line.strip()
            for line in text.splitlines()
            if line.strip().startswith(("import ", "from "))
        ]
        for banned in _BANNED:
            assert all(banned not in line for line in imports)
    doc = mambair.__doc__ or ""
    assert "pure-torch" in doc
    assert "CUDA" in doc
    assert "prompt block" in doc


def _nearest(alpha: np.ndarray, height: int, width: int) -> np.ndarray:
    image = Image.fromarray(np.clip(np.rint(alpha * 255.0), 0, 255).astype(np.uint8), "L")
    try:
        resized = image.resize((width, height), Image.Resampling.NEAREST)
        try:
            return np.asarray(resized).astype(np.float32) / 255.0
        finally:
            resized.close()
    finally:
        image.close()
