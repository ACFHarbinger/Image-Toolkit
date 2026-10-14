"""Hutchinson Hessian-trace estimator (#756) — the Generalization Gauge.

Estimates the trace of the loss Hessian on the *adapter* parameters
(``requires_grad`` only) with ``num_vectors`` Rademacher probes:

    trace(H) ≈ (1/m) Σ_i z_iᵀ H z_i,   z_ij ∈ {-1, +1}

each term computed exactly via a Hessian-vector product (double
backward). This estimates curvature on fixed training inputs, not
held-out generalization. It complements #748's
1-D loss slice: the slice shows the shape along one direction, this is
a scalar curvature gauge over the whole adapter space.

Design constraints this module must honor:

- **Deterministic:** the probe vectors come from a seeded generator, so
  the same z's are used at every checkpoint — the trace *series*
  measures the surface evolving under training, not probe noise.
- **Never disturbs training:** ``torch.autograd.grad`` computes fresh
  gradients without touching ``.grad``; parameter state is preserved by
  construction (asserted in tests).
- **Fail-soft:** the caller treats any exception as "no gauge this
  checkpoint"; a non-finite estimate is reported, not raised.

Cost per checkpoint: one forward + one graph-building backward + m
Hessian backwards ≈ (2 + m) backward-equivalents (about four training
steps' worth of work at m=5).
"""
from __future__ import annotations

import logging
import math
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Callable, Sequence

import torch

log = logging.getLogger(__name__)

DEFAULT_VECTORS = 5


@dataclass(frozen=True)
class HessianTraceReport:
    """One checkpoint's trace estimate + its parameterization."""

    trace: float
    per_vector: tuple[float, ...]
    num_vectors: int
    param_count: int
    batch_size: int
    seed: int

    @property
    def trace_per_param(self) -> float:
        return self.trace / self.param_count if self.param_count else float("nan")

    @property
    def finite(self) -> bool:
        return math.isfinite(self.trace) and all(math.isfinite(v) for v in self.per_vector)


def rademacher_probes(params: Sequence[torch.Tensor], num_vectors: int, seed: int) -> list[list[torch.Tensor]]:
    """Deterministic ±1 probe vectors, one list of tensors per probe,
    matching each parameter's shape/dtype/device."""
    return list(_iter_probes(params, num_vectors, seed))


def _iter_probes(params, num_vectors, seed):
    generators = {}
    for p in params:
        if p.device not in generators:
            generators[p.device] = torch.Generator(device=p.device).manual_seed(seed)
    for _ in range(num_vectors):
        yield [torch.randint(0, 2, p.shape, generator=generators[p.device], device=p.device,
                             dtype=torch.int8).to(p.dtype).mul_(2).sub_(1) for p in params]


@contextmanager
def diagnostic_eval(model, seed):
    """Preserve RNG and mixed module modes even when the diagnostic fails."""
    modes = [(module, module.training) for module in model.modules()]
    devices = sorted({p.device.index for p in model.parameters() if p.device.type == "cuda"})
    with torch.random.fork_rng(devices=devices):
        torch.random.default_generator.manual_seed(seed)
        for device in devices:
            with torch.cuda.device(device):
                torch.cuda.manual_seed(seed)
        try:
            model.eval()
            yield
        finally:
            for module, training in modes:
                module.training = training


def _freeze_tree(value):
    if isinstance(value, torch.Tensor):
        return value.detach().clone()
    if isinstance(value, dict):
        return {key: _freeze_tree(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return type(value)(_freeze_tree(item) for item in value)
    return value


def hutchinson_trace(
    loss_fn: Callable[[], torch.Tensor],
    params: Sequence[torch.Tensor],
    *,
    num_vectors: int = DEFAULT_VECTORS,
    seed: int = 0,
    batch_size: int = 0,
) -> HessianTraceReport:
    """Estimate tr(H) of ``loss_fn`` w.r.t. ``params`` (adapter params).

    *loss_fn* must return a scalar tensor with no graph retained from
    elsewhere; it is re-differentiated here from scratch.
    """
    live = [p for p in params if p.requires_grad]
    param_count = sum(p.numel() for p in live)
    if not live or num_vectors <= 0:
        return HessianTraceReport(
            trace=float("nan"), per_vector=(), num_vectors=0,
            param_count=param_count, batch_size=batch_size, seed=seed,
        )

    loss = loss_fn()
    grads = (torch.autograd.grad(loss, live, create_graph=True, allow_unused=True)
             if loss.requires_grad else (None,) * len(live))

    per_vector: list[float] = []
    for probes in _iter_probes(live, num_vectors, seed):
        weighted = [
            (z * g).sum() for z, g in zip(probes, grads, strict=True) if g is not None and g.requires_grad
        ]
        gz = sum(weighted) if weighted else None
        if gz is None:
            per_vector.append(0.0)
            continue
        hvp = torch.autograd.grad(gz, live, allow_unused=True, retain_graph=True)
        terms = [
            (z * h).sum().item() for z, h in zip(probes, hvp, strict=True) if h is not None
        ]
        per_vector.append(sum(terms) if terms else 0.0)

    trace = sum(per_vector) / len(per_vector)
    report = HessianTraceReport(
        trace=trace,
        per_vector=tuple(per_vector),
        num_vectors=num_vectors,
        param_count=param_count,
        batch_size=batch_size,
        seed=seed,
    )
    # Free the double-backward graph before returning.
    loss = None
    grads = None
    return report


@dataclass(frozen=True)
class FrozenEvalBatch:
    """A training batch frozen for the whole run: the same latents,
    conditioning, noise, and timesteps at every checkpoint, so the trace
    series is comparable across checkpoints by construction."""

    latents: torch.Tensor
    noise: torch.Tensor
    timesteps: torch.Tensor
    target: torch.Tensor
    encoder_hidden_states: torch.Tensor
    added_cond_kwargs: Any = None
    batch_size: int = 0


def freeze_eval_batch(
    *,
    latents: torch.Tensor,
    encoder_hidden_states: torch.Tensor,
    added_cond_kwargs: Any,
    num_train_timesteps: int,
    seed: int,
    device: str | torch.device,
    add_noise: Callable,
    get_velocity: Callable | None = None,
) -> FrozenEvalBatch:
    """Detach + clone the current batch's conditioning and draw its
    noise/timesteps once from ``seed`` (independent of the training
    loop's RNG, so freezing at any step is reproducible)."""
    generator = torch.Generator(device=device)
    generator.manual_seed(seed)
    latents = latents.detach().clone()
    noise = torch.randn(latents.shape, generator=generator, device=latents.device, dtype=latents.dtype)
    timesteps = torch.randint(
        0, num_train_timesteps, (latents.shape[0],), generator=generator, device=latents.device
    ).long()
    # Epsilon prediction targets the noise itself; v-prediction targets
    # the scheduler velocity.
    target = get_velocity(latents, noise, timesteps) if get_velocity is not None else noise
    return FrozenEvalBatch(
        latents=latents,
        noise=noise,
        timesteps=timesteps,
        target=target.detach().clone(),
        encoder_hidden_states=encoder_hidden_states.detach().clone(),
        added_cond_kwargs=_freeze_tree(added_cond_kwargs),
        batch_size=int(latents.shape[0]),
    )


__all__ = [
    "DEFAULT_VECTORS",
    "FrozenEvalBatch",
    "HessianTraceReport",
    "freeze_eval_batch",
    "hutchinson_trace",
    "rademacher_probes",
]


def run_checkpoint_gauge(
    tuner, diagnostics, step: int, epoch: int, latents,
    encoder_hidden_states, added_cond_kwargs,
) -> None:
    """#756: Generalization Gauge at a checkpoint point.

    Hutchinson trace of the loss Hessian on the adapter parameters,
    Opt-in Rademacher probes against a training batch frozen at the
    first checkpoint (same latents/noise/timesteps afterwards, so
    the trace series is comparable). Fail-soft by contract: no
    diagnostics, the ``hessian_vectors=0`` off-switch, or any
    failure degrades to no gauge — training never dies for a
    diagnostic. ``autograd.grad`` never writes ``.grad``, so the
    training state is preserved by construction.
    """
    cfg = tuner.cfg
    if diagnostics is None or cfg.hessian_vectors <= 0 or latents is None:
        return
    if not getattr(tuner.accelerator, "is_main_process", True):
        return
    try:
        if tuner._frozen_eval is None:
            tuner._frozen_eval = freeze_eval_batch(
                latents=latents,
                encoder_hidden_states=encoder_hidden_states,
                added_cond_kwargs=added_cond_kwargs,
                num_train_timesteps=tuner.noise_scheduler.config.num_train_timesteps,
                seed=cfg.validation_seed,
                device=tuner.accelerator.device,
                add_noise=tuner.noise_scheduler.add_noise,
                get_velocity=(
                    tuner.noise_scheduler.get_velocity
                    if cfg.prediction_type == "v_prediction" else None
                ),
            )
        frozen = tuner._frozen_eval

        def frozen_loss() -> torch.Tensor:
            noisy = tuner.noise_scheduler.add_noise(frozen.latents, frozen.noise, frozen.timesteps)
            model_pred = model(
                noisy, frozen.timesteps, frozen.encoder_hidden_states,
                added_cond_kwargs=frozen.added_cond_kwargs,
            ).sample
            return tuner.compute_loss(model_pred, frozen.target, frozen.timesteps)

        from torch.nn.attention import SDPBackend, sdpa_kernel

        model = tuner.accelerator.unwrap_model(tuner.unet)
        params = [p for p in model.parameters() if p.requires_grad]
        # Unwrapped eval avoids DDP collectives and reentrant checkpointing.
        with diagnostic_eval(model, cfg.validation_seed), sdpa_kernel(SDPBackend.MATH), tuner.accelerator.autocast():
            report = hutchinson_trace(
                frozen_loss, params,
                num_vectors=cfg.hessian_vectors, seed=cfg.validation_seed,
                batch_size=frozen.batch_size,
            )
        if not report.finite:
            log.warning("Hessian trace non-finite at step %s — skipped", step)
            return
        diagnostics.log_step(
            step,
            epoch=epoch,
            **{"hessian/trace": report.trace, "hessian/param": report.trace_per_param},
        )
    except Exception as exc:  # fail-soft: a diagnostic must never kill training
        log.warning("Hessian trace failed at step %s: %s", step, exc)
