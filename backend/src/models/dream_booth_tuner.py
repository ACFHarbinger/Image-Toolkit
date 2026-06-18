"""
backend/src/models/lora_diffusion.py
======================================
Anime diffusion fine-tuning: LoRATuner (legacy), LoRATunerV2, and
DreamBoothTuner.

LoRATunerV2 adds over the original:
  - LyCORIS support (LoCon / LoHa / LoKr via lycoris-lora package)
  - DoRA / rsLoRA via PEFT
  - Dual text-encoder training with separate LR multipliers
  - Min-SNR-γ loss (ε-prediction and v-prediction)
  - Prodigy / Adafactor / AdamW8bit / Lion optimizers
  - EMA wrapper compatible with PEFT adapters
  - SDXL micro-conditioning (original_size / crop_top_left / target_size)
  - Hydra-compatible config dataclass

DreamBoothTuner extends LoRATunerV2 with prior-preservation loss and
class-image generation.

FullFineTuner lives in backend/src/models/full_finetune.py.
"""

from __future__ import annotations
from .lo_ra_tuner_config import LoRATunerConfig
from .lo_ra_tuner_v2 import LoRATunerV2

import os
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import torch
import torch.nn.functional as F
from PIL import Image
from accelerate import Accelerator
from diffusers import (
    DDPMScheduler,
    AutoencoderKL,
    UNet2DConditionModel,
    StableDiffusionPipeline,
    StableDiffusionXLPipeline,
    DPMSolverMultistepScheduler,
)
from diffusers.optimization import get_scheduler
from diffusers.training_utils import EMAModel, compute_snr
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms
from transformers import CLIPTextModel, CLIPTokenizer, CLIPTextModelWithProjection
from huggingface_hub import hf_hub_download
from peft import LoraConfig, get_peft_model
from tqdm.auto import tqdm

# ---------------------------------------------------------------------------
# Optional dependencies
# ---------------------------------------------------------------------------
try:
    import bitsandbytes as bnb
    _BNB_OK = True
except ImportError:
    _BNB_OK = False

try:
    from prodigyopt import Prodigy
    _PRODIGY_OK = True
except ImportError:
    _PRODIGY_OK = False

try:
    from transformers.optimization import Adafactor
    _ADAFACTOR_OK = True
except ImportError:
    _ADAFACTOR_OK = False

try:
    import lycoris.kohya as lycoris_kohya
    _LYCORIS_OK = True
except ImportError:
    _LYCORIS_OK = False

# ---------------------------------------------------------------------------
# SDXL LoRA target modules
# ---------------------------------------------------------------------------
SDXL_ATTN_TARGETS = (
    "to_q", "to_k", "to_v", "to_out.0",
    "proj_in", "proj_out",
    "ff.net.0.proj", "ff.net.2",
)
SDXL_CONV_TARGETS = (
    "conv1", "conv2", "conv_shortcut", "conv", "time_emb_proj",
)
TE_ATTN_TARGETS = ("q_proj", "k_proj", "v_proj", "out_proj")

# ===========================================================================
# LoRA Tuner Config
# ===========================================================================
@dataclass

# ===========================================================================
# LoRATunerV2
# ===========================================================================

# ===========================================================================
# DreamBoothTuner
# ===========================================================================
class DreamBoothTuner(LoRATunerV2):
    """
    Extends LoRATunerV2 with prior-preservation loss and class-image generation.

    Set cfg.method = 'peft' or 'lycoris' for LoRA-based DreamBooth, or
    override build_adapters() to skip adapters entirely for full-UNet DreamBooth.
    """

    def __init__(
        self,
        cfg: LoRATunerConfig,
        use_prior_preservation: bool = True,
        prior_loss_weight: float = 1.0,
        num_class_images: int = 200,
        class_prompt: str = "1girl",
        class_dir: Optional[str] = None,
        sample_batch_size: int = 4,
    ):
        super().__init__(cfg)
        self.use_prior_preservation = use_prior_preservation
        self.prior_loss_weight = prior_loss_weight
        self.num_class_images = num_class_images
        self.class_prompt = class_prompt
        self.class_dir = Path(class_dir) if class_dir else Path(cfg.output_dir) / "class_images"
        self.sample_batch_size = sample_batch_size

    def maybe_generate_class_images(self) -> list[Path]:
        self.class_dir.mkdir(parents=True, exist_ok=True)
        existing = sorted(self.class_dir.glob("*.png"))
        if len(existing) >= self.num_class_images:
            return existing

        print(f"[DreamBoothTuner] Generating {self.num_class_images - len(existing)} class images…")
        PipeClass = StableDiffusionXLPipeline if self.is_sdxl else StableDiffusionPipeline
        pipe = PipeClass.from_pretrained(
            self.cfg.base_model_path,
            unet=self.unet if not hasattr(self.unet, "peft_config") else None,
            torch_dtype=torch.float16,
            safety_checker=None,
            requires_safety_checker=False,
        ).to("cuda")
        pipe.set_progress_bar_config(disable=True)

        n_to_make = self.num_class_images - len(existing)
        for i in range(0, n_to_make, self.sample_batch_size):
            batch = min(self.sample_batch_size, n_to_make - i)
            imgs = pipe(
                prompt=[self.class_prompt] * batch,
                num_inference_steps=30,
                guidance_scale=5.0,
            ).images
            for j, im in enumerate(imgs):
                im.save(self.class_dir / f"class_{len(existing) + i + j:05d}.png")

        del pipe
        torch.cuda.empty_cache()
        return sorted(self.class_dir.glob("*.png"))

    def compute_step_with_prior(
        self,
        batch_instance: dict,
        batch_class: dict,
    ) -> torch.Tensor:
        loss_inst = self._forward_pass(batch_instance)
        loss_prior = self._forward_pass(batch_class)
        return loss_inst + self.prior_loss_weight * loss_prior

    def _forward_pass(self, batch: dict) -> torch.Tensor:
        with torch.no_grad():
            latents = self.vae.encode(
                batch["pixel_values"].to(dtype=self.vae.dtype)
            ).latent_dist.sample() * self.vae.config.scaling_factor

        noise = torch.randn_like(latents)
        bsz = latents.shape[0]
        timesteps = torch.randint(
            0, self.noise_scheduler.config.num_train_timesteps,
            (bsz,), device=latents.device,
        ).long()
        noisy = self.noise_scheduler.add_noise(latents, noise, timesteps)
        target = (
            self.noise_scheduler.get_velocity(latents, noise, timesteps)
            if self.cfg.prediction_type == "v_prediction"
            else noise
        )

        if self.is_sdxl:
            embeds, pooled = self.encode_prompt_sdxl([""] * bsz)
            time_ids = torch.zeros(bsz, 6, device=latents.device, dtype=embeds.dtype)
            time_ids[:, 0] = time_ids[:, 1] = time_ids[:, 4] = time_ids[:, 5] = 1024
            added = {"text_embeds": pooled, "time_ids": time_ids}
        else:
            input_ids = batch.get("input_ids_one", torch.zeros(bsz, 77, dtype=torch.long, device=latents.device))
            with torch.no_grad():
                embeds = self.text_encoder_one(input_ids.to(self.accelerator.device))[0]
            added = None

        pred = self.unet(noisy, timesteps, embeds, added_cond_kwargs=added).sample
        return self.compute_loss(pred, target, timesteps)
