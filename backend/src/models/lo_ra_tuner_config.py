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
class LoRATunerConfig:
    # Model
    base_model_path: str = "OnomaAIResearch/Illustrious-XL-v2.0"
    prediction_type: str = "epsilon"        # 'epsilon' or 'v_prediction'
    zero_terminal_snr: bool = False         # True for NoobAI-XL Vpred
    clip_skip: int = 1                      # 1 for Illustrious/NoobAI (not 2!)

    # Adapter
    method: str = "peft"                    # 'peft' or 'lycoris'
    rank: int = 16
    alpha: Optional[int] = None            # defaults to rank
    use_dora: bool = False
    use_rslora: bool = False
    lycoris_algo: str = "lora"             # 'lora','locon','loha','lokr','dylora'
    lycoris_conv_dim: int = 8
    lycoris_conv_alpha: int = 4

    # Text encoder training
    train_text_encoder_one: bool = False
    train_text_encoder_two: bool = False
    te_lr_scale: float = 0.5

    # Training
    resolution: int = 1024
    train_batch_size: int = 1
    gradient_accumulation_steps: int = 1
    gradient_checkpointing: bool = True
    mixed_precision: str = "bf16"          # 'no','fp16','bf16'
    max_train_steps: Optional[int] = 2000
    max_train_epochs: Optional[int] = None

    # Loss
    snr_gamma: Optional[float] = 5.0       # None disables Min-SNR; 1.0 for v-pred
    noise_offset: float = 0.0

    # Optimizer
    optimizer_type: str = "adamw8bit"      # 'adamw','adamw8bit','prodigy','adafactor','lion'
    unet_lr: float = 1e-4
    lr_scheduler: str = "cosine_with_restarts"
    lr_warmup_steps: int = 100
    lr_num_cycles: int = 1
    weight_decay: float = 1e-2

    # EMA
    use_ema: bool = False
    ema_decay: float = 0.9999

    # Output
    output_dir: str = "output_lora"
    save_every_n_epochs: int = 1
    save_precision: str = "bf16"

    # Validation
    validation_prompts: list[str] = field(default_factory=list)
    validation_seed: int = 42

    # Logging
    use_wandb: bool = False
    wandb_project: str = "anime-diffusion"
    use_tensorboard: bool = True

# ===========================================================================
# LoRATunerV2
# ===========================================================================

# ===========================================================================
# DreamBoothTuner
# ===========================================================================
