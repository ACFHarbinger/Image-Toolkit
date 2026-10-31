"""GpuLeaseArbiter occupancy rules beyond one exclusive job (#758, #1154)."""
from __future__ import annotations

import pytest

from middleware.src.core.gpu_lease_arbiter import (
    CONSERVATIVE_VRAM_FRACTION,
    KIND_GENERATE,
    KIND_OTHER,
    KIND_TRAIN,
    PROFILE_BALANCED,
    PROFILE_CONSERVATIVE,
    GpuLeaseArbiter,
    infer_kind,
    parse_profile,
    profile_from_env,
    release_unused_cuda_blocks,
)
from middleware.src.core.gpu_vram_calibration import clear, owner_scale

# Index 0 is the smaller free pool on purpose: a picker that ignores free VRAM
# or an allow-list would hand it out first.
_TWO_DEVICES = (
    {"index": 0, "total_gb": 24.0, "free_gb": 4.0},
    {"index": 1, "total_gb": 24.0, "free_gb": 20.0},
)


@pytest.fixture(autouse=True)
def _reset_calibration(monkeypatch):
    clear()
    monkeypatch.delenv("IMAGE_TOOLKIT_GPU_DEVICES", raising=False)
    yield
    clear()


def test_infer_kind_from_owner():
    assert infer_kind("lora-train") == KIND_TRAIN
    assert infer_kind("cbir-train") == KIND_TRAIN
    assert infer_kind("lora-generate") == KIND_GENERATE
    assert infer_kind("guided") == KIND_GENERATE
    assert infer_kind("matrix") == KIND_GENERATE
    assert infer_kind("dataset-advisor") == KIND_OTHER
    assert infer_kind("custom", kind=KIND_TRAIN) == KIND_TRAIN


def test_parse_profile_rejects_unknown():
    assert parse_profile("balanced") == PROFILE_BALANCED
    assert parse_profile(" Conservative ") == PROFILE_CONSERVATIVE
    with pytest.raises(ValueError, match="balanced"):
        parse_profile("aggressive")


def test_profile_from_env_defaults_to_balanced(monkeypatch):
    monkeypatch.delenv("IMAGE_TOOLKIT_GPU_PROFILE", raising=False)
    assert profile_from_env() == PROFILE_BALANCED
    monkeypatch.setenv("IMAGE_TOOLKIT_GPU_PROFILE", "conservative")
    assert profile_from_env() == PROFILE_CONSERVATIVE


def test_balanced_keeps_exclusive_mutex_and_ignores_browser():
    lease = GpuLeaseArbiter(device_total_gb=16.0)
    lease.note_external_browser(True)
    assert lease.machine_wide is False
    assert lease.try_acquire("lora-train", estimated_gb=15.0)
    assert lease.owner == "lora-train"
    assert lease.try_acquire("matrix") is False
    assert lease.refusal_text() == "GPU admission is held by lora-train."
    lease.release("lora-train")
    assert lease.owner is None
    assert lease.try_acquire("matrix")
    lease.release("matrix")


def test_conservative_refuses_while_comfy_browser_is_noted():
    lease = GpuLeaseArbiter(profile=PROFILE_CONSERVATIVE, device_total_gb=16.0)
    lease.note_external_browser(True)
    assert lease.try_acquire("lora-train") is False
    assert lease.owner is None
    assert "browser" in lease.refusal_text().lower()
    assert "conservative" in lease.refusal_text().lower()
    lease.note_external_browser(False)
    assert lease.try_acquire("lora-train")
    lease.release("lora-train")


def test_conservative_refuses_estimate_above_device_fraction():
    lease = GpuLeaseArbiter(profile=PROFILE_CONSERVATIVE, device_total_gb=16.0)
    ceiling = CONSERVATIVE_VRAM_FRACTION * 16.0
    assert lease.try_acquire("lora-train", estimated_gb=ceiling) is True
    lease.release("lora-train")
    assert lease.try_acquire("lora-train", estimated_gb=ceiling + 0.1) is False
    assert lease.owner is None
    assert "14.5 GB" in lease.refusal_text() or "estimated" in lease.refusal_text()
    assert "conservative" in lease.refusal_text().lower()


def test_balanced_admits_an_estimate_that_conservative_would_refuse():
    lease = GpuLeaseArbiter(profile=PROFILE_BALANCED, device_total_gb=16.0)
    assert lease.try_acquire("guided", estimated_gb=15.5)
    lease.release("guided")


def test_unknown_device_skips_the_estimate_check():
    lease = GpuLeaseArbiter(profile=PROFILE_CONSERVATIVE)
    assert lease.try_acquire("lora-train", estimated_gb=99.0)
    lease.release("lora-train")


def test_release_records_measured_peak():
    lease = GpuLeaseArbiter(peak_reader=lambda: 3.25)
    assert lease.try_acquire("lora-train", estimated_gb=4.0)
    assert lease.snapshot().estimated_gb == 4.0
    lease.release("lora-train")
    snap = lease.snapshot()
    assert snap.owner is None
    assert snap.measured_peak_gb == 3.25
    assert snap.estimated_gb is None


def test_release_raises_owner_scale_when_peak_exceeds_estimate():
    lease = GpuLeaseArbiter(peak_reader=lambda: 6.0)
    assert lease.try_acquire("lora-generate", estimated_gb=4.0)
    lease.release("lora-generate")
    assert owner_scale("lora-generate") == pytest.approx(1.5)


def test_comfy_release_does_not_calibrate_from_this_process_peak():
    lease = GpuLeaseArbiter(peak_reader=lambda: 9.9)
    assert lease.try_acquire("guided", estimated_gb=4.0)
    lease.release("guided")
    assert owner_scale("guided") == 1.0


def test_release_prefers_explicit_measured_peak():
    lease = GpuLeaseArbiter(peak_reader=lambda: 1.0)
    lease.try_acquire("matrix")
    lease.release("matrix", measured_peak_gb=7.5)
    assert lease.snapshot().measured_peak_gb == 7.5


def test_wrong_owner_does_not_release():
    lease = GpuLeaseArbiter()
    assert lease.try_acquire("lora-train")
    lease.release("matrix")
    assert lease.owner == "lora-train"
    lease.release("lora-train")
    assert lease.owner is None


def test_empty_cache_runs_only_on_kind_transition():
    calls: list[int] = []
    lease = GpuLeaseArbiter(empty_cache=lambda: calls.append(1))
    assert lease.try_acquire("lora-train")
    lease.release("lora-train")
    assert calls == []
    assert lease.try_acquire("cbir-train")
    lease.release("cbir-train")
    assert calls == []
    assert lease.try_acquire("lora-generate")
    lease.release("lora-generate")
    assert calls == [1]
    assert lease.try_acquire("guided")
    lease.release("guided")
    assert calls == [1]


def test_empty_cache_exception_does_not_block_admission():
    def boom() -> None:
        raise RuntimeError("cuda empty_cache failed")

    lease = GpuLeaseArbiter(empty_cache=boom)
    assert lease.try_acquire("lora-train")
    lease.release("lora-train")
    assert lease.try_acquire("lora-generate")
    lease.release("lora-generate")


def test_snapshot_and_scope_text_include_profile():
    lease = GpuLeaseArbiter(profile=PROFILE_CONSERVATIVE, device_total_gb=16.0)
    lease.note_external_browser(True)
    snap = lease.snapshot()
    assert snap.profile == PROFILE_CONSERVATIVE
    assert snap.external_browser is True
    assert snap.device_total_gb == 16.0
    text = lease.scope_text().lower()
    assert "browser" in text
    assert "conservative" in text


def test_set_profile_changes_occupancy_rules():
    lease = GpuLeaseArbiter(device_total_gb=16.0)
    lease.note_external_browser(True)
    assert lease.try_acquire("guided")
    lease.release("guided")
    lease.set_profile(PROFILE_CONSERVATIVE)
    assert lease.try_acquire("guided") is False
    lease.set_profile(PROFILE_BALANCED)
    assert lease.try_acquire("guided")
    lease.release("guided")


def test_release_unused_cuda_blocks_is_a_no_op_without_torch():
    release_unused_cuda_blocks()


def test_snapshot_does_not_probe_cuda():
    calls: list[int] = []
    lease = GpuLeaseArbiter(device_probe=lambda: calls.append(1) or 16.0)
    snap = lease.snapshot()
    assert calls == []
    assert snap.device_total_gb is None


def test_conservative_refuses_an_embedded_comfy_view():
    lease = GpuLeaseArbiter(profile=PROFILE_CONSERVATIVE, device_total_gb=16.0)
    lease.note_embedded_view("comfy-tab", True)
    assert lease.try_acquire("lora-train") is False
    assert "browser" in lease.refusal_text().lower()
    lease.note_embedded_view("comfy-tab", False)
    assert lease.try_acquire("lora-train")
    lease.release("lora-train")


def test_comfy_release_does_not_use_this_process_torch_peak():
    lease = GpuLeaseArbiter(peak_reader=lambda: 9.9)
    assert lease.try_acquire("guided", estimated_gb=4.0)
    lease.release("guided")
    assert lease.snapshot().measured_peak_gb is None
    assert lease.try_acquire("lora-train")
    lease.release("lora-train")
    assert lease.snapshot().measured_peak_gb == 9.9


def test_stale_release_does_not_unlock_the_next_owner():
    lease = GpuLeaseArbiter()
    assert lease.try_acquire("lora-train")
    lease.release("lora-train")
    assert lease.try_acquire("matrix")
    lease.release("lora-train")
    assert lease.owner == "matrix"
    assert lease.try_acquire("guided") is False
    lease.release("matrix")


def test_comfy_matrix_try_admit_keeps_busy_text_and_uses_arbiter_refusals():
    from middleware.src.comfy_matrix import GpuLease, try_admit

    busy = GpuLease()
    assert try_admit("lora-train", busy) is None
    assert try_admit("matrix", busy) == "GPU admission is held by lora-train."
    busy.release("lora-train")

    conservative = GpuLease(profile=PROFILE_CONSERVATIVE, device_total_gb=16.0)
    conservative.note_external_browser(True)
    message = try_admit("lora-train", conservative)
    assert message is not None
    assert "browser" in message.lower()
    assert conservative.owner is None


def test_snapshot_does_not_probe_cuda_on_the_calling_thread():
    calls = []
    lease = GpuLeaseArbiter(device_probe=lambda: calls.append(True) or 16)
    assert lease.snapshot().device_total_gb is None
    assert not calls


def test_comfy_peak_is_not_the_local_torch_peak():
    lease = GpuLeaseArbiter(peak_reader=lambda: 12)
    assert lease.try_acquire("guided")
    lease.release("guided")
    assert lease.snapshot().measured_peak_gb is None


def test_embedded_browser_occupancy_survives_another_view_closing():
    lease = GpuLeaseArbiter(profile=PROFILE_CONSERVATIVE)
    lease.note_embedded_view("one", True)
    lease.note_embedded_view("two", True)
    lease.note_embedded_view("one", False)
    assert not lease.try_acquire("train")
    lease.note_embedded_view("two", False)
    assert lease.try_acquire("train")
    lease.release("train")


def test_concurrent_duplicate_release_reads_peak_once():
    import threading

    entered, proceed = threading.Event(), threading.Event()
    calls, failures = [], []

    def peak():
        calls.append(True)
        entered.set()
        assert proceed.wait(2)
        return 1

    lease = GpuLeaseArbiter(peak_reader=peak)
    assert lease.try_acquire("train")

    def release():
        try:
            lease.release("train")
        except Exception as error:
            failures.append(error)

    one = threading.Thread(target=release)
    two = threading.Thread(target=release)
    one.start()
    assert entered.wait(2)
    two.start()
    proceed.set()
    one.join(3)
    two.join(3)
    assert not failures and len(calls) == 1
    assert lease.try_acquire("next")
    lease.release("next")


def test_multi_device_picks_largest_free_then_the_other():
    lease = GpuLeaseArbiter(devices=_TWO_DEVICES)
    assert lease.free_gb(0) == 4.0
    assert lease.free_gb(1) == 20.0
    assert lease.free_gb(2) is None
    assert lease.try_acquire("first", estimated_gb=30.0)
    assert lease.device_for("first") == 1
    assert lease.free_gb(1) == 20.0
    assert lease.try_acquire("second", estimated_gb=30.0)
    assert lease.device_for("second") == 0
    assert lease.try_acquire("third") is False
    assert lease.owner is None
    assert lease.snapshot().held_devices == ((0, "second"), (1, "first"))


def test_same_owner_may_hold_two_devices():
    lease = GpuLeaseArbiter(devices=_TWO_DEVICES)
    assert lease.try_acquire("worker")
    assert lease.try_acquire("worker")
    assert lease.owner == "worker"
    assert lease.device_for("worker") is None
    assert lease.devices_for("worker") == (0, 1)
    lease.release("worker", device=1)
    assert lease.devices_for("worker") == (0,)
    assert lease.device_for("worker") == 0
    lease.release("someone-else")
    assert lease.device_for("worker") == 0
    lease.release("worker")
    assert lease.owner is None
    assert lease.devices_for("worker") == ()


def test_allow_list_never_returns_an_excluded_device(monkeypatch):
    monkeypatch.setenv("IMAGE_TOOLKIT_GPU_DEVICES", "0,1")
    lease = GpuLeaseArbiter(devices=_TWO_DEVICES, allow_devices=(1,))
    assert lease.try_acquire("only")
    assert lease.device_for("only") == 1
    assert lease.try_acquire("other") is False
    assert lease.try_acquire("other", device=0) is False
    assert "allow" in lease.refusal_text().lower()
    assert lease.devices_for("only") == (1,)
    assert 0 not in lease.devices_for("only")

    monkeypatch.setenv("IMAGE_TOOLKIT_GPU_DEVICES", "1")
    from_env = GpuLeaseArbiter(devices=_TWO_DEVICES)
    assert from_env.try_acquire("only", device=0) is False
    assert from_env.try_acquire("only")
    assert from_env.device_for("only") == 1
    assert from_env.try_acquire("second") is False


def test_conservative_refuses_estimate_above_per_device_fraction():
    devices = (
        {"index": 0, "total_gb": 24.0, "free_gb": 24.0},
        {"index": 1, "total_gb": 24.0, "free_gb": 23.0},
    )
    lease = GpuLeaseArbiter(profile=PROFILE_CONSERVATIVE, devices=devices)
    ceiling = CONSERVATIVE_VRAM_FRACTION * 24.0
    assert lease.try_acquire("job", estimated_gb=ceiling)
    assert lease.device_for("job") == 0
    lease.release("job")
    assert lease.try_acquire("job", estimated_gb=ceiling + 0.1) is False
    assert lease.owner is None
    assert "conservative" in lease.refusal_text().lower()
    assert "estimated" in lease.refusal_text().lower()


def test_conservative_browser_blocks_every_device_and_balanced_does_not():
    lease = GpuLeaseArbiter(profile=PROFILE_CONSERVATIVE, devices=_TWO_DEVICES)
    lease.note_external_browser(True)
    assert lease.try_acquire("a", device=1) is False
    assert lease.try_acquire("b") is False
    lease.note_external_browser(False)
    lease.note_embedded_view("comfy-tab", True)
    assert lease.try_acquire("a") is False
    lease.note_embedded_view("comfy-tab", False)
    lease.set_profile(PROFILE_BALANCED)
    lease.note_external_browser(True)
    assert lease.try_acquire("b", estimated_gb=30.0)
    assert lease.device_for("b") == 1


def test_release_frees_only_that_owners_devices():
    lease = GpuLeaseArbiter(devices=_TWO_DEVICES)
    assert lease.try_acquire("a")
    assert lease.try_acquire("b")
    assert lease.device_for("a") == 1
    assert lease.device_for("b") == 0
    lease.release("a")
    assert lease.devices_for("a") == ()
    assert lease.devices_for("b") == (0,)
    assert lease.owner == "b"
    assert lease.try_acquire("c")
    assert lease.device_for("c") == 1
    lease.release("c")
    lease.release("b", device=0)
    assert lease.owner is None


def test_balanced_skips_a_device_with_no_free_vram():
    devices = (
        {"index": 0, "total_gb": 24.0, "free_gb": 0.0},
        {"index": 1, "total_gb": 24.0, "free_gb": 4.0},
    )
    lease = GpuLeaseArbiter(devices=devices)
    assert lease.try_acquire("job", estimated_gb=100.0)
    assert lease.device_for("job") == 1
    assert lease.try_acquire("other") is False


def test_multi_device_snapshot_does_not_probe():
    calls: list[int] = []
    lease = GpuLeaseArbiter(
        profile=PROFILE_CONSERVATIVE,
        devices=_TWO_DEVICES,
        device_probe=lambda: calls.append(1) or 16.0,
    )
    assert lease.snapshot().device_total_gb is None
    assert lease.try_acquire("a", estimated_gb=3.0)
    snap = lease.snapshot()
    assert snap.owner == "a"
    assert snap.held_devices == ((1, "a"),)
    assert snap.device_total_gb is None
    assert calls == []


def test_legacy_device_argument_does_not_invent_a_table():
    lease = GpuLeaseArbiter(device_total_gb=16.0)
    assert lease.free_gb(0) is None
    assert lease.try_acquire("solo", device=0) is False
    assert "table" in lease.refusal_text()
    assert lease.try_acquire("solo")
    assert lease.owner == "solo"
    assert lease.device_for("solo") is None
    assert lease.devices_for("solo") == ()
    lease.release("solo")


@pytest.mark.parametrize("raw", ["", "   ", "nope", "0,x", "0,", "-1", "1.0"])
def test_bad_device_env_refuses_at_acquire_without_crashing(monkeypatch, raw):
    monkeypatch.setenv("IMAGE_TOOLKIT_GPU_DEVICES", raw)
    lease = GpuLeaseArbiter(devices=_TWO_DEVICES)
    assert lease.try_acquire("job") is False
    assert lease.owner is None
    assert "IMAGE_TOOLKIT_GPU_DEVICES" in lease.refusal_text()


def test_allow_devices_overrides_a_garbage_env(monkeypatch):
    monkeypatch.setenv("IMAGE_TOOLKIT_GPU_DEVICES", "nope")
    lease = GpuLeaseArbiter(devices=_TWO_DEVICES, allow_devices=(0,))
    assert lease.try_acquire("job")
    assert lease.device_for("job") == 0
    assert lease.try_acquire("other") is False


def test_empty_cache_does_not_run_while_a_device_is_held():
    calls: list[int] = []
    lease = GpuLeaseArbiter(devices=_TWO_DEVICES, empty_cache=lambda: calls.append(1))
    assert lease.try_acquire("lora-train", device=0)
    lease.release("lora-train")
    assert calls == []
    assert lease.try_acquire("lora-train", device=0)
    assert lease.try_acquire("lora-generate", device=1)
    assert calls == []
    lease.release("lora-train")
    lease.release("lora-generate")
    assert calls == []
    assert lease.try_acquire("lora-train")
    assert calls == [1]
    lease.release("lora-train")


def test_overlapping_acquires_take_different_devices():
    import threading

    lease = GpuLeaseArbiter(devices=_TWO_DEVICES)
    barrier = threading.Barrier(2)
    results: dict[str, bool] = {}

    def grab(owner: str) -> None:
        barrier.wait(2)
        results[owner] = lease.try_acquire(owner)

    threads = [threading.Thread(target=grab, args=(name,)) for name in ("a", "b")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(3)
        assert not thread.is_alive()
    assert results == {"a": True, "b": True}
    assert lease.devices_for("a") != lease.devices_for("b")
    assert lease.owner is None


def test_release_calibration_accounts_for_seed_and_live_scales():
    from middleware.src.core.gpu_vram_estimate import estimate_job_gb, formula_job_gb

    formula = formula_job_gb("upscale", tile_size=400)
    lease = GpuLeaseArbiter()
    for multiplier in (2.0, 3.0):
        estimate = estimate_job_gb("upscale", tile_size=400)
        assert lease.try_acquire("upscale", estimated_gb=estimate)
        lease.release("upscale", measured_peak_gb=formula * multiplier)
        assert estimate_job_gb("upscale", tile_size=400) >= round(formula * multiplier, 2)
