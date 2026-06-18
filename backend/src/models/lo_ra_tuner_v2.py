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

# --- Relocated Nested Imports ---
from peft.utils import get_peft_model_state_dict
import safetensors.torch as sf
# --------------------------------


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
class LoRATunerV2:
    """
    Extended LoRA trainer supporting LyCORIS, DoRA, rsLoRA, dual-TE training,
    Min-SNR-γ loss (ε and v-prediction), multiple optimizer backends, and EMA.
    """

    def __init__(self, cfg: LoRATunerConfig):
        self.cfg = cfg
        os.makedirs(cfg.output_dir, exist_ok=True)

        self.accelerator = Accelerator(
            gradient_accumulation_steps=cfg.gradient_accumulation_steps,
            mixed_precision=cfg.mixed_precision,
        )

        print(f"[LoRATunerV2] Loading base model: {cfg.base_model_path}")
        self.is_sdxl = self._detect_sdxl(cfg.base_model_path)
        self._load_components()
        self._freeze_base()

        self.lycoris_net = None
        self.ema = None
        self._param_groups: list[dict] = []

    # ------------------------------------------------------------------
    # Model loading
    # ------------------------------------------------------------------
    def _detect_sdxl(self, model_id: str) -> bool:
        kw = ("xl", "animagine", "illustrious", "noobai", "pony")
        return any(k in model_id.lower() for k in kw)

    def _load_components(self):
        cfg = self.cfg
        self.tokenizer_one = CLIPTokenizer.from_pretrained(
            cfg.base_model_path, subfolder="tokenizer"
        )
        self.text_encoder_one = CLIPTextModel.from_pretrained(
            cfg.base_model_path, subfolder="text_encoder"
        )
        if self.is_sdxl:
            self.tokenizer_two = CLIPTokenizer.from_pretrained(
                cfg.base_model_path, subfolder="tokenizer_2"
            )
            self.text_encoder_two = CLIPTextModelWithProjection.from_pretrained(
                cfg.base_model_path, subfolder="text_encoder_2"
            )
        else:
            self.tokenizer_two = None
            self.text_encoder_two = None

        self.vae = AutoencoderKL.from_pretrained(cfg.base_model_path, subfolder="vae")
        self.unet = UNet2DConditionModel.from_pretrained(
            cfg.base_model_path, subfolder="unet"
        )

        # Scheduler: handle v-prediction
        self.noise_scheduler = DDPMScheduler.from_pretrained(
            cfg.base_model_path, subfolder="scheduler"
        )
        if cfg.prediction_type == "v_prediction":
            self.noise_scheduler.config.prediction_type = "v_prediction"
            if cfg.zero_terminal_snr:
                self.noise_scheduler.config.rescale_betas_zero_snr = True

    def _freeze_base(self):
        self.vae.requires_grad_(False)
        self.text_encoder_one.requires_grad_(False)
        self.unet.requires_grad_(False)
        if self.text_encoder_two is not None:
            self.text_encoder_two.requires_grad_(False)

        dev = self.accelerator.device
        self.vae.to(dev)
        self.text_encoder_one.to(dev)
        if self.text_encoder_two is not None:
            self.text_encoder_two.to(dev)

        if self.cfg.gradient_checkpointing:
            self.unet.enable_gradient_checkpointing()

    # ------------------------------------------------------------------
    # Adapter construction
    # ------------------------------------------------------------------
    def build_adapters(self):
        cfg = self.cfg
        alpha = cfg.alpha if cfg.alpha is not None else cfg.rank

        if cfg.method == "peft":
            lora_cfg = LoraConfig(
                r=cfg.rank,
                lora_alpha=alpha,
                target_modules=list(SDXL_ATTN_TARGETS),
                use_dora=cfg.use_dora,
                use_rslora=cfg.use_rslora,
                init_lora_weights="gaussian",
                bias="none",
            )
            self.unet = get_peft_model(self.unet, lora_cfg)
            self.unet.print_trainable_parameters()

            if cfg.train_text_encoder_one:
                te_cfg = LoraConfig(
                    r=max(cfg.rank // 2, 1),
                    lora_alpha=max(alpha // 2, 1),
                    target_modules=list(TE_ATTN_TARGETS),
                    use_dora=cfg.use_dora,
                    use_rslora=cfg.use_rslora,
                    init_lora_weights="gaussian",
                    bias="none",
                )
                self.text_encoder_one = get_peft_model(self.text_encoder_one, te_cfg)
                self.text_encoder_one.requires_grad_(True)

            if cfg.train_text_encoder_two and self.text_encoder_two is not None:
                self.text_encoder_two = get_peft_model(self.text_encoder_two, te_cfg)
                self.text_encoder_two.requires_grad_(True)

        elif cfg.method == "lycoris":
            if not _LYCORIS_OK:
                raise ImportError("lycoris-lora is required (pip install lycoris-lora)")
            te_list = []
            if cfg.train_text_encoder_one and self.text_encoder_one is not None:
                te_list.append(self.text_encoder_one)
            if cfg.train_text_encoder_two and self.text_encoder_two is not None:
                te_list.append(self.text_encoder_two)

            self.lycoris_net = lycoris_kohya.create_network(
                multiplier=1.0,
                network_dim=cfg.rank,
                network_alpha=alpha,
                vae=self.vae,
                text_encoder=te_list if te_list else [self.text_encoder_one],
                unet=self.unet,
                neuron_dropout=0.0,
                algo=cfg.lycoris_algo,
                linear_dim=cfg.rank,
                linear_alpha=alpha,
                conv_dim=cfg.lycoris_conv_dim,
                conv_alpha=cfg.lycoris_conv_alpha,
                dropout=0.0,
                use_tucker=False,
            )
            self.lycoris_net.apply_to(
                te_list or None,
                self.unet,
                apply_text_encoder=bool(te_list),
                apply_unet=True,
            )
        else:
            raise ValueError(f"Unknown adapter method: {cfg.method!r}")

        # Collect parameter groups with per-component LRs
        unet_params = [p for p in self.unet.parameters() if p.requires_grad]
        te1_params = [p for p in self.text_encoder_one.parameters() if p.requires_grad]
        te2_params = (
            [p for p in self.text_encoder_two.parameters() if p.requires_grad]
            if self.text_encoder_two is not None
            else []
        )
        self._param_groups = [{"params": unet_params, "lr": cfg.unet_lr}]
        if te1_params:
            self._param_groups.append({"params": te1_params, "lr": cfg.unet_lr * cfg.te_lr_scale})
        if te2_params:
            self._param_groups.append({"params": te2_params, "lr": cfg.unet_lr * cfg.te_lr_scale * 0.5})

    # ------------------------------------------------------------------
    # Optimizer
    # ------------------------------------------------------------------
    def build_optimizer(self) -> torch.optim.Optimizer:
        params = self._param_groups
        name = self.cfg.optimizer_type.lower()

        if name == "adamw":
            return torch.optim.AdamW(params, weight_decay=self.cfg.weight_decay,
                                     betas=(0.9, 0.999), eps=1e-8)
        if name == "adamw8bit":
            if not _BNB_OK:
                raise ImportError("bitsandbytes is required for adamw8bit")
            return bnb.optim.AdamW8bit(params, weight_decay=self.cfg.weight_decay,
                                       betas=(0.9, 0.999), eps=1e-8)
        if name == "lion":
            if not _BNB_OK:
                raise ImportError("bitsandbytes is required for Lion8bit")
            return bnb.optim.Lion8bit(params, weight_decay=self.cfg.weight_decay,
                                      betas=(0.95, 0.98))
        if name == "prodigy":
            if not _PRODIGY_OK:
                raise ImportError("prodigyopt is required (pip install prodigyopt)")
            for g in params:
                g["lr"] = 1.0
            return Prodigy(
                params, lr=1.0, betas=(0.9, 0.99), beta3=None,
                weight_decay=self.cfg.weight_decay, decouple=True,
                use_bias_correction=True, safeguard_warmup=True, d_coef=2.0,
            )
        if name == "adafactor":
            if not _ADAFACTOR_OK:
                raise ImportError("transformers is required for Adafactor")
            return Adafactor(
                params, scale_parameter=False, relative_step=False,
                warmup_init=False, weight_decay=1e-3,
            )
        raise ValueError(f"Unknown optimizer: {name!r}")

    # ------------------------------------------------------------------
    # LR scheduler
    # ------------------------------------------------------------------
    def build_scheduler(self, optimizer, num_total_steps: int):
        return get_scheduler(
            self.cfg.lr_scheduler,
            optimizer=optimizer,
            num_warmup_steps=self.cfg.lr_warmup_steps,
            num_training_steps=num_total_steps,
            num_cycles=self.cfg.lr_num_cycles,
        )

    # ------------------------------------------------------------------
    # Loss computation
    # ------------------------------------------------------------------
    def compute_loss(
        self,
        noise_pred: torch.Tensor,
        target: torch.Tensor,
        timesteps: torch.Tensor,
    ) -> torch.Tensor:
        cfg = self.cfg
        if cfg.snr_gamma is None:
            return F.mse_loss(noise_pred.float(), target.float(), reduction="mean")

        snr = compute_snr(self.noise_scheduler, timesteps)
        snr_clamped = torch.stack(
            [snr, cfg.snr_gamma * torch.ones_like(snr)], dim=1
        ).min(dim=1)[0]

        if cfg.prediction_type == "v_prediction":
            weights = (snr_clamped + 1.0) / (snr + 1.0)
        else:
            weights = snr_clamped / snr

        loss = F.mse_loss(noise_pred.float(), target.float(), reduction="none")
        loss = loss.mean(dim=list(range(1, loss.dim()))) * weights
        return loss.mean()

    # ------------------------------------------------------------------
    # SDXL encode prompts
    # ------------------------------------------------------------------
    def encode_prompt_sdxl(self, prompts: list[str]):
        text_inputs1 = self.tokenizer_one(
            prompts, padding="max_length",
            max_length=self.tokenizer_one.model_max_length,
            truncation=True, return_tensors="pt",
        )
        with torch.no_grad():
            embeds1 = self.text_encoder_one(
                text_inputs1.input_ids.to(self.accelerator.device)
            )[0]

        text_inputs2 = self.tokenizer_two(
            prompts, padding="max_length",
            max_length=self.tokenizer_two.model_max_length,
            truncation=True, return_tensors="pt",
        )
        with torch.no_grad():
            out2 = self.text_encoder_two(
                text_inputs2.input_ids.to(self.accelerator.device),
                output_hidden_states=True,
            )
        return torch.cat([embeds1, out2.hidden_states[-2]], dim=-1), out2.text_embeds

    # ------------------------------------------------------------------
    # Training loop
    # ------------------------------------------------------------------
    def train(self, dataloader: DataLoader, diagnostics=None):
        cfg = self.cfg
        self.build_adapters()
        optimizer = self.build_optimizer()

        num_update_steps_per_epoch = max(
            len(dataloader) // cfg.gradient_accumulation_steps, 1
        )
        if cfg.max_train_epochs is not None:
            total_steps = num_update_steps_per_epoch * cfg.max_train_epochs
        else:
            total_steps = cfg.max_train_steps or 2000
        epochs = max(total_steps // num_update_steps_per_epoch, 1)

        lr_scheduler = self.build_scheduler(optimizer, total_steps)

        # EMA
        if cfg.use_ema:
            ema_params = [p for p in self.unet.parameters() if p.requires_grad]
            self.ema = EMAModel(
                parameters=ema_params, decay=cfg.ema_decay,
                use_ema_warmup=True, inv_gamma=1.0, power=2 / 3,
                model_cls=UNet2DConditionModel, model_config=self.unet.config,
            )

        # Accelerator prepare
        trainables = [self.unet, optimizer, dataloader, lr_scheduler]
        prepared = self.accelerator.prepare(*trainables)
        self.unet, optimizer, dataloader, lr_scheduler = prepared

        global_step = 0
        print(f"[LoRATunerV2] Training: {epochs} epochs × {num_update_steps_per_epoch} steps = {total_steps} total")

        for epoch in range(epochs):
            self.unet.train()
            if cfg.train_text_encoder_one:
                self.text_encoder_one.train()

            prog = tqdm(dataloader, desc=f"Epoch {epoch}", disable=not self.accelerator.is_local_main_process)

            for batch in prog:
                with self.accelerator.accumulate(self.unet):
                    # Encode images to latents
                    with torch.no_grad():
                        px = batch["pixel_values"].to(dtype=self.vae.dtype)
                        latents = self.vae.encode(px).latent_dist.sample()
                        latents = latents * self.vae.config.scaling_factor

                    noise = torch.randn_like(latents)
                    if cfg.noise_offset > 0:
                        noise += cfg.noise_offset * torch.randn(
                            latents.shape[0], latents.shape[1], 1, 1, device=latents.device
                        )
                    bsz = latents.shape[0]
                    timesteps = torch.randint(
                        0, self.noise_scheduler.config.num_train_timesteps,
                        (bsz,), device=latents.device,
                    ).long()
                    noisy_latents = self.noise_scheduler.add_noise(latents, noise, timesteps)

                    # Target for v-prediction
                    if cfg.prediction_type == "v_prediction":
                        target = self.noise_scheduler.get_velocity(latents, noise, timesteps)
                    else:
                        target = noise

                    # Text conditioning
                    added_cond_kwargs = None
                    if self.is_sdxl:
                        prompt_embeds, pooled = self.encode_prompt_sdxl(
                            batch.get("prompt", [""] * bsz)
                            if "prompt" in batch
                            else self._ids_to_prompts(batch.get("input_ids_one"))
                        )
                        # SDXL micro-conditioning
                        orig = batch.get("original_size", torch.tensor([[1024, 1024]] * bsz)).to(latents.device)
                        tgt = batch.get("target_size", torch.tensor([[1024, 1024]] * bsz)).to(latents.device)
                        ctl = batch.get("crop_top_left", torch.zeros(bsz, 2)).to(latents.device)
                        time_ids = torch.cat([orig, ctl, tgt], dim=-1).to(dtype=prompt_embeds.dtype)
                        added_cond_kwargs = {"text_embeds": pooled, "time_ids": time_ids}
                        encoder_hidden_states = prompt_embeds
                    else:
                        input_ids = batch["input_ids_one"].to(self.accelerator.device)
                        with torch.no_grad():
                            encoder_hidden_states = self.text_encoder_one(input_ids)[0]

                    # UNet forward
                    model_pred = self.unet(
                        noisy_latents, timesteps, encoder_hidden_states,
                        added_cond_kwargs=added_cond_kwargs,
                    ).sample

                    loss = self.compute_loss(model_pred, target, timesteps)
                    self.accelerator.backward(loss)
                    optimizer.step()
                    lr_scheduler.step()
                    optimizer.zero_grad()

                    if cfg.use_ema and self.ema is not None:
                        self.ema.step(p for p in self.unet.parameters() if p.requires_grad)

                global_step += 1
                prog.set_postfix({"loss": loss.detach().item(), "step": global_step})

                if diagnostics is not None:
                    diagnostics.log_step(global_step, loss=loss.detach().item())

                if global_step >= total_steps:
                    break

            # Save checkpoint every N epochs
            if (epoch + 1) % cfg.save_every_n_epochs == 0:
                self._save_checkpoint(epoch)

            if global_step >= total_steps:
                break

        self._save_final()
        print(f"[LoRATunerV2] Training complete. Output: {cfg.output_dir}")

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def _save_checkpoint(self, epoch: int):
        path = Path(self.cfg.output_dir) / f"checkpoint-epoch{epoch:04d}"
        path.mkdir(exist_ok=True)
        unwrapped = self.accelerator.unwrap_model(self.unet)
        unwrapped.save_pretrained(str(path))
        print(f"  Checkpoint saved: {path}")

    def _save_final(self):
        unwrapped = self.accelerator.unwrap_model(self.unet)
        # Save PEFT / LyCORIS adapter weights as safetensors
        if self.lycoris_net is not None:
            out = Path(self.cfg.output_dir) / "lycoris_net.safetensors"
            self.lycoris_net.save_weights(str(out), dtype=torch.bfloat16)
        else:
            # relocated: from peft.utils import get_peft_model_state_dict
            # relocated: import safetensors.torch as sf
            state = get_peft_model_state_dict(unwrapped)
            sf.save_file(state, Path(self.cfg.output_dir) / "lora_weights.safetensors")

    def _ids_to_prompts(self, input_ids) -> list[str]:
        if input_ids is None:
            return [""]
        return self.tokenizer_one.batch_decode(input_ids, skip_special_tokens=True)

    # ------------------------------------------------------------------
    # Inference helper (wraps generate_anime_image)
    # ------------------------------------------------------------------
    def generate(
        self,
        prompt: str,
        negative_prompt: str = "",
        lora_path: Optional[str] = None,
        steps: int = 30,
        cfg_scale: float = 6.0,
        seed: Optional[int] = None,
        width: int = 832,
        height: int = 1216,
    ) -> Image.Image:
        PipeClass = StableDiffusionXLPipeline if self.is_sdxl else StableDiffusionPipeline
        pipe = PipeClass.from_pretrained(
            self.cfg.base_model_path,
            torch_dtype=torch.bfloat16,
            safety_checker=None,
            requires_safety_checker=False,
        )
        if self.cfg.prediction_type == "v_prediction":
            pipe.scheduler = DPMSolverMultistepScheduler.from_config(
                pipe.scheduler.config,
                prediction_type="v_prediction",
                rescale_betas_zero_snr=True,
            )
        else:
            pipe.scheduler = DPMSolverMultistepScheduler.from_config(
                pipe.scheduler.config, use_karras_sigmas=True
            )
        if torch.cuda.is_available():
            pipe = pipe.to("cuda")
        if lora_path and os.path.exists(lora_path):
            pipe.load_lora_weights(lora_path)
        gen = torch.Generator("cuda").manual_seed(
            seed if seed is not None else random.randint(0, 2**31 - 1)
        )
        return pipe(
            prompt=prompt,
            negative_prompt=negative_prompt,
            num_inference_steps=steps,
            guidance_scale=cfg_scale,
            width=width,
            height=height,
            generator=gen,
        ).images[0]


# ===========================================================================
# DreamBoothTuner
# ===========================================================================
