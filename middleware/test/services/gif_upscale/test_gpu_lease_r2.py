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


def test_unrouted_try_admit_does_not_run_on_a_card_it_does_not_hold() -> None:
    """Training, neural upscalers, and Comfy receive only success or refusal.

    They then execute on their own device (``device_name`` or generic ``cuda``).
    A GIF job holding cuda:0 must keep that caller off every card, and a granted
    caller must hold every card so it cannot execute on one the lease did not give.
    """
    from middleware.src.comfy_matrix import try_admit

    lease = GpuLeaseArbiter(devices=_TABLE)
    assert lease.try_acquire("gif", device=0) is True
    refusal = try_admit("gan-train", lease, estimated_gb=1.0)
    assert refusal is not None
    assert "gif" in refusal
    assert lease.devices_for("gan-train") == ()
    lease.release("gif", device=0)

    assert try_admit("gan-train", lease, estimated_gb=1.0) is None
    assert lease.devices_for("gan-train") == (0, 1)
    assert lease.try_acquire("gif-other", device=1) is False
    lease.release("gan-train")
    assert lease.devices_for("gan-train") == ()
    assert lease.owner is None
    assert lease.try_acquire("gif-other", device=0) is True
    lease.release("gif-other", device=0)


def test_comfy_sweep_holds_every_card_while_it_submits() -> None:
    """Comfy execution is not placed on the device ``try_acquire`` would pick."""
    from middleware.src.comfy_matrix import run_matrix_sweep

    lease = GpuLeaseArbiter(devices=_TABLE)
    held: list[tuple[int, ...]] = []
    workflow = {
        "1": {"class_type": "KSampler", "inputs": {"seed": 1, "steps": 1, "cfg": 1.0}},
        "2": {"class_type": "EmptyLatentImage", "inputs": {"width": 8, "height": 8}},
    }

    def queue(_workflow: dict, _meta: dict) -> str:
        held.append(lease.devices_for("matrix"))
        return "prompt-1"

    result = run_matrix_sweep(
        workflow=workflow,
        axis="seed",
        values=[1],
        queue=queue,
        wait_for_completion=lambda _prompt: True,
        preview_edge=8,
        lease=lease,
        pressure_check=lambda: False,
    )
    assert result.stopped is None
    assert held == [(0, 1)]
    assert lease.devices_for("matrix") == ()
    assert lease.try_acquire("gif", device=0) is True
    lease.release("gif", device=0)


def test_first_attach_cannot_leave_a_slotless_legacy_owner() -> None:
    """Deterministic race: observe no table, then attach, then the acquire commits.

    The old order took the legacy mutex after the table existed. Release then
    looked for a device slot, found none, and left the legacy lock held.
    """
    import threading

    from middleware.src.comfy_matrix import try_admit

    lease = GpuLeaseArbiter()
    entered = threading.Event()
    attached = threading.Event()
    real = lease._transition
    main = threading.current_thread()

    class _Gate:
        def __init__(self) -> None:
            self._arm = True

        def acquire(self, blocking: bool = True, timeout: float = -1) -> bool:
            if self._arm and threading.current_thread() is main:
                self._arm = False
                entered.set()
                assert attached.wait(2)
            if timeout == -1:
                return real.acquire(blocking)
            return real.acquire(blocking, timeout)

        def release(self) -> None:
            real.release()

        def locked(self) -> bool:
            return real.locked()

        def __enter__(self) -> "_Gate":
            self.acquire()
            return self

        def __exit__(self, *_args: object) -> bool:
            self.release()
            return False

    lease._transition = _Gate()

    def _attach() -> None:
        assert entered.wait(2)
        assert lease.ensure_device_table(_TABLE) is True
        attached.set()

    thread = threading.Thread(target=_attach)
    thread.start()
    assert try_admit("trainer", lease) is None
    thread.join(3)
    assert not thread.is_alive()
    assert lease.devices_for("trainer") == (0, 1)
    assert lease._lock.locked() is False
    lease.release("trainer")
    assert lease.owner is None
    assert lease.snapshot().held_devices == ()
    assert lease._lock.locked() is False
    assert lease.try_acquire("gif", device=0) is True
    lease.release("gif", device=0)


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
