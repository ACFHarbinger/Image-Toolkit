"""C2 (#1160): pre-flight estimate. CPU only. The device probe is injected.

Projection tolerance: decode, scale, index, and lzw are measured_s times
frame_count/sample_frames. Palette is measured_s times
min(16, frame_count)/sample_frames. That is linear in the sample, not a
measured full-job time. A GPU job is not timed; the CPU total is an upper bound.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest
from middleware.src.core.gpu_lease_arbiter import GpuLeaseArbiter
from middleware.src.services.media.gif_upscale import estimate as estimate_mod
from middleware.src.services.media.gif_upscale.base import AlgorithmError, ResampleCancelled
from middleware.src.services.media.gif_upscale.estimate import (
    estimate_gif_job,
    usable_gif_gpu,
    workers_batch_warning,
)
from middleware.src.settings.adapters import MemoryStore
from middleware.src.settings.scopes import SettingScope
from middleware.src.settings.service import SettingsService
from PIL import Image


def _settings(**values: object) -> SettingsService:
    store = MemoryStore()
    for key, value in values.items():
        store.set(key, value)
    return SettingsService(stores={SettingScope.DEVICE: store})


def _gif(path, frames: int = 20, size: tuple[int, int] = (16, 16)) -> None:
    images = []
    for index in range(frames):
        image = Image.new("RGB", size, (index * 10 % 256, 40, 80))
        images.append(image)
    images[0].save(
        path,
        format="GIF",
        save_all=True,
        append_images=images[1:],
        duration=40,
        loop=0,
        optimize=False,
    )
    for image in images:
        image.close()


def _no_gpu() -> tuple[bool, str]:
    return False, "cpu"


def test_workers_warning_only_when_both_are_on() -> None:
    assert workers_batch_warning(1, True) is None
    assert workers_batch_warning(4, False) is None
    assert workers_batch_warning("nope", True) is None  # type: ignore[arg-type]
    warning = workers_batch_warning(2, True)
    assert warning is not None
    assert "workers=2" in warning
    assert "4 processes" in warning
    assert "D10" in warning


def test_usable_gpu_uses_an_injected_probe_and_the_default_hook(monkeypatch: pytest.MonkeyPatch) -> None:
    assert usable_gif_gpu(lambda: (False, "cuda:0")) == (False, "cpu")
    assert usable_gif_gpu(lambda: (True, "cuda:1")) == (True, "cuda:1")
    monkeypatch.setattr(estimate_mod, "_default_gpu_probe", lambda: (True, "cuda:0"))
    assert usable_gif_gpu() == (True, "cuda:0")


def test_estimate_projects_from_a_few_frames_and_does_not_decode_the_rest(tmp_path, monkeypatch) -> None:
    source = tmp_path / "clip.gif"
    _gif(source, frames=20)
    pulled: list[int] = []
    real = estimate_mod.iter_gif_frames

    def counting(path: str):
        for item in real(path):
            pulled.append(1)
            yield item

    monkeypatch.setattr(estimate_mod, "iter_gif_frames", counting)
    calls: list[tuple[str, int, int]] = []

    def progress(stage: str, done: int, total: int) -> None:
        calls.append((stage, done, total))

    original = {"factor": 2, "progress": progress}
    result = estimate_gif_job(
        str(source),
        original,
        sample_frames=4,
        device_probe=_no_gpu,
        scratch_dir=tmp_path,
        settings_service=_settings(),
    )
    assert "workers" not in original
    assert pulled == [1, 1, 1, 1]
    assert result.frame_count == 20
    assert result.sample_frames == 4
    assert (result.src_w, result.src_h, result.dst_w, result.dst_h) == (16, 16, 32, 32)
    assert result.timed_device == "cpu"
    assert result.device == "cpu"
    assert result.workers == 1
    assert result.warning is None
    assert "timed cpu lanczos on 4 of 20 frames" in result.path
    assert "job would use cpu" in result.path
    assert "batch multi-core off" in result.path
    assert not (tmp_path / "gif-estimate-lzw.gif").exists()
    assert calls[0] == ("estimate", 0, 20)
    assert max(done for _stage, done, _total in calls) == 4

    frame_ratio = 20 / 4
    palette_ratio = 16 / 4
    for stage in ("decode", "scale", "lzw"):
        assert math.isclose(result.projected_s[stage], result.measured_s[stage] * frame_ratio, abs_tol=1e-12)
    assert math.isclose(result.projected_s["palette"], result.measured_s["palette"] * palette_ratio, abs_tol=1e-12)
    rest = result.measured_s["index"] - result.index_setup_s
    per_frame = rest / 3
    assert math.isclose(result.projected_s["index"], result.index_setup_s + per_frame * 19, abs_tol=1e-12)
    assert result.projected_s["index"] < result.measured_s["index"] * frame_ratio
    assert math.isclose(result.total_s, sum(result.projected_s.values()), abs_tol=1e-12)
    assert result.measured_s["scale"] > 0
    assert any("Linear projection" in note for note in result.notes)
    assert any("ratio 5" in note and "ratio 4" in note for note in result.notes)


def test_gpu_job_names_the_card_and_keeps_the_cpu_sample_as_an_upper_bound(tmp_path) -> None:
    source = tmp_path / "clip.gif"
    _gif(source, frames=6)
    seen: list[str] = []

    def probe() -> tuple[bool, str]:
        seen.append("probe")
        return True, "cuda:0"

    result = estimate_gif_job(
        str(source),
        {"factor": 2, "algorithm": "lanczos3-dering", "quality": "exact"},
        sample_frames=2,
        device_probe=probe,
        scratch_dir=tmp_path,
        settings_service=_settings(),
    )
    assert seen == ["probe"]
    assert result.device == "cuda:0"
    assert result.timed_device == "cpu"
    assert "job would use cuda:0" in result.path
    assert "CPU sample is an upper bound" in result.path
    assert any("upper bound" in note for note in result.notes)
    assert result.sample_frames == 2
    assert result.frame_count == 6


def test_missing_gpu_says_it_fell_back(tmp_path) -> None:
    source = tmp_path / "clip.gif"
    _gif(source, frames=4)
    result = estimate_gif_job(
        str(source),
        {"factor": 2, "algorithm": "lanczos3-dering", "device": "cuda:1", "quality": "exact"},
        sample_frames=2,
        device_probe=_no_gpu,
        scratch_dir=tmp_path,
        settings_service=_settings(),
    )
    assert result.device == "cpu"
    assert "fell back to cpu" in " ".join(result.notes)
    assert "job would use cpu" in result.path


def test_cpu_algorithm_does_not_ask_the_probe(tmp_path) -> None:
    source = tmp_path / "clip.gif"
    _gif(source, frames=4)

    def probe() -> tuple[bool, str]:
        raise AssertionError("lanczos does not use a GPU")

    result = estimate_gif_job(
        str(source),
        {"factor": 2, "algorithm": "lanczos", "quality": "exact"},
        device_probe=probe,
        scratch_dir=tmp_path,
        settings_service=_settings(),
    )
    assert result.device == "cpu"
    assert "lanczos/temporal runs on cpu" in " ".join(result.notes)


def test_workers_above_one_with_batch_multicore_warns_and_reads_settings(tmp_path) -> None:
    source = tmp_path / "clip.gif"
    _gif(source, frames=4)
    result = estimate_gif_job(
        str(source),
        {"factor": 2, "quality": "exact"},
        use_multicore=True,
        device_probe=_no_gpu,
        scratch_dir=tmp_path,
        settings_service=_settings(**{"gif_upscale.workers": 3}),
    )
    assert result.workers == 3
    assert result.warning is not None
    assert "workers=3" in result.warning
    assert "6 processes" in result.warning
    assert "workers=3" in result.path
    assert "batch multi-core on" in result.path
    assert any("up to 6 processes" in note for note in result.notes)


def test_cancel_during_the_sample_propagates(tmp_path) -> None:
    source = tmp_path / "clip.gif"
    _gif(source, frames=8)

    def progress(stage: str, done: int, total: int) -> None:
        del stage, total
        if done >= 1:
            raise ResampleCancelled("stop")

    with pytest.raises(ResampleCancelled):
        estimate_gif_job(
            str(source),
            {"factor": 2, "quality": "exact", "progress": progress},
            sample_frames=4,
            device_probe=_no_gpu,
            scratch_dir=tmp_path,
            settings_service=_settings(),
        )
    assert not (tmp_path / "gif-estimate-lzw.gif").exists()


def test_sample_cap_stays_at_eight_frames(tmp_path) -> None:
    source = tmp_path / "clip.gif"
    _gif(source, frames=12)
    result = estimate_gif_job(
        str(source),
        {"factor": 2, "quality": "exact"},
        sample_frames=100,
        device_probe=_no_gpu,
        scratch_dir=tmp_path,
        settings_service=_settings(),
    )
    assert result.sample_frames == 8
    assert result.frame_count == 12
    assert "8 of 12" in result.path
    assert np.isfinite(result.total_s)


def _cancel_at(stage_name: str):
    def progress(stage: str, done: int, total: int) -> None:
        del total
        if stage == stage_name and done >= 1:
            raise ResampleCancelled(stage_name)

    return progress


def test_cancel_between_scale_frames(tmp_path) -> None:
    source = tmp_path / "clip.gif"
    _gif(source, frames=4)
    with pytest.raises(ResampleCancelled):
        estimate_gif_job(
            str(source),
            {"factor": 2, "quality": "exact", "progress": _cancel_at("scale")},
            sample_frames=4,
            device_probe=_no_gpu,
            scratch_dir=tmp_path,
            settings_service=_settings(),
        )


def test_cancel_between_index_frames(tmp_path) -> None:
    source = tmp_path / "clip.gif"
    _gif(source, frames=4)
    with pytest.raises(ResampleCancelled):
        estimate_gif_job(
            str(source),
            {"factor": 2, "quality": "exact", "progress": _cancel_at("index")},
            sample_frames=4,
            device_probe=_no_gpu,
            scratch_dir=tmp_path,
            settings_service=_settings(),
        )


def test_cancel_between_lzw_frames(tmp_path) -> None:
    source = tmp_path / "clip.gif"
    _gif(source, frames=4)
    with pytest.raises(ResampleCancelled):
        estimate_gif_job(
            str(source),
            {"factor": 2, "quality": "exact", "progress": _cancel_at("lzw")},
            sample_frames=4,
            device_probe=_no_gpu,
            scratch_dir=tmp_path,
            settings_service=_settings(),
        )
    assert not (tmp_path / "gif-estimate-lzw.gif").exists()


def test_pinned_device_must_exist_and_admission_is_provisional(tmp_path) -> None:
    source = tmp_path / "clip.gif"
    _gif(source, frames=4)
    result = estimate_gif_job(
        str(source),
        {"factor": 2, "algorithm": "lanczos3-dering", "device": "cuda:1", "quality": "exact"},
        sample_frames=2,
        device_probe=lambda: (True, "cuda:0"),
        scratch_dir=tmp_path,
        settings_service=_settings(),
    )
    assert result.device == "cpu"
    notes = " ".join(result.notes)
    assert "cuda:1" in notes
    assert "provisional" in notes.lower()


def test_allow_list_and_holder_select_the_projected_card(tmp_path) -> None:
    source = tmp_path / "clip.gif"
    _gif(source, frames=4)
    arbiter = GpuLeaseArbiter(
        devices=(
            {"index": 0, "total_gb": 24, "free_gb": 20},
            {"index": 1, "total_gb": 24, "free_gb": 18},
        ),
        allow_devices=(0, 1),
    )
    assert arbiter.try_acquire("trainer", device=0)
    held = estimate_gif_job(
        str(source),
        {
            "factor": 2,
            "algorithm": "lanczos3-dering",
            "allow_devices": [0],
            "gpu_arbiter": arbiter,
            "quality": "exact",
        },
        sample_frames=2,
        device_probe=lambda: (True, "cuda:0"),
        scratch_dir=tmp_path,
        settings_service=_settings(),
    )
    assert held.device == "cpu"
    held_notes = " ".join(held.notes).lower()
    assert "held" in held_notes
    assert "provisional" in held_notes
    free = estimate_gif_job(
        str(source),
        {
            "factor": 2,
            "algorithm": "lanczos3-dering",
            "allow_devices": [1],
            "gpu_arbiter": arbiter,
            "quality": "exact",
        },
        sample_frames=2,
        device_probe=lambda: (True, "cuda:0"),
        scratch_dir=tmp_path,
        settings_service=_settings(),
    )
    assert free.device == "cuda:1"
    assert "provisional" in " ".join(free.notes).lower()


def test_gpu_algorithm_is_not_sampled_on_cpu(tmp_path, monkeypatch) -> None:
    source = tmp_path / "clip.gif"
    _gif(source, frames=2)
    calls: list[str] = []
    real = estimate_mod._one_frame

    def counting(*args, **kwargs):
        calls.append("scale")
        return real(*args, **kwargs)

    monkeypatch.setattr(estimate_mod, "_one_frame", counting)
    with pytest.raises(AlgorithmError, match="only times algorithms that run on CPU"):
        estimate_gif_job(
            str(source),
            {"factor": 4, "algorithm": "realesrgan-anime-6b", "quality": "exact"},
            sample_frames=1,
            device_probe=_no_gpu,
            scratch_dir=tmp_path,
            settings_service=_settings(),
        )
    assert calls == []


def test_scratch_dirs_are_unique_and_the_default_is_under_downloads(tmp_path, monkeypatch) -> None:
    source = tmp_path / "clip.gif"
    _gif(source, frames=2)
    paths: list[object] = []
    real_writer = estimate_mod.IndexedGifWriter

    class _RecordingWriter(real_writer):
        def __init__(self, path, *args, **kwargs):
            paths.append(path)
            super().__init__(path, *args, **kwargs)

    monkeypatch.setattr(estimate_mod, "IndexedGifWriter", _RecordingWriter)
    kwargs = {
        "sample_frames": 1,
        "device_probe": _no_gpu,
        "settings_service": _settings(),
    }
    params = {"factor": 2, "quality": "exact"}
    estimate_gif_job(str(source), params, scratch_dir=tmp_path, **kwargs)
    estimate_gif_job(str(source), params, scratch_dir=tmp_path, **kwargs)
    assert paths[0] != paths[1]
    assert Path(paths[0]).parent != tmp_path
    assert tmp_path in Path(paths[0]).parents
    estimate_gif_job(str(source), params, scratch_dir=None, **kwargs)
    downloads = Path.home() / "Downloads" / "Data" / "Tests"
    assert downloads in Path(paths[2]).parents
