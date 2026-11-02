"""R2 (#1171): GIF GPU jobs take the process shared lease.

These tests do not touch a CUDA device. Another process (ComfyUI on cuda:1)
is not a holder of this in-process lease; only the free-VRAM probe at acquire
time sees it, and that probe is not run here.
"""

from __future__ import annotations

import pytest
from middleware.src.core.gpu_lease_arbiter import GpuLeaseArbiter
from middleware.src.services.media.gif_upscale.gpu_batch import acquire_gpu_session, resolve_gif_arbiter
from middleware.src.services.media.gif_upscale.gpu_schedule import acquire_gpu_sessions
from middleware.src.services.media.gif_upscale.pipeline import _finish_message, _path_record

_TABLE = (
    {"index": 0, "total_gb": 24.0, "free_gb": 20.0},
    {"index": 1, "total_gb": 24.0, "free_gb": 10.0},
)
_STAGES = ("decode", "palette", "scale", "index", "lzw")


class _FakeSession:
    def __init__(self, **kwargs: object) -> None:
        self.arbiter = kwargs["arbiter"]
        self.owner = kwargs["owner"]
        self.device_index = kwargs["device_index"]
        self.opts = kwargs["opts"]
        self.device_name = f"cuda:{self.device_index}"
        self.scale_path = "gpu-sgemm-lut"
        self.closed = False

    def close(self) -> None:
        self.closed = True
        self.arbiter.release(self.owner, device=self.device_index)


def _cuda_ready(monkeypatch: pytest.MonkeyPatch) -> None:
    torch = pytest.importorskip("torch")
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(
        "middleware.src.services.media.gif_upscale.gpu_batch.GpuResampleSession",
        _FakeSession,
    )
    monkeypatch.setattr(
        "middleware.src.services.media.gif_upscale.gpu_schedule.cuda_device_table",
        lambda: _TABLE,
    )
    monkeypatch.setattr(
        "middleware.src.services.media.gif_upscale.gpu_batch.cuda_device_table",
        lambda: _TABLE,
    )


def test_legacy_holder_blocks_device_table_until_release() -> None:
    lease = GpuLeaseArbiter()
    assert lease.try_acquire("trainer")
    assert lease.ensure_device_table(_TABLE) is False
    assert lease.device_indexes() is None
    assert lease.owner == "trainer"
    lease.release("trainer")
    assert lease.ensure_device_table(_TABLE) is True
    assert lease.device_indexes() == (0, 1)


def test_allow_devices_limits_one_acquire() -> None:
    lease = GpuLeaseArbiter()
    assert lease.ensure_device_table(_TABLE) is True
    assert lease.try_acquire("gif", allow_devices=(1,)) is True
    assert lease.device_for("gif") == 1
    assert lease.try_acquire("other", device=0) is True


def test_import_failure_uses_a_standalone_arbiter() -> None:
    def broken() -> GpuLeaseArbiter:
        raise ImportError("comfy_matrix is unavailable")

    arbiter, source = resolve_gif_arbiter(_TABLE[:1], allow_devices=(0,), shared_loader=broken)
    assert source == "standalone"
    assert arbiter.device_indexes() == (0,)
    assert arbiter.try_acquire("gif", device=0) is True
    assert arbiter.snapshot().held_devices == ((0, "gif"),)


def test_held_shared_lease_names_the_holder(monkeypatch: pytest.MonkeyPatch) -> None:
    _cuda_ready(monkeypatch)
    shared = GpuLeaseArbiter()
    assert shared.try_acquire("trainer")
    monkeypatch.setattr(
        "middleware.src.services.media.gif_upscale.gpu_batch._load_shared_gif_lease",
        lambda: shared,
    )
    opts: dict = {"params": {"device": "cuda:0"}}
    session, reason = acquire_gpu_session(src_h=4, src_w=4, dst_h=8, dst_w=8, opts=opts)
    assert session is None
    assert reason is not None
    assert "trainer" in reason
    assert "fell back to cpu" in reason.lower()
    assert opts["_gpu_lease"] == "shared"
    assert opts["_device"] == "cpu"
    assert shared.owner == "trainer"
    path = _path_record(opts, "lanczos3-dering", "mediancut")
    message = _finish_message(8, 8, "out.gif", path, dict.fromkeys(_STAGES, 0.0), opts.get("_gpu_fallback"))
    assert "lease=shared" in message
    assert "trainer" in message


def test_gif_lease_is_visible_on_the_shared_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    _cuda_ready(monkeypatch)
    shared = GpuLeaseArbiter()
    monkeypatch.setattr(
        "middleware.src.services.media.gif_upscale.gpu_batch._load_shared_gif_lease",
        lambda: shared,
    )
    opts: dict = {"params": {}}
    sessions, reason = acquire_gpu_sessions(src_h=4, src_w=4, dst_h=8, dst_w=8, opts=opts)
    assert reason is None
    assert len(sessions) == 2
    held = dict(shared.snapshot().held_devices)
    assert set(held) == {0, 1}
    assert opts["_gpu_lease"] == "shared"
    assert "lease=shared" in _finish_message(
        8,
        8,
        "out.gif",
        _path_record(opts, "lanczos3-dering", "mediancut"),
        dict.fromkeys(_STAGES, 0.0),
    )
    for session in sessions:
        session.close()
    assert shared.snapshot().held_devices == ()


def test_explicit_arbiter_does_not_use_the_shared_lease(monkeypatch: pytest.MonkeyPatch) -> None:
    _cuda_ready(monkeypatch)

    def forbidden() -> GpuLeaseArbiter:
        raise AssertionError("explicit arbiter must not load the shared lease")

    monkeypatch.setattr(
        "middleware.src.services.media.gif_upscale.gpu_batch._load_shared_gif_lease",
        forbidden,
    )
    explicit = GpuLeaseArbiter(devices=_TABLE[:1])
    opts: dict = {"params": {}}
    session, reason = acquire_gpu_session(
        src_h=4, src_w=4, dst_h=8, dst_w=8, opts=opts, arbiter=explicit
    )
    assert reason is None
    assert session is not None
    assert session.arbiter is explicit
    assert opts["_gpu_lease"] == "explicit"
    assert explicit.snapshot().held_devices == ((0, session.owner),)
