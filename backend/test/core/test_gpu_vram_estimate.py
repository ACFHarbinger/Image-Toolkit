"""Job-parameter VRAM estimates used at production admit sites (#758)."""
from __future__ import annotations

import pytest

from backend.src.core.gpu_lease_arbiter import PROFILE_CONSERVATIVE, GpuLeaseArbiter
from backend.src.core.gpu_vram_calibration import clear, record_peak
from backend.src.core.gpu_vram_estimate import (
    diffusion_gb,
    estimate_job_gb,
    formula_job_gb,
    model_family,
    workflow_family,
    workflow_latent_size,
)


@pytest.fixture(autouse=True)
def _reset_calibration():
    clear()
    yield
    clear()


def test_family_from_model_id():
    assert model_family("stabilityai/stable-diffusion-xl-base-1.0") == "sdxl"
    assert model_family("OnomaAIResearch/Illustrious-XL-v2.0") == "sdxl"
    assert model_family("animegan_v2") == "animegan"
    assert model_family("runwayml/stable-diffusion-v1-5") == "sd15"


def test_estimates_scale_with_resolution_batch_and_rank():
    small = estimate_job_gb("lora-generate", model_id="runwayml/stable-diffusion-v1-5", batch_size=1)
    large = estimate_job_gb(
        "lora-generate",
        model_id="stabilityai/stable-diffusion-xl-base-1.0",
        width=1024,
        height=1024,
        batch_size=2,
    )
    train = estimate_job_gb(
        "lora-train",
        model_id="stabilityai/stable-diffusion-xl-base-1.0",
        rank=16,
        batch_size=2,
    )
    assert 3.5 <= small <= 6.0
    assert large > small
    assert train > estimate_job_gb(
        "lora-train",
        model_id="runwayml/stable-diffusion-v1-5",
        rank=4,
        batch_size=1,
    )


def test_comfy_estimate_reads_latent_and_checkpoint():
    workflow = {
        "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "sd_xl_base_1.0.safetensors"}},
        "5": {"class_type": "EmptyLatentImage", "inputs": {"width": 1024, "height": 1280, "batch_size": 1}},
    }
    assert workflow_latent_size(workflow) == (1024, 1280)
    assert workflow_family(workflow) == "sdxl"
    guided = estimate_job_gb("guided", workflow=workflow)
    preview = estimate_job_gb("matrix", workflow=workflow, width=512, height=512)
    assert guided > preview


def test_upscale_estimate_accounts_for_resident_full_image():
    tile = estimate_job_gb("upscale", tile_size=400)
    huge = estimate_job_gb("upscale", width=8000, height=4000, tile_size=400)
    assert 0.8 <= tile <= 2.5
    assert huge > tile
    assert tile == round(formula_job_gb("upscale", tile_size=400) * 1.43, 2)


def test_gan_train_seed_matches_measured_peak():
    assert estimate_job_gb("gan-train", batch_size=1) == round(
        formula_job_gb("gan-train", batch_size=1) * 2.24, 2
    )


def test_every_production_owner_returns_a_positive_estimate():
    owners = (
        "lora-train",
        "lora-generate",
        "guided",
        "graph",
        "promoted",
        "matrix",
        "guidance",
        "upscale",
        "gan-train",
        "cbir-train",
        "dataset-advisor",
        "vlm-advise",
        "loss-slice",
        "training-experiment",
    )
    for owner in owners:
        assert estimate_job_gb(owner) > 0


def test_conservative_admission_uses_the_job_estimate():
    estimate = estimate_job_gb(
        "lora-train",
        model_id="stabilityai/stable-diffusion-xl-base-1.0",
        rank=16,
        batch_size=2,
    )
    lease = GpuLeaseArbiter(profile=PROFILE_CONSERVATIVE, device_total_gb=8.0)
    assert lease.try_acquire("lora-train", estimated_gb=estimate) is False
    assert "estimated" in lease.refusal_text().lower()
    roomy = GpuLeaseArbiter(profile=PROFILE_CONSERVATIVE, device_total_gb=24.0)
    assert roomy.try_acquire("lora-train", estimated_gb=estimate)
    roomy.release("lora-train")


def test_diffusion_gb_is_deterministic():
    assert diffusion_gb(family="sd15", width=512, height=512) == diffusion_gb(
        family="sd15", width=512, height=512
    )


def test_measured_peak_raises_future_estimates():
    formula = formula_job_gb("upscale", tile_size=400)
    record_peak("upscale", formula * 2, formula)
    assert estimate_job_gb("upscale", tile_size=400) == pytest.approx(round(formula * 2, 2))


def test_smaller_peak_does_not_lower_estimate():
    before = estimate_job_gb("gan-train", batch_size=1)
    formula = formula_job_gb("gan-train", batch_size=1)
    record_peak("gan-train", formula * 0.25, formula)
    assert estimate_job_gb("gan-train", batch_size=1) == before


def test_comfy_formula_is_unchanged_without_a_seed():
    workflow = {
        "5": {"class_type": "EmptyLatentImage", "inputs": {"width": 512, "height": 512, "batch_size": 1}},
    }
    assert estimate_job_gb("guided", workflow=workflow) == estimate_job_gb(
        "guided", workflow=workflow
    )


def test_workflow_batch_size_affects_admission_estimate():
    workflow = {"1": {"class_type": "EmptyLatentImage", "inputs": {"width": 512, "height": 512, "batch_size": 1}}}
    single = estimate_job_gb("graph", workflow=workflow)
    workflow["1"]["inputs"]["batch_size"] = 8
    assert estimate_job_gb("graph", workflow=workflow) > single
