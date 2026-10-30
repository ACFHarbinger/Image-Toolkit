"""OSEDiff and TSD-SR shells stay offline: no downloads and no CUDA."""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import numpy as np
import pytest
import torch
import torch.nn.functional as F
from middleware.src.services.media.gif_upscale.base import AlgorithmError
from middleware.src.services.media.gif_upscale.neural import osediff, tsd_sr
from middleware.src.services.media.gif_upscale.registry import list_algorithms

_BACKENDS = (
    (osediff, "OSEDiff_SRx4.pth", "gif-upscale-osediff", 6.0, 6000),
    (tsd_sr, "TSDSR_SRx4.pth", "gif-upscale-tsd-sr", 5.5, 5500),
)
_NEURAL = Path(__file__).resolve().parents[3] / "src/services/media/gif_upscale/neural"
_ROOT = Path(__file__).resolve().parents[4]


def test_import_does_not_call_hf_hub_download() -> None:
    for name in ("osediff.py", "tsd_sr.py"):
        text = (_NEURAL / name).read_text(encoding="utf-8")
        for banned in ("huggingface_hub", "hf_hub_download", "urllib", "diffusers"):
            assert banned not in text
    script = textwrap.dedent(
        """
        import sys
        import types

        stub = types.ModuleType("huggingface_hub")

        def hf_hub_download(*args, **kwargs):
            raise SystemExit("hf_hub_download was called")

        stub.hf_hub_download = hf_hub_download
        sys.modules["huggingface_hub"] = stub
        import middleware.src.services.media.gif_upscale.neural.osediff
        import middleware.src.services.media.gif_upscale.neural.tsd_sr
        print("ok")
        """
    )
    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
        cwd=_ROOT,
    )
    assert completed.returncode == 0, completed.stderr
    assert "ok" in completed.stdout


def test_offline_empty_cache_is_unavailable(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("IMAGE_TOOLKIT_GIF_UPSCALE_WEIGHTS_POLICY", "offline")
    monkeypatch.setenv("IMAGE_TOOLKIT_GIF_UPSCALE_CACHE", str(tmp_path / "empty"))
    rows = {row["id"]: row for row in list_algorithms()}
    frame = np.zeros((2, 2, 4), dtype=np.float32)
    for module, _filename, _owner, _gb, vram in _BACKENDS:
        algorithm_id = module._ID
        row = rows[algorithm_id]
        assert row["available"] is False
        assert "offline" in row["reason"]
        assert algorithm_id in row["reason"]
        assert row["content"] == "realistic"
        assert row["kind"] == "neural"
        assert row["containers"] == ["gif", "still"]
        assert row["supports_scale"] == [4.0]
        assert row["supports_downscale"] is False
        assert row["needs_gpu"] is True
        assert row["vram_mb_estimate"] == vram
        assert row["license"] == "Apache-2.0"
        assert row["weights_sha256"] is None
        with pytest.raises(AlgorithmError) as caught:
            module.upscale([frame], 4.0, {})
        message = str(caught.value)
        assert "offline" in message
        assert algorithm_id in message


@pytest.mark.parametrize("module", (osediff, tsd_sr))
def test_tiny_forward(module) -> None:
    network = module.OneStepResidualSR(width=8, n_blocks=1).to("cpu")
    output = network(torch.zeros(1, 3, 8, 8))
    assert tuple(output.shape) == (1, 3, 32, 32)


@pytest.mark.parametrize("module", (osediff, tsd_sr))
def test_tiny_state_dict_reloads_strict(module) -> None:
    network = module.OneStepResidualSR(width=8, n_blocks=1)
    fresh = module.OneStepResidualSR(width=8, n_blocks=1)
    fresh.load_state_dict(network.state_dict(), strict=True)
    sample = torch.rand(1, 3, 8, 8)
    with torch.no_grad():
        assert torch.equal(network(sample), fresh(sample))


def _constant_shell(module, bias: float):
    network = module.OneStepResidualSR(width=8, n_blocks=1)
    with torch.no_grad():
        for parameter in network.parameters():
            parameter.zero_()
        network.tail.bias.fill_(bias)
    return network


def _patch_lease(monkeypatch):
    seen: list[tuple] = []

    def admit(owner, lease=None, *, estimated_gb=None, kind=None):
        del lease
        seen.append(("admit", owner, estimated_gb, kind))
        return None

    def release(owner, *args, **kwargs):
        del args, kwargs
        seen.append(("release", owner))

    monkeypatch.setattr("middleware.src.comfy_matrix.try_admit", admit)
    monkeypatch.setattr("middleware.src.comfy_matrix.gpu_lease.release", release)
    return seen


@pytest.mark.parametrize(("module", "filename", "owner", "gb", "vram"), _BACKENDS)
def test_fidelity_guard_blends_toward_bicubic(module, filename, owner, gb, vram, tmp_path, monkeypatch) -> None:
    del vram
    monkeypatch.setenv("IMAGE_TOOLKIT_GIF_UPSCALE_WEIGHTS_POLICY", "offline")
    monkeypatch.setenv("IMAGE_TOOLKIT_GIF_UPSCALE_CACHE", str(tmp_path))
    seen = _patch_lease(monkeypatch)
    network = _constant_shell(module, 0.1)
    torch.save(network.state_dict(), tmp_path / filename)
    frame = np.full((8, 8, 4), 0.4, dtype=np.float32)
    frame[:, :, 3] = 0.0
    frame[0, 0, 3] = 1.0
    tensor = torch.from_numpy(np.ascontiguousarray(frame[:, :, :3])).permute(2, 0, 1).unsqueeze(0)
    with torch.no_grad():
        predicted = network(tensor)
        reference = F.interpolate(tensor, scale_factor=4, mode="bicubic", align_corners=False)
    pred_px = float(predicted[0, 0, 0, 0])
    ref_px = float(reference[0, 0, 0, 0])
    assert abs(pred_px - ref_px) > 1e-3

    kept = module.upscale([frame], 4.0, {"fidelity_distance": lambda _predicted, _reference: 0.0})[0]
    blended = module.upscale(
        [frame],
        4.0,
        {"fidelity_distance": lambda _predicted, _reference: 1.0, "fidelity_blend": 0.5},
    )[0]
    assert kept[0, 0, 0] == pytest.approx(pred_px, abs=1e-5)
    assert blended[0, 0, 0] == pytest.approx((pred_px + ref_px) / 2.0, abs=1e-5)
    assert abs(float(blended[0, 0, 0]) - pred_px) > 1e-3
    assert kept[0, 0, 3] == pytest.approx(1.0)
    assert kept[0, 4, 3] == pytest.approx(0.0)
    assert blended[0, 0, 3] == pytest.approx(1.0)

    under_limit = module.upscale([frame], 4.0, {})[0]
    assert under_limit[0, 0, 0] == pytest.approx(pred_px, abs=1e-5)

    far = _constant_shell(module, 0.4)
    torch.save(far.state_dict(), tmp_path / filename)
    with torch.no_grad():
        far_predicted = far(tensor)
        far_reference = F.interpolate(tensor, scale_factor=4, mode="bicubic", align_corners=False)
    pulled = module.upscale([frame], 4.0, {})[0]
    far_px = float(far_predicted[0, 0, 0, 0])
    far_ref = float(far_reference[0, 0, 0, 0])
    assert pulled[0, 0, 0] == pytest.approx((far_px + far_ref) / 2.0, abs=1e-5)
    assert ("admit", owner, gb, "generate") in seen
    assert seen.count(("release", owner)) == seen.count(("admit", owner, gb, "generate"))
