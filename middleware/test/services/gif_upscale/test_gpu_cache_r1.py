"""R1 (#1170): closing a GIF GPU session returns cached VRAM.

The real-CUDA test is skipped when CUDA is unavailable. It uses whichever
device this process calls cuda:0. Run it with CUDA_VISIBLE_DEVICES=0 so
the shared cuda:1 card is not in the process. Reserved bytes after close
must fall back near the starting value (the old bug left about 1 GB).
A fake session covers the hook and the tensor drop with no device.
"""

from __future__ import annotations

import gc

import numpy as np
import pytest
from middleware.src.core.gpu_lease_arbiter import GpuLeaseArbiter, release_unused_cuda_blocks
from middleware.src.services.media.gif_upscale.gpu_batch import GpuResampleSession

_SLACK_BYTES = 64 * 1024 * 1024


def _cuda_available() -> bool:
    try:
        import torch
    except ImportError:
        return False
    cuda = getattr(torch, "cuda", None)
    return bool(cuda is not None and cuda.is_available())


def test_close_drops_tensors_and_runs_the_lease_hook() -> None:
    calls: list[str] = []
    arbiter = GpuLeaseArbiter(
        devices=({"index": 0, "total_gb": 8.0, "free_gb": 8.0},),
        empty_cache=lambda: calls.append("empty"),
    )
    assert arbiter.try_acquire("gif", device=0)
    session = GpuResampleSession.__new__(GpuResampleSession)
    session._closed = False
    session.arbiter = arbiter
    session.owner = "gif"
    session.device_index = 0
    for name in (
        "wx_t",
        "wy_t",
        "src_x_t",
        "src_y_t",
        "x_index_t",
        "x_weight_t",
        "x_valid_t",
        "y_index_t",
        "y_weight_t",
        "y_valid_t",
        "_bayer_t",
        "_pal_t",
        "_half_t",
        "_lut_t",
    ):
        setattr(session, name, object())
    session.close()
    assert calls == ["empty"]
    assert session._closed is True
    assert session.x_index_t is None
    assert session.y_weight_t is None
    assert session._lut_t is None
    assert session.wx_t is None
    assert arbiter.snapshot().held_devices == ()
    session.close()
    assert calls == ["empty"]


def test_close_without_a_hook_still_releases_the_lease() -> None:
    arbiter = GpuLeaseArbiter(devices=({"index": 0, "total_gb": 8.0, "free_gb": 8.0},))
    assert arbiter.try_acquire("gif", device=0)
    session = GpuResampleSession.__new__(GpuResampleSession)
    session._closed = False
    session.arbiter = arbiter
    session.owner = "gif"
    session.device_index = 0
    session.close()
    assert arbiter.snapshot().held_devices == ()
    assert arbiter.release_cached_memory() is None


@pytest.mark.skipif(not _cuda_available(), reason="CUDA is required to measure reserved VRAM")
def test_close_returns_reserved_vram_near_the_start() -> None:
    import torch
    from middleware.src.comfy_matrix import GpuLease

    torch.cuda.set_device(0)
    gc.collect()
    torch.cuda.empty_cache()
    before = int(torch.cuda.memory_reserved(0))
    free_bytes, _total_bytes = torch.cuda.mem_get_info(0)
    props = torch.cuda.get_device_properties(0)
    arbiter = GpuLease(
        devices=({"index": 0, "total_gb": props.total_memory / (1024**3), "free_gb": free_bytes / (1024**3)},),
        empty_cache=release_unused_cuda_blocks,
    )
    assert arbiter.try_acquire("gif-r1", device=0)
    try:
        session = GpuResampleSession(
            arbiter=arbiter,
            owner="gif-r1",
            device_index=0,
            free_gb=free_bytes / (1024**3),
            src_h=48,
            src_w=64,
            dst_h=96,
            dst_w=128,
            opts={"params": {}},
            batch_size=4,
        )
        frames = [np.full((48, 64, 4), 255, dtype=np.uint8) for _ in range(4)]
        session.scale_batch_uint8(frames)
        torch.cuda.synchronize(0)
        during = int(torch.cuda.memory_reserved(0))
        session.close()
    except Exception:
        arbiter.release("gif-r1", device=0)
        raise
    del session
    gc.collect()
    after = int(torch.cuda.memory_reserved(0))
    print(f"R1 reserved bytes before={before} during={during} after={after}")
    assert during >= before
    assert after <= before + _SLACK_BYTES
    if during > before + _SLACK_BYTES:
        assert after < during
