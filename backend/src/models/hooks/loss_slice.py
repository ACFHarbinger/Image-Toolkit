"""Loss-geometry 1-D slice along the leading ΔW direction (#748).

Explicit-action research tooling: never automatic, never wired to a live
trainer. A fresh tuner is constructed for the slice; the chosen module is
perturbed via a *forward hook* — ``output += α·σ1·u1·(v1ᵀx)``, identical
to adding the rank-1 term ``α·σ1·u1·v1ᵀ`` to the module's effective
weight but without mutating any parameter (asserted after every sweep).

The result is a *slice along the leading ΔW direction*, labeled as such.
It is not "the loss landscape" and carries no generalization guarantee.

The diffusers-backed paths (load_tuner_for_slice / build_eval_batches /
run_diffusion_loss_slice) are thin composition over LoRATunerV2's own
loader and loss math, py_compile- and stub-verified only — no live GPU
run has been executed for them (resource rule); that is a known limit.
"""
from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

import torch

from backend.src.core.adapter_reports import DirectionSpec, LossSliceResult

log = logging.getLogger(__name__)

DEFAULT_POINTS = 21


class RankOnePerturbation:
    """Forward hook adding α·σ1·u1·(v1ᵀx) to one module's output.

    (u1 v1ᵀ)x = u1 (v1ᵀ x), so a rank-1 weight perturbation needs one dot
    product and one outer product per forward — no weight is touched.
    The hook's return value replaces the module output (PyTorch contract).
    """

    def __init__(self, sigma: float, u1: torch.Tensor, v1: torch.Tensor, alpha: float = 0.0) -> None:
        self.sigma = float(sigma)
        self.u1 = u1.detach()
        self.v1 = v1.detach()
        self.alpha = float(alpha)

    def __call__(self, module: Any, args, output) -> torch.Tensor | None:
        x = args[0] if args else None
        if x is None or x.dim() != 2 or x.shape[-1] != self.v1.shape[-1]:
            return None
        gain = self.alpha * self.sigma * (x @ self.v1)
        return output + gain.unsqueeze(-1) * self.u1


def compute_loss_slice(
    target_module: torch.nn.Module,
    loss_fn,
    *,
    sigma: float,
    u1: torch.Tensor,
    v1: torch.Tensor,
    num_points: int = DEFAULT_POINTS,
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """Generic α-sweep over [-1, 1].

    *loss_fn()* must be closed over the *same* pre-built batches for
    every α (fixed noise/timesteps — the curve reflects only the
    perturbation). Target-module parameters are snapshotted before and
    equality-checked after: a slice must never leave a residue.
    """
    before = {name: p.detach().clone() for name, p in target_module.named_parameters()}
    alphas = torch.linspace(-1.0, 1.0, num_points).tolist()
    losses: list[float] = []
    hook = RankOnePerturbation(sigma=sigma, u1=u1, v1=v1, alpha=0.0)
    handle = target_module.register_forward_hook(hook)
    try:
        with torch.inference_mode():
            for alpha in alphas:
                hook.alpha = alpha
                losses.append(float(loss_fn()))
    finally:
        handle.remove()
        for name, p in target_module.named_parameters():
            if name in before and not torch.equal(p.detach(), before[name]):
                raise RuntimeError(f"loss slice mutated parameter {name}")
    return tuple(alphas), tuple(losses)


def load_tuner_for_slice(config: dict | Any) -> Any:
    """Build a fresh LoRATunerV2 from a run record's config — never a live
    trainer. The chosen checkpoint's adapter is injected afterwards by
    ``inject_checkpoint``."""
    from backend.src.models.tuning.lo_ra_tuner_config import LoRATunerConfig
    from backend.src.models.tuning.lo_ra_tuner_v2 import LoRATunerV2

    if isinstance(config, dict):
        config = LoRATunerConfig(
            base_model_path=str(config.get("model_id", "")),
            output_dir=str(config.get("output_name", "output_lora")),
            rank=int(config.get("rank", 16)),
        )
    return LoRATunerV2(config)


def inject_checkpoint(tuner: Any, checkpoint_path: str) -> None:
    """Apply a saved adapter (peft safetensors or LyCORIS weights) to the
    freshly built tuner. py_compile-verified only; no live GPU run."""
    from peft import set_peft_model_state_dict
    from safetensors.torch import load_file

    if tuner.lycoris_net is not None:
        tuner.lycoris_net.load_weights(str(checkpoint_path))
        return
    state = load_file(str(checkpoint_path))
    # get_peft_model_state_dict strips the "base_model.model." prefix;
    # set_peft_model_state_dict expects it back.
    if not any(k.startswith("base_model.model.") for k in state):
        state = {f"base_model.model.{k}": v for k, v in state.items()}
    set_peft_model_state_dict(tuner.unet, state)


def build_eval_batches(
    tuner: Any,
    batches: Sequence[tuple[torch.Tensor, Sequence[str]]],
    *,
    seed: int = 42,
) -> list[dict[str, Any]]:
    """Fix the sweep inputs once, per LoRATunerV2's own loss math.

    *batches* is (pixel_values, prompts) pairs — from the run's eval
    images with the record's trigger word. Everything the loss needs is
    frozen here (latents, noise, timesteps, prompt embeds, target), so
    the α-sweep measures only the perturbation.
    """
    prepared: list[dict[str, Any]] = []
    for index, (pixels, prompts) in enumerate(batches):
        generator = torch.Generator().manual_seed(seed + index)
        with torch.no_grad():
            px = pixels.to(dtype=tuner.vae.dtype)
            latents = tuner.vae.encode(px).latent_dist.sample()
            latents = latents * tuner.vae.config.scaling_factor
        noise = torch.randn(latents.shape, generator=generator, device=latents.device)
        bsz = latents.shape[0]
        timesteps = torch.randint(
            0, tuner.noise_scheduler.config.num_train_timesteps,
            (bsz,), generator=generator, device=latents.device,
        ).long()
        noisy_latents = tuner.noise_scheduler.add_noise(latents, noise, timesteps)
        target = (
            tuner.noise_scheduler.get_velocity(latents, noise, timesteps)
            if tuner.cfg.prediction_type == "v_prediction"
            else noise
        )
        added_cond_kwargs = None
        if tuner.is_sdxl:
            prompt_embeds, _pooled = tuner.encode_prompt_sdxl(list(prompts))
        else:
            inputs = tuner.tokenizer_one(
                list(prompts), padding="max_length", max_length=77, truncation=True, return_tensors="pt"
            )
            prompt_embeds = tuner.text_encoder_one(inputs.input_ids.to(tuner.text_encoder_one.device))[0]
        prepared.append(
            {
                "noisy_latents": noisy_latents,
                "timesteps": timesteps,
                "prompt_embeds": prompt_embeds,
                "target": target,
                "added_cond_kwargs": added_cond_kwargs,
            }
        )
    return prepared


def run_diffusion_loss_slice(
    tuner: Any,
    *,
    checkpoint_path: str,
    base_model: str,
    eval_batches: Sequence[dict[str, Any]],
    direction_module: str | None = None,
    num_points: int = DEFAULT_POINTS,
    seed: int = 42,
    direction: tuple[DirectionSpec, torch.Tensor, torch.Tensor] | None = None,
) -> LossSliceResult:
    """Full slice for a loaded, checkpoint-injected tuner + fixed eval
    batches. *direction* may be precomputed (from #743's file-based
    ``principal_direction``); otherwise it is derived from the checkpoint.
    """
    from backend.src.models.hooks.adapter_geometry import principal_direction

    if direction is None:
        direction = principal_direction(checkpoint_path, direction_module)
    spec, u1, v1 = direction
    target = _resolve_module(tuner.unet, spec.module)
    if target is None:
        raise ValueError(f"module {spec.module!r} not found in the loaded model")

    def diffusion_loss() -> float:
        total = 0.0
        for batch in eval_batches:
            model_pred = tuner.unet(
                batch["noisy_latents"],
                batch["timesteps"],
                batch["prompt_embeds"],
                added_cond_kwargs=batch["added_cond_kwargs"],
            ).sample
            total += float(
                torch.nn.functional.mse_loss(model_pred.float(), batch["target"].float(), reduction="mean")
            )
        return total / max(1, len(eval_batches))

    alphas, losses = compute_loss_slice(
        target,
        diffusion_loss,
        sigma=spec.sigma,
        u1=u1,
        v1=v1,
        num_points=num_points,
    )
    return LossSliceResult(
        checkpoint=str(checkpoint_path),
        module=spec.module,
        sigma=spec.sigma,
        energy_fraction=spec.energy_fraction,
        alphas=alphas,
        losses=losses,
        eval_images=len(eval_batches),
        seed=seed,
        base_model=str(base_model),
        num_points=num_points,
    )


def _resolve_module(root: torch.nn.Module, key: str) -> torch.nn.Module | None:
    node: torch.nn.Module = root
    for part in key.split("."):
        if not hasattr(node, part):
            return None
        node = getattr(node, part)
        if not isinstance(node, torch.nn.Module):
            return None
    return node
