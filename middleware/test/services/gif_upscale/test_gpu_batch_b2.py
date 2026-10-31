"""Tests for Task B2 (#1155): GPU batch scale + on-device Bayer dither and nearest-palette index."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from middleware.src.core.gpu_lease_arbiter import GpuLeaseArbiter
from middleware.src.services.media.gif_upscale import encode
from middleware.src.services.media.gif_upscale.base import ResampleCancelled
from middleware.src.services.media.gif_upscale.classical._resize import (
    _clip_plan,
    _ensure_sgemm,
    _resize_lanczos_sgemm,
    lanczos_kernel,
)
from middleware.src.services.media.gif_upscale.encode import (
    build_palette_lut,
    index_frame,
)
from middleware.src.services.media.gif_upscale.gpu_batch import (
    acquire_gpu_session,
    compute_gpu_batch_size,
)
from middleware.src.services.media.gif_upscale.io import decode_gif
from middleware.src.services.media.gif_upscale.pipeline import resample_gif
from PIL import Image


def _cuda_ready() -> bool:
    try:
        import torch

        return bool(torch.cuda.is_available() and torch.cuda.device_count() > 0)
    except Exception:
        return False


def test_compute_gpu_batch_size_scales_with_free_vram_and_cap() -> None:
    small = compute_gpu_batch_size(1.0, 400, 720, 800, 1440, quality="balanced")
    large = compute_gpu_batch_size(12.0, 400, 720, 800, 1440, quality="balanced")
    capped = compute_gpu_batch_size(20.0, 400, 720, 800, 1440, quality="balanced", vram_cap_gb=1.0)
    tiny = compute_gpu_batch_size(0.1, 400, 720, 800, 1440, quality="exact")
    assert 1 <= small < large <= 64
    assert capped == small
    assert tiny == 1


@pytest.mark.skipif(not _cuda_ready(), reason="CUDA required for on-device GPU tests")
@pytest.mark.parametrize("shape", [((20, 32), (40, 64)), ((19, 33), (39, 67))])
@pytest.mark.parametrize("translucent", [False, True])
def test_gpu_scale_and_index_matches_cpu_reference_and_breaks_ties(
    shape: tuple[tuple[int, int], tuple[int, int]],
    translucent: bool,
) -> None:
    """Check opaque/translucent edges, odd sizes, impulse/checkerboard, and deterministic palette ties."""
    (src_h, src_w), (dst_h, dst_w) = shape
    rng = np.random.default_rng(1155)

    # Frame 0: random gradient + step edge; Frame 1: impulse + checkerboard; Frame 2: identical to Frame 0 (temporal stability)
    f0 = rng.integers(0, 256, size=(src_h, src_w, 4), dtype=np.uint8)
    f0[:, src_w // 2 :, :3] = 240
    f0[..., 3] = 255

    f1 = np.zeros((src_h, src_w, 4), dtype=np.uint8)
    f1[::2, ::2, :3] = 255
    f1[1::2, 1::2, :3] = 255
    f1[src_h // 2, src_w // 2, :3] = [255, 128, 64]
    f1[..., 3] = 255

    if translucent:
        f0[:4, :5, 3] = 0
        f0[4:8, :, 3] = 180
        f1[:3, :3, 3] = 40

    f2 = f0.copy()
    frames_u8 = [f0, f1, f2]

    # Palette with deliberate duplicate/equidistant entries to verify deterministic tie-breaking
    palette = rng.integers(0, 256, size=(256, 3), dtype=np.uint8).astype(np.float32)
    palette[0] = [0.0, 0.0, 0.0]
    palette[15] = [100.0, 100.0, 100.0]
    palette[90] = [100.0, 100.0, 100.0]

    arbiter = GpuLeaseArbiter(devices=({"index": 0, "total_gb": 24.0, "free_gb": 16.0},))
    for quality in ("balanced", "exact", "fast"):
        opts: dict = {"size": (dst_w, dst_h), "params": {"quality": quality, "gpu_arbiter": arbiter}}
        session, reason = acquire_gpu_session(
            src_h=src_h,
            src_w=src_w,
            dst_h=dst_h,
            dst_w=dst_w,
            opts=opts,
            arbiter=arbiter,
        )
        assert session is not None and reason is None
        try:
            # 1. Float scale equivalence against CPU
            gpu_floats = session.scale_batch_float(frames_u8)
            plan = _clip_plan({}, "lanczos3-dering", src_h, src_w, dst_h, dst_w, 3.0, lanczos_kernel(3.0))
            _ensure_sgemm(plan)
            if quality != "exact":
                cpu_f0 = _resize_lanczos_sgemm(
                    f0.astype(np.float32) / 255.0,
                    plan,
                    "lanczos3-dering",
                    clip_unit=True,
                    strength=1.0 if quality == "fast" else None,
                )
                visible = cpu_f0[..., 3] > 0.0
                max_diff = float(np.max(np.abs(gpu_floats[0][visible] - cpu_f0[visible])))
                assert max_diff <= 1.0 / 255.0

            # 2. On-device dither + palette index equivalence against CPU index_frame on the same scaled uint8 frames
            session.prepare_palette(palette, transparent=True, dither="ordered", quality=quality)
            indices_gpu, scale_s, index_s = session.scale_and_index_batch(frames_u8)
            assert scale_s > 0.0 and index_s > 0.0
            assert indices_gpu.shape == (3, dst_h, dst_w)
            assert indices_gpu.dtype == np.uint8

            # Temporal stability: identical input frames f0 and f2 produce bit-identical palette indices
            np.testing.assert_array_equal(indices_gpu[0], indices_gpu[2])

            scaled_u8 = session.scale_batch_uint8(frames_u8)
            lut = build_palette_lut(palette[1:]) if quality != "exact" else None
            for idx_pos in range(len(frames_u8)):
                cpu_idx = index_frame(
                    scaled_u8[idx_pos],
                    palette,
                    transparent=True,
                    dither="ordered",
                    quality=quality,
                    lut=lut,
                )
                np.testing.assert_array_equal(indices_gpu[idx_pos], cpu_idx)
        finally:
            session.close()
        assert arbiter.devices_for(session.owner) == ()


def test_stream_gpu_fallback_when_arbiter_refuses_and_cancel_releases_lease(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(encode, "STREAM_RGBA_BYTES", 1)
    source = tmp_path / "clip.gif"
    frames = [Image.new("RGB", (16, 12), (i * 20 % 256, 50, 200 - i * 15 % 200)) for i in range(6)]
    frames[0].save(source, format="GIF", save_all=True, append_images=frames[1:], duration=40, loop=0, disposal=2)
    for im in frames:
        im.close()

    # 1. Held arbiter forces CPU fallback with an explicit message (D12, D13)
    held_arbiter = GpuLeaseArbiter(devices=({"index": 0, "total_gb": 24.0, "free_gb": 16.0},))
    assert held_arbiter.try_acquire("comfy_job", device=0) is True
    out_fallback = tmp_path / "fallback.gif"
    res_fallback = resample_gif(
        str(source),
        str(out_fallback),
        {
            "algorithm": "lanczos3-dering",
            "mode": "factor",
            "factor": 2,
            "gpu_arbiter": held_arbiter,
        },
    )
    assert res_fallback["success"] is True
    assert res_fallback["path"]["device"] == "cpu"
    assert "fallback=" in res_fallback["message"]
    if _cuda_ready():
        assert "comfy_job" in res_fallback["message"]
    else:
        assert "CUDA is unavailable" in res_fallback["message"]
    assert out_fallback.exists()

    # 2. When arbiter is free and CUDA is ready, GPU runs and cancel releases the lease and removes partial output
    if _cuda_ready():
        free_arbiter = GpuLeaseArbiter(devices=({"index": 0, "total_gb": 24.0, "free_gb": 16.0},))
        out_gpu = tmp_path / "gpu.gif"
        res_gpu = resample_gif(
            str(source),
            str(out_gpu),
            {
                "algorithm": "lanczos3-dering",
                "mode": "factor",
                "factor": 2,
                "gpu_arbiter": free_arbiter,
            },
        )
        assert res_gpu["success"] is True
        assert res_gpu["path"]["device"] == "cuda:0"
        assert res_gpu["path"]["kernel"].startswith("gpu-sgemm-")
        assert free_arbiter.snapshot().held_devices == ()
        clip_gpu = decode_gif(str(out_gpu))
        clip_cpu = decode_gif(str(out_fallback))
        assert len(clip_gpu.frames) == 6
        for fg, fc in zip(clip_gpu.frames, clip_cpu.frames, strict=True):
            # Decoded GIF RGB matches CPU output (0.0 mean difference on identical quantization)
            assert float(np.abs(fg.astype(np.float32) - fc.astype(np.float32)).mean()) <= 1.0

        partial = tmp_path / "partial.gif"
        seen_calls = {"n": 0}

        def cancel_on_third(stage: str, done: int, total: int) -> None:
            del done, total
            if stage == "scale_encode":
                seen_calls["n"] += 1
                if seen_calls["n"] >= 3:
                    raise ResampleCancelled

        with pytest.raises(ResampleCancelled):
            resample_gif(
                str(source),
                str(partial),
                {
                    "algorithm": "lanczos3-dering",
                    "mode": "factor",
                    "factor": 2,
                    "gpu_arbiter": free_arbiter,
                    "progress": cancel_on_third,
                },
            )
        assert seen_calls["n"] == 3
        assert not partial.exists()
        assert free_arbiter.snapshot().held_devices == ()


def test_in_memory_gif_gpu_and_fallback(tmp_path: Path) -> None:
    source = tmp_path / "small.gif"
    frames = [Image.new("RGB", (12, 8), (i * 40 % 256, 100, 200)) for i in range(4)]
    frames[0].save(source, format="GIF", save_all=True, append_images=frames[1:], duration=50, loop=0, disposal=2)
    for im in frames:
        im.close()

    held_arbiter = GpuLeaseArbiter(devices=({"index": 0, "total_gb": 24.0, "free_gb": 16.0},))
    assert held_arbiter.try_acquire("other_job", device=0) is True
    out_fb = tmp_path / "small_fb.gif"
    res_fb = resample_gif(
        str(source),
        str(out_fb),
        {"algorithm": "lanczos3-dering", "mode": "factor", "factor": 2, "gpu_arbiter": held_arbiter},
    )
    assert res_fb["success"] is True
    assert res_fb["path"]["device"] == "cpu"
    assert "fallback=" in res_fb["message"]

    if _cuda_ready():
        free_arbiter = GpuLeaseArbiter(devices=({"index": 0, "total_gb": 24.0, "free_gb": 16.0},))
        out_gpu = tmp_path / "small_gpu.gif"
        res_gpu = resample_gif(
            str(source),
            str(out_gpu),
            {"algorithm": "lanczos3-dering", "mode": "factor", "factor": 2, "gpu_arbiter": free_arbiter},
        )
        assert res_gpu["success"] is True
        assert res_gpu["path"]["device"] == "cuda:0"
        assert res_gpu["path"]["kernel"].startswith("gpu-sgemm-")
        assert res_gpu["timings"]["index"] > 0.0
        assert free_arbiter.snapshot().held_devices == ()
