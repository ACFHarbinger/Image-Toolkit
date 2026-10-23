"""#756 512px redesign: the probe-scale knob (CPU, no diffusers, no GPU).

`hessian_probe_scale` area-interpolates the frozen probe batch down by
1/scale before freezing — the 12 GB recipe at 512px training is scale 2.
These tests pin the shapes, the exact interpolation, the determinism, and
the threading through run_checkpoint_gauge's stub-tuner contract.
"""
import contextlib
from types import SimpleNamespace

import torch
import torch.nn as nn

from middleware.src.models.hooks.hessian_trace import (
    FrozenEvalBatch,
    freeze_eval_batch,
    hutchinson_trace,
    run_checkpoint_gauge,
)


def _add_noise(latents, noise, timesteps):
    return latents + 0.1 * noise


def _freeze(latents, *, scale=1, seed=42, get_velocity=None):
    return freeze_eval_batch(
        latents=latents,
        encoder_hidden_states=torch.randn(latents.shape[0], 3, 8),
        added_cond_kwargs=None,
        num_train_timesteps=1000,
        seed=seed,
        device="cpu",
        add_noise=_add_noise,
        get_velocity=get_velocity,
        probe_scale=scale,
    )


def test_probe_scale_halves_the_latent_grid():
    latents = torch.randn(2, 4, 64, 64)
    frozen = _freeze(latents, scale=2)
    assert frozen.latents.shape == (2, 4, 32, 32)
    assert frozen.noise.shape == (2, 4, 32, 32)  # noise drawn at the scaled shape
    assert frozen.target.shape == (2, 4, 32, 32)
    assert frozen.probe_scale == 2
    assert frozen.batch_size == 2


def test_probe_interpolation_is_exact_area():
    latents = torch.randn(1, 4, 64, 64)
    frozen = _freeze(latents, scale=2)
    expected = torch.nn.functional.interpolate(latents, scale_factor=0.5, mode="area")
    assert torch.allclose(frozen.latents, expected)


def test_scale_one_is_byte_identical_to_the_old_behavior():
    latents = torch.randn(1, 4, 64, 64)
    scaled_default = _freeze(latents, scale=1)
    legacy = freeze_eval_batch(
        latents=latents,
        encoder_hidden_states=torch.randn(1, 3, 8),
        added_cond_kwargs=None,
        num_train_timesteps=1000,
        seed=42,
        device="cpu",
        add_noise=_add_noise,
    )
    assert torch.equal(scaled_default.latents, legacy.latents)
    assert torch.equal(scaled_default.noise, legacy.noise)
    assert torch.equal(scaled_default.timesteps, legacy.timesteps)
    assert scaled_default.probe_scale == 1


def test_scaled_freeze_is_deterministic_and_independent():
    latents = torch.randn(1, 4, 64, 64)
    first = _freeze(latents, scale=2, seed=9)
    second = _freeze(latents, scale=2, seed=9)
    assert torch.equal(first.noise, second.noise)
    assert torch.equal(first.latents, second.latents)
    # Mutating the source afterwards cannot reach the frozen probe.
    original = latents.clone()
    latents.mul_(50.0)
    assert torch.allclose(first.latents, torch.nn.functional.interpolate(original, scale_factor=0.5, mode="area"))


def test_v_prediction_target_uses_the_scaled_latents():
    latents = torch.randn(1, 4, 64, 64)
    seen = {}

    def get_velocity(lat, noise, timesteps):
        seen["shape"] = tuple(lat.shape)
        return noise * 2.0

    frozen = _freeze(latents, scale=2, get_velocity=get_velocity)
    assert seen["shape"] == (1, 4, 32, 32)
    assert torch.allclose(frozen.target, frozen.noise * 2.0)


def test_hutchinson_report_carries_the_scale():
    model = nn.Linear(4, 3)

    def loss_fn():
        return (model(torch.ones(2, 4)) ** 2).sum()

    report = hutchinson_trace(loss_fn, [model.weight, model.bias], num_vectors=2, seed=1, probe_scale=2)
    assert report.probe_scale == 2
    assert report.finite
    baseline = hutchinson_trace(loss_fn, [model.weight, model.bias], num_vectors=2, seed=1)
    assert baseline.probe_scale == 1
    # The scale is a label on the report; the estimator machinery is identical.
    assert report.per_vector == baseline.per_vector


def test_gauge_threads_cfg_probe_scale_into_the_frozen_batch():
    class _TinyUNet(nn.Module):
        def __init__(self):
            super().__init__()
            self.proj = nn.Linear(4, 4)

        def forward(self, noisy, timesteps, encoder_hidden_states, added_cond_kwargs=None):
            return SimpleNamespace(sample=torch.tanh(self.proj(noisy)))

    class _Diagnostics:
        def __init__(self):
            self.steps = []

        def log_step(self, step, **fields):
            self.steps.append((step, fields))

    tuner = SimpleNamespace(
        cfg=SimpleNamespace(
            hessian_vectors=2, validation_seed=7, prediction_type="epsilon", hessian_probe_scale=2,
        ),
        accelerator=SimpleNamespace(
            device="cpu", is_main_process=True,
            unwrap_model=lambda m: m, autocast=contextlib.nullcontext,
        ),
        noise_scheduler=SimpleNamespace(
            config=SimpleNamespace(num_train_timesteps=1000),
            add_noise=_add_noise,
        ),
        unet=_TinyUNet(),
        compute_loss=lambda pred, target, t: ((pred - target) ** 2).mean(),
        _frozen_eval=None,
    )
    latents = torch.randn(1, 4, 8, 8)
    embeds = torch.randn(1, 3, 4)
    diag = _Diagnostics()
    run_checkpoint_gauge(tuner, diag, 6, 0, latents, embeds, None)
    assert tuner._frozen_eval.probe_scale == 2
    assert tuner._frozen_eval.latents.shape == (1, 4, 4, 4)
    assert len(diag.steps) == 1
    step, fields = diag.steps[0]
    assert step == 6
    assert "hessian/trace" in fields
    assert isinstance(tuner._frozen_eval, FrozenEvalBatch)
