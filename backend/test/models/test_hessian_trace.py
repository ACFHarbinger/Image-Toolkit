"""#756: Hutchinson Hessian-trace estimator — exact math on synthetic models.

Diagonal curvature makes Rademacher probes variance-free (z² = 1), so
traces are asserted exactly; the cross-term HVP path is verified by
replaying the same seeded probes by hand. No diffusers, no GPU.
"""
import math

import pytest
import torch
import torch.nn as nn

from backend.src.models.hooks.hessian_trace import (
    FrozenEvalBatch,
    HessianTraceReport,
    freeze_eval_batch,
    hutchinson_trace,
    rademacher_probes,
)


class _DiagonalQuad(nn.Module):
    """loss = ½ Σ a_i θ_i²  →  H = diag(a), trace = Σ a_i (exact for ±1 probes)."""

    def __init__(self, a):
        super().__init__()
        self.register_buffer("a", torch.tensor(a, dtype=torch.float32))
        self.weight = nn.Parameter(torch.zeros(len(a)))

    def loss(self):
        return 0.5 * (self.a * self.weight * self.weight).sum()


class _FullQuad(nn.Module):
    """loss = ½ θᵀAθ → arbitrary curvature for HVP replay."""

    def __init__(self, matrix):
        super().__init__()
        matrix = torch.tensor(matrix, dtype=torch.float32)
        self.register_buffer("A", matrix)
        self.weight = nn.Parameter(torch.zeros(matrix.shape[0]))

    def loss(self):
        return 0.5 * self.weight @ self.A @ self.weight


def test_diagonal_hessian_trace_is_exact_for_rademacher_probes():
    a = [3.0, 1.5, 0.25, 4.0, 0.5]
    model = _DiagonalQuad(a)
    report = hutchinson_trace(model.loss, [model.weight], num_vectors=5, seed=42)
    assert report.trace == pytest.approx(sum(a), rel=1e-5)
    assert report.param_count == len(a)
    assert len(report.per_vector) == 5
    assert report.trace_per_param == pytest.approx(sum(a) / len(a), rel=1e-5)
    assert report.finite


def test_cross_term_hvp_matches_hand_replay():
    matrix = [[2.0, 1.0, 0.0], [1.0, 3.0, 0.5], [0.0, 0.5, 1.0]]
    model = _FullQuad(matrix)
    params = [model.weight]
    report = hutchinson_trace(model.loss, params, num_vectors=4, seed=7)

    probes = rademacher_probes(params, 4, 7)
    for vector_estimate, z in zip(report.per_vector, probes, strict=True):
        expected = float(z[0] @ torch.tensor(matrix) @ z[0])
        assert vector_estimate == pytest.approx(expected, rel=1e-5)


def test_seeded_probes_are_deterministic():
    # Diagonal curvature is probe-invariant; use full curvature so the
    # seed actually changes the estimate.
    matrix = [[2.0, 1.0, 0.0], [1.0, 3.0, 0.5], [0.0, 0.5, 1.0]]
    model = _FullQuad(matrix)
    first = hutchinson_trace(model.loss, [model.weight], num_vectors=3, seed=9)
    second = hutchinson_trace(model.loss, [model.weight], num_vectors=3, seed=9)
    assert first.per_vector == second.per_vector
    other = hutchinson_trace(model.loss, [model.weight], num_vectors=3, seed=10)
    assert other.per_vector != first.per_vector  # new probes, new estimate


def test_hutchinson_never_touches_training_grads():
    model = _DiagonalQuad([1.0, 2.0])
    model.weight.grad = torch.zeros_like(model.weight)
    before = model.weight.detach().clone()
    hutchinson_trace(model.loss, [model.weight], num_vectors=2, seed=1)
    assert torch.equal(model.weight.detach(), before)
    assert torch.equal(model.weight.grad, torch.zeros_like(model.weight))


def test_only_trainable_params_are_measured():
    model = _DiagonalQuad([2.0, 2.0])
    frozen = nn.Parameter(torch.ones(3))
    frozen.requires_grad_(False)
    report = hutchinson_trace(model.loss, [model.weight, frozen], num_vectors=2, seed=3)
    assert report.param_count == 2  # the frozen parameter is excluded


def test_zero_vectors_and_empty_params_degrade():
    model = _DiagonalQuad([1.0])
    empty = hutchinson_trace(model.loss, [], num_vectors=5, seed=1)
    assert empty.num_vectors == 0 and math.isnan(empty.trace)
    off = hutchinson_trace(model.loss, [model.weight], num_vectors=0, seed=1)
    assert off.num_vectors == 0 and math.isnan(off.trace)


def test_freeze_eval_batch_is_independent_and_deterministic():
    latents = torch.randn(2, 4, 8, 8)
    embeds = torch.randn(2, 5, 16)
    state = {"add_noise_calls": 0}

    def add_noise(lat, noise, timesteps):
        state["add_noise_calls"] += 1
        return lat + noise

    frozen = freeze_eval_batch(
        latents=latents, encoder_hidden_states=embeds, added_cond_kwargs=None,
        num_train_timesteps=1000, seed=42, device="cpu",
        add_noise=add_noise,
    )
    # The frozen conditioning is a detached clone — mutating the source
    # afterwards cannot reach it.
    original_latents = latents.clone()
    original_embeds = embeds.clone()
    latents.mul_(100.0)
    embeds.mul_(100.0)
    assert torch.allclose(frozen.latents, original_latents)
    assert torch.allclose(frozen.encoder_hidden_states, original_embeds)
    assert frozen.batch_size == 2
    assert frozen.timesteps.shape == (2,)
    assert torch.allclose(frozen.noise, frozen.target)  # epsilon target

    twin = freeze_eval_batch(
        latents=torch.randn(2, 4, 8, 8), encoder_hidden_states=torch.randn(2, 5, 16),
        added_cond_kwargs=None, num_train_timesteps=1000, seed=42, device="cpu",
        add_noise=add_noise,
    )
    assert torch.equal(frozen.noise, twin.noise)  # same seed → same probes
    assert torch.equal(frozen.timesteps, twin.timesteps)
    assert isinstance(frozen, FrozenEvalBatch)

    # v-prediction routing: get_velocity defines the target.
    frozen_v = freeze_eval_batch(
        latents=torch.randn(1, 4, 8, 8), encoder_hidden_states=torch.randn(1, 5, 16),
        added_cond_kwargs=None, num_train_timesteps=1000, seed=42, device="cpu",
        add_noise=add_noise,
        get_velocity=lambda lat, noise, t: noise * 3.0,
    )
    assert torch.allclose(frozen_v.target, frozen_v.noise * 3.0)


def test_report_dataclass_shape():
    report = HessianTraceReport(
        trace=12.0, per_vector=(12.0, 12.0), num_vectors=2,
        param_count=6, batch_size=2, seed=42,
    )
    assert report.trace_per_param == 2.0
    assert report.finite
    assert not HessianTraceReport(
        trace=float("nan"), per_vector=(), num_vectors=0, param_count=0, batch_size=0, seed=0,
    ).finite
