"""GpuLeaseArbiter occupancy rules beyond one exclusive job (#758)."""
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


@pytest.fixture(autouse=True)
def _reset_calibration():
    clear()
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


def test_release_calibration_accounts_for_seed_and_live_scales():
    from middleware.src.core.gpu_vram_estimate import estimate_job_gb, formula_job_gb

    formula = formula_job_gb("upscale", tile_size=400)
    lease = GpuLeaseArbiter()
    for multiplier in (2.0, 3.0):
        estimate = estimate_job_gb("upscale", tile_size=400)
        assert lease.try_acquire("upscale", estimated_gb=estimate)
        lease.release("upscale", measured_peak_gb=formula * multiplier)
        assert estimate_job_gb("upscale", tile_size=400) >= round(formula * multiplier, 2)
