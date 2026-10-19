"""#748: the ΔW-principal loss slice — perturbation math, sweep, immutability.

No diffusers, no GPU: a tiny nn.Linear stands in for the model. The
diffusers-backed composition (load_tuner_for_slice / build_eval_batches /
run_diffusion_loss_slice) is py_compile-verified only — no live GPU run,
per the resource rule.
"""
import pytest
import torch
import torch.nn as nn

from middleware.src.core.adapter_reports import LossSliceResult
from middleware.src.models.hooks.loss_slice import (
    DEFAULT_POINTS,
    RankOnePerturbation,
    compute_loss_slice,
)


def test_perturbation_hook_is_rank_one_weight_addition():
    """hook(x) must equal x @ (W + α·σ·u1·v1ᵀ).T + b for a Linear."""
    torch.manual_seed(7)
    module = nn.Linear(4, 3)
    u1 = torch.randn(3)
    u1 = u1 / u1.norm()
    v1 = torch.randn(4)
    v1 = v1 / v1.norm()
    sigma, alpha = 2.5, 0.4

    x = torch.randn(5, 4)
    expected = module(x) + alpha * sigma * (x @ v1).unsqueeze(-1) * u1
    expected_perturbed_weight = x @ (module.weight + alpha * sigma * u1.outer(v1)).T + module.bias

    hook = RankOnePerturbation(sigma=sigma, u1=u1, v1=v1, alpha=alpha)
    result = hook(module, (x,), module(x))
    assert torch.allclose(result, expected, atol=1e-6)
    # Equivalent to the rank-1 weight addition, to hook tolerance.
    assert torch.allclose(result, expected_perturbed_weight, atol=1e-6)


def test_compute_loss_slice_sweeps_alpha_deterministically():
    torch.manual_seed(3)
    module = nn.Linear(4, 3)
    u1 = torch.tensor([1.0, 0.0, 0.0])
    v1 = torch.tensor([1.0, 0.0, 0.0, 0.0])
    sigma = 1.0
    x = torch.ones(1, 4)  # v1ᵀx = 1 for every row
    batch = x

    def loss_fn() -> float:
        # Linear in the perturbation → losses must trace a straight line
        # in α whose slope is σ·(v1ᵀx)·sum(u1).
        return float(module(batch).sum())

    alphas, losses = compute_loss_slice(
        module, loss_fn, sigma=sigma, u1=u1, v1=v1, num_points=5,
    )
    assert alphas == (-1.0, -0.5, 0.0, 0.5, 1.0)
    base = losses[2]
    step = sigma * float(batch[0] @ v1) * float(u1.sum())
    assert losses[0] == pytest.approx(base - step, rel=1e-5)
    assert losses[4] == pytest.approx(base + step, rel=1e-5)

    # Same inputs → identical slice (fixed-batch determinism).
    alphas2, losses2 = compute_loss_slice(
        module, loss_fn, sigma=sigma, u1=u1, v1=v1, num_points=5,
    )
    assert losses2 == losses and alphas2 == alphas


def test_compute_loss_slice_never_mutates_parameters():
    torch.manual_seed(11)
    module = nn.Linear(4, 3)
    before = {name: p.detach().clone() for name, p in module.named_parameters()}
    u1 = torch.ones(3) / 3 ** 0.5
    v1 = torch.ones(4) / 2.0
    compute_loss_slice(module, lambda: float(module(torch.ones(2, 4)).sum()),
                       sigma=3.0, u1=u1, v1=v1, num_points=DEFAULT_POINTS)
    for name, p in module.named_parameters():
        assert torch.equal(p.detach(), before[name])


def test_slice_result_round_trips(tmp_path):
    result = LossSliceResult(
        checkpoint="/out/checkpoint-epoch0002",
        module="unet.big",
        sigma=2.5,
        energy_fraction=0.9,
        alphas=(-1.0, 0.0, 1.0),
        losses=(1.5, 1.0, 1.25),
        eval_images=4,
        seed=42,
        base_model="some/model",
        num_points=3,
    )
    path = tmp_path / "loss_slice.json"
    result.to_json_file(path)
    loaded = LossSliceResult.from_json_file(path)
    assert loaded == result
    assert loaded.label.startswith("1-D slice")
    assert LossSliceResult.from_json_file(tmp_path / "missing.json") is None


def test_attention_sequence_is_perturbed_with_matching_dtype():
    module = nn.Linear(4, 3).double()
    x = torch.ones(2, 5, 4, dtype=torch.float64)
    hook = RankOnePerturbation(2, torch.ones(3), torch.ones(4), .5)
    result = hook(module, (x,), module(x))
    assert torch.allclose(result, module(x) + 4)
    assert result.dtype == x.dtype


def test_eval_batch_freezes_sdxl_conditioning_and_noise():
    from types import SimpleNamespace as NS

    from middleware.src.models.hooks.loss_slice import build_eval_batches
    class Distribution:
        def sample(self, generator):
            return torch.randn((1, 4, 2, 2), generator=generator)
    tuner = NS(
        accelerator=NS(device=torch.device("cpu")),
        vae=NS(dtype=torch.float32, config=NS(scaling_factor=1),
               encode=lambda px: NS(latent_dist=Distribution())),
        cfg=NS(prediction_type="epsilon"), is_sdxl=True,
        noise_scheduler=NS(config=NS(num_train_timesteps=100), add_noise=lambda x, n, t: x + n),
        encode_prompt_sdxl=lambda prompts: (torch.ones(1, 77, 8), torch.ones(1, 8)),
    )
    inputs = [(torch.ones(1, 3, 16, 32), ["fixed"])]
    first = build_eval_batches(tuner, inputs)[0]
    second = build_eval_batches(tuner, inputs)[0]
    assert torch.equal(first["noisy_latents"], second["noisy_latents"])
    assert first["added_cond_kwargs"]["time_ids"].tolist() == [[16, 32, 0, 0, 16, 32]]
    assert first["added_cond_kwargs"]["text_embeds"].shape == (1, 8)
