"""R1 (#1170): closing a GIF GPU session returns cached VRAM.

The real-CUDA test is skipped when CUDA is unavailable. It uses whichever
device this process calls cuda:0. Run it with CUDA_VISIBLE_DEVICES=0 so
the shared cuda:1 card is not in the process. Reserved bytes after close
must fall by at least half the growth this run observed. A fixed 64 MiB
allowance used to accept a fully retained ~24 MiB allocation.
A fake session covers the hook and the tensor drop with no device.
"""

from __future__ import annotations

import gc

import numpy as np
import pytest
from middleware.src.core.gpu_lease_arbiter import GpuLeaseArbiter, release_unused_cuda_blocks
from middleware.src.services.media.gif_upscale.gpu_batch import GpuResampleSession, acquire_gpu_session


def _reserved_fell(before: int, during: int, after: int) -> bool:
    """The reserved drop has to be at least half the growth this run observed.

    A fixed 64 MiB allowance accepted a fully retained ~24 MiB allocation,
    and the old strict check ran only when the growth exceeded that allowance.
    """
    grown = during - before
    if grown <= 0:
        return False
    return after <= before + grown // 2


def _cuda_available() -> bool:
    try:
        import torch
    except ImportError:
        return False
    cuda = getattr(torch, "cuda", None)
    return bool(cuda is not None and cuda.is_available())


def test_sixty_four_mib_slack_accepts_a_retained_24_mib_block() -> None:
    before, during = 0, 24 * 1024 * 1024
    retained = during
    old_slack = 64 * 1024 * 1024
    old_passes = retained <= before + old_slack and not (during > before + old_slack)
    assert old_passes
    assert _reserved_fell(before, during, retained) is False
    assert _reserved_fell(before, during, before) is True


def test_close_inside_except_drops_traceback_tensors_before_the_flush() -> None:
    """A GPU exception's traceback keeps the batch tensors alive across close().

    The flush has to run after those tensors are dropped. A later close() used
    to return immediately, so the blocks stayed in the caching allocator.
    """
    order: list[str] = []

    class _Marker:
        def __del__(self) -> None:
            order.append("dead")

    arbiter = GpuLeaseArbiter(
        devices=({"index": 0, "total_gb": 8.0, "free_gb": 8.0},),
        empty_cache=lambda: order.append("flush"),
    )
    assert arbiter.try_acquire("gif", device=0)
    session = GpuResampleSession.__new__(GpuResampleSession)
    session._closed = False
    session.arbiter = arbiter
    session.owner = "gif"
    session.device_index = 0

    def _blow() -> None:
        _marker = _Marker()
        raise RuntimeError("batch")

    try:
        _blow()
    except RuntimeError:
        session.close()
    assert order == ["dead", "flush"]
    assert arbiter.snapshot().held_devices == ()


def test_constructor_failure_flushes_after_the_partial_object_is_dropped(monkeypatch: pytest.MonkeyPatch) -> None:
    torch = pytest.importorskip("torch")
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    order: list[str] = []

    class _Marker:
        def __del__(self) -> None:
            order.append("dead")

    arbiter = GpuLeaseArbiter(
        devices=({"index": 0, "total_gb": 8.0, "free_gb": 8.0},),
        empty_cache=lambda: order.append("flush"),
    )

    def _boom(self: GpuResampleSession, **_kwargs: object) -> None:
        self._marker = _Marker()
        raise RuntimeError("init failed after alloc")

    monkeypatch.setattr(GpuResampleSession, "__init__", _boom)
    session, reason = acquire_gpu_session(
        src_h=4,
        src_w=4,
        dst_h=8,
        dst_w=8,
        opts={"params": {"device": "cuda:0"}},
        arbiter=arbiter,
        owner="gif-init",
    )
    assert session is None
    assert reason is not None and "init failed after alloc" in reason
    assert order[:2] == ["dead", "flush"]
    assert arbiter.snapshot().held_devices == ()


def test_cublas_clear_is_skipped_while_another_device_is_held(monkeypatch: pytest.MonkeyPatch) -> None:
    cleared: list[bool] = []
    monkeypatch.setattr(
        "middleware.src.services.media.gif_upscale.gpu_batch._clear_cublas_workspace",
        lambda _torch: cleared.append(True),
    )
    arbiter = GpuLeaseArbiter(
        devices=(
            {"index": 0, "total_gb": 8.0, "free_gb": 8.0},
            {"index": 1, "total_gb": 8.0, "free_gb": 8.0},
        )
    )
    assert arbiter.try_acquire("gif-a", device=0)
    assert arbiter.try_acquire("gif-b", device=1)

    def _fake(owner: str, device: int) -> GpuResampleSession:
        session = GpuResampleSession.__new__(GpuResampleSession)
        session._closed = False
        session.arbiter = arbiter
        session.owner = owner
        session.device_index = device
        session._torch = object()
        return session

    first = _fake("gif-a", 0)
    second = _fake("gif-b", 1)
    first.close()
    assert cleared == []
    second.close()
    assert cleared == [True]
    assert arbiter.snapshot().held_devices == ()


def test_cublas_clear_is_skipped_while_another_session_is_open(monkeypatch: pytest.MonkeyPatch) -> None:
    from middleware.src.services.media.gif_upscale import gpu_batch

    cleared: list[bool] = []
    monkeypatch.setattr(gpu_batch, "_clear_cublas_workspace", lambda _torch: cleared.append(True))
    gpu_batch._retain_open_session()
    try:
        arbiter = GpuLeaseArbiter(devices=({"index": 0, "total_gb": 8.0, "free_gb": 8.0},))
        assert arbiter.try_acquire("gif", device=0)
        session = GpuResampleSession.__new__(GpuResampleSession)
        session._closed = False
        session._counted = False
        session.arbiter = arbiter
        session.owner = "gif"
        session.device_index = 0
        session._torch = object()
        session.close()
        assert cleared == []
        assert arbiter.snapshot().held_devices == ()
    finally:
        gpu_batch._release_open_session()


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
    assert _reserved_fell(before, during, after)


@pytest.mark.skipif(not _cuda_available(), reason="CUDA is required to measure reserved VRAM")
def test_failed_init_returns_the_observed_block(monkeypatch: pytest.MonkeyPatch) -> None:
    import torch

    torch.cuda.set_device(0)
    gc.collect()
    torch.cuda.empty_cache()
    before = int(torch.cuda.memory_reserved(0))
    seen: dict[str, int] = {}
    free_bytes, _total = torch.cuda.mem_get_info(0)
    props = torch.cuda.get_device_properties(0)
    arbiter = GpuLeaseArbiter(
        devices=({"index": 0, "total_gb": props.total_memory / (1024**3), "free_gb": free_bytes / (1024**3)},),
        empty_cache=release_unused_cuda_blocks,
    )

    def _boom(self: GpuResampleSession, **_kwargs: object) -> None:
        self.wx_t = torch.empty(32 * 1024 * 1024, dtype=torch.uint8, device="cuda:0")
        torch.cuda.synchronize(0)
        seen["during"] = int(torch.cuda.memory_reserved(0))
        raise RuntimeError("init failed after alloc")

    monkeypatch.setattr(GpuResampleSession, "__init__", _boom)
    session, reason = acquire_gpu_session(
        src_h=4,
        src_w=4,
        dst_h=8,
        dst_w=8,
        opts={"params": {"device": "cuda:0"}},
        arbiter=arbiter,
        owner="gif-init",
    )
    assert session is None
    assert reason is not None and "init failed after alloc" in reason
    gc.collect()
    after = int(torch.cuda.memory_reserved(0))
    print(f"R1 init-fail reserved before={before} during={seen['during']} after={after}")
    assert _reserved_fell(before, seen["during"], after)
    assert arbiter.snapshot().held_devices == ()


@pytest.mark.skipif(not _cuda_available(), reason="CUDA is required to measure reserved VRAM")
def test_close_inside_except_returns_the_observed_block() -> None:
    import torch

    torch.cuda.set_device(0)
    gc.collect()
    torch.cuda.empty_cache()
    before = int(torch.cuda.memory_reserved(0))
    seen: dict[str, int] = {}
    free_bytes, _total = torch.cuda.mem_get_info(0)
    props = torch.cuda.get_device_properties(0)
    arbiter = GpuLeaseArbiter(
        devices=({"index": 0, "total_gb": props.total_memory / (1024**3), "free_gb": free_bytes / (1024**3)},),
        empty_cache=release_unused_cuda_blocks,
    )
    assert arbiter.try_acquire("gif-r1", device=0)
    session = GpuResampleSession.__new__(GpuResampleSession)
    session._closed = False
    session._counted = False
    session.arbiter = arbiter
    session.owner = "gif-r1"
    session.device_index = 0
    session._torch = torch

    def _blow() -> None:
        _blob = torch.empty(32 * 1024 * 1024, dtype=torch.uint8, device="cuda:0")
        torch.cuda.synchronize(0)
        seen["during"] = int(torch.cuda.memory_reserved(0))
        raise RuntimeError("batch")

    try:
        _blow()
    except RuntimeError:
        session.close()
    gc.collect()
    after = int(torch.cuda.memory_reserved(0))
    print(f"R1 except-close reserved before={before} during={seen['during']} after={after}")
    assert _reserved_fell(before, seen["during"], after)
    assert arbiter.snapshot().held_devices == ()
