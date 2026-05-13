"""
backend/src/models/diagnostics/training_hooks.py
=================================================
Training diagnostics for anime diffusion fine-tuning.

Components
----------
DiagnosticsLogger     — TensorBoard + W&B dual logging, gradient norms,
                        LoRA weight norms, sample grids
CrossAttnRecorder     — hooks into UNet cross-attention layers to record
                        attention probability maps per token
lora_effective_rank   — SVD analysis of LoRA adapter weights
lora_delta_heatmap    — bar chart of per-layer ‖ΔW‖_F
grid_to_pil           — compose a list of PIL images into a contact sheet
"""

from __future__ import annotations

import logging
from typing import Callable, Optional

import numpy as np
import torch
import torch.nn as nn
from PIL import Image

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional dependencies
# ---------------------------------------------------------------------------
try:
    from torch.utils.tensorboard import SummaryWriter
    _TB_OK = True
except ImportError:
    _TB_OK = False
    log.warning("tensorboard not installed — TensorBoard logging disabled")

try:
    import wandb
    _WANDB_OK = True
except ImportError:
    _WANDB_OK = False
    log.warning("wandb not installed — W&B logging disabled")


# ---------------------------------------------------------------------------
# DiagnosticsLogger
# ---------------------------------------------------------------------------
class DiagnosticsLogger:
    """
    Unified TensorBoard + W&B logger for diffusion training loops.

    Parameters
    ----------
    run_name        : experiment name (used for both TB dir and W&B run name)
    project         : W&B project name
    use_wandb       : whether to initialise a W&B run
    use_tensorboard : whether to create a SummaryWriter
    tb_dir          : root directory for TensorBoard event files
    log_grad_every  : log gradient norms every N steps (0 = disabled)
    """

    def __init__(
        self,
        run_name: str,
        project: str = "anime-diffusion",
        use_wandb: bool = False,
        use_tensorboard: bool = True,
        tb_dir: str = "runs",
        log_grad_every: int = 25,
    ):
        self.run_name = run_name
        self.log_grad_every = log_grad_every
        self._step = 0

        self.tb: Optional[SummaryWriter] = None
        if use_tensorboard and _TB_OK:
            self.tb = SummaryWriter(f"{tb_dir}/{run_name}")

        self.wb = None
        if use_wandb and _WANDB_OK:
            self.wb = wandb.init(project=project, name=run_name)

    # ------------------------------------------------------------------
    def log_step(self, step: int, **metrics):
        self._step = step
        if self.tb:
            for k, v in metrics.items():
                self.tb.add_scalar(k, float(v), step)
        if self.wb:
            self.wb.log({k: float(v) for k, v in metrics.items()}, step=step)

    def log_grad_norm(self, model: nn.Module, step: int, prefix: str = "grad") -> float:
        if self.log_grad_every <= 0 or step % self.log_grad_every != 0:
            return 0.0
        total_sq = 0.0
        per_layer: dict[str, float] = {}
        for n, p in model.named_parameters():
            if p.grad is None:
                continue
            gn = p.grad.detach().data.norm(2).item()
            per_layer[f"{prefix}/norm/{n}"] = gn
            total_sq += gn ** 2
        total = total_sq ** 0.5
        self.log_step(step, **{f"{prefix}/total": total})
        # Only log top-32 layers to keep TB UI usable
        top = sorted(per_layer.items(), key=lambda kv: -kv[1])[:32]
        if self.tb:
            for k, v in top:
                self.tb.add_scalar(k, v, step)
        return total

    def log_lora_weight_norms(self, peft_model: nn.Module, step: int):
        for n, p in peft_model.named_parameters():
            if "lora_A" in n or "lora_B" in n:
                norm = p.detach().norm(2).item()
                if self.tb:
                    self.tb.add_scalar(f"lora/wnorm/{n}", norm, step)

    def log_vae_roundtrip(self, vae, x: torch.Tensor, step: int):
        """Log VAE encode→decode L1 to detect VAE drift (a silent failure mode)."""
        with torch.no_grad():
            lat = vae.encode(x).latent_dist.sample() * vae.config.scaling_factor
            rec = vae.decode(lat / vae.config.scaling_factor).sample
        l1 = (x - rec).abs().mean().item()
        self.log_step(step, vae_l1=l1)

    def log_sample_grid(
        self,
        pipe,
        prompts: list[str],
        step: int,
        seed: int = 42,
        tag: str = "sample",
    ):
        gen = torch.Generator("cuda").manual_seed(seed)
        with torch.inference_mode():
            imgs = pipe(
                prompt=prompts,
                num_inference_steps=30,
                guidance_scale=6.0,
                generator=gen,
            ).images
        grid = grid_to_pil(imgs)
        if self.tb:
            t = torch.tensor(np.asarray(grid)).permute(2, 0, 1)
            self.tb.add_image(tag, t, step)
        if self.wb:
            wandb.log({tag: wandb.Image(grid)}, step=step)

    def close(self):
        if self.tb:
            self.tb.close()
        if self.wb:
            self.wb.finish()


# ---------------------------------------------------------------------------
# CrossAttnRecorder
# ---------------------------------------------------------------------------
class CrossAttnRecorder:
    """
    Hooks into UNet cross-attention layers to record attention probability
    maps during a forward pass.

    Usage
    -----
        recorder = CrossAttnRecorder(unet)
        with torch.inference_mode():
            _ = unet(noisy, t, embeds)
        maps = recorder.maps      # {layer_name: Tensor(heads, hw, tokens)}
        heatmaps = recorder.trigger_heatmap(token_idx=1, h=64, w=64)
        recorder.remove()
    """

    def __init__(self, unet: nn.Module, layer_filter: Callable = lambda n: "attn2" in n):
        self.maps: dict[str, torch.Tensor] = {}
        self._handles: list = []
        for n, m in unet.named_modules():
            if layer_filter(n) and hasattr(m, "processor"):
                handle = m.register_forward_hook(self._make_hook(n))
                self._handles.append(handle)

    def _make_hook(self, name: str):
        def hook(module, args, output):
            # Try to extract attention weights from the output if available
            if isinstance(output, tuple) and len(output) > 1 and isinstance(output[1], torch.Tensor):
                self.maps[name] = output[1].detach().cpu().half()
        return hook

    def trigger_heatmap(
        self, token_idx: int, h: int, w: int
    ) -> list[tuple[str, np.ndarray]]:
        out = []
        for name, m in self.maps.items():
            if m.dim() < 3:
                continue
            # m shape: (batch*heads, hw, tokens) or (heads, hw, tokens)
            if m.dim() == 3:
                probs = m.mean(0)          # (hw, tokens)
            else:
                probs = m.mean(dim=(0, 1)) # fallback
            if token_idx >= probs.shape[-1]:
                continue
            weights = probs[:, token_idx]
            side = int(weights.shape[0] ** 0.5)
            if side * side != weights.shape[0]:
                continue
            grid = weights.reshape(side, side).float().numpy()
            out.append((name, grid))
        return out

    def remove(self):
        for h in self._handles:
            h.remove()
        self._handles.clear()


# ---------------------------------------------------------------------------
# LoRA SVD effective-rank analysis
# ---------------------------------------------------------------------------
def lora_effective_rank(
    peft_model: nn.Module,
    threshold: float = 0.99,
) -> dict[str, dict]:
    """
    For each LoRA layer, compute:
      eff_rank  — number of singular values accounting for `threshold` of variance
      max_sv    — largest singular value
      fro       — Frobenius norm of ΔW

    If eff_rank ≤ rank/4 across all layers → under-parameterised, reduce rank.
    If eff_rank == rank for many layers → over-parameterised, raise rank (or use rsLoRA).
    """
    out = {}
    for n, m in peft_model.named_modules():
        A = getattr(m, "lora_A", None)
        B = getattr(m, "lora_B", None)
        if A is None or B is None:
            continue
        adapters = A if isinstance(A, dict) else {"default": A}
        for adapter_name in adapters:
            try:
                a_w = (A[adapter_name].weight if isinstance(A, dict) else A.weight)
                b_w = (B[adapter_name].weight if isinstance(B, dict) else B.weight)
                W = (b_w @ a_w).detach().float()
                s = torch.linalg.svdvals(W)
                cumvar = (s ** 2).cumsum(0) / (s ** 2).sum().clamp(min=1e-12)
                eff = int((cumvar < threshold).sum().item()) + 1
                out[f"{n}.{adapter_name}"] = {
                    "eff_rank": eff,
                    "rank": a_w.shape[0],
                    "max_sv": float(s.max()),
                    "fro": float(s.norm()),
                }
            except Exception as exc:
                log.debug("SVD failed for %s.%s: %s", n, adapter_name, exc)
    return out


# ---------------------------------------------------------------------------
# LoRA ΔW Frobenius-norm heatmap
# ---------------------------------------------------------------------------
def lora_delta_heatmap(peft_model: nn.Module, out_path: str):
    """
    Bar chart of ‖B·A‖_F per LoRA layer, saved to out_path as PNG.
    Lights up layers that moved the most — useful for rank-utilisation audits.
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        log.warning("matplotlib required for lora_delta_heatmap")
        return

    rows = []
    for n, m in peft_model.named_modules():
        A = getattr(m, "lora_A", None)
        B = getattr(m, "lora_B", None)
        if A is None or B is None:
            continue
        try:
            a_w = A.weight if not isinstance(A, dict) else A["default"].weight
            b_w = B.weight if not isinstance(B, dict) else B["default"].weight
            W = (b_w @ a_w).detach().float()
            rows.append((n, float(W.norm()), float(W.abs().mean())))
        except Exception:
            pass

    if not rows:
        return

    rows.sort(key=lambda r: -r[1])
    names = [r[0] for r in rows]
    norms = [r[1] for r in rows]

    fig, ax = plt.subplots(figsize=(8, max(4, len(rows) * 0.18)))
    ax.barh(names, norms)
    ax.set_xlabel("‖ΔW‖_F (Frobenius norm)")
    ax.set_title("LoRA layer weight delta magnitudes")
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Utility: image grid
# ---------------------------------------------------------------------------
def grid_to_pil(images: list[Image.Image], cols: int = 4) -> Image.Image:
    if not images:
        return Image.new("RGB", (512, 512), "black")
    rows = (len(images) + cols - 1) // cols
    w, h = images[0].size
    out = Image.new("RGB", (cols * w, rows * h), "white")
    for i, im in enumerate(images):
        out.paste(im, ((i % cols) * w, (i // cols) * h))
    return out
