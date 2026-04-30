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


class LoRATuner:
    # --- Cancellation Flag ---
    is_cancelled = False

    @staticmethod
    def cancel_process():
        LoRATuner.is_cancelled = True
        print("[CANCELLED] LoRA process cancellation requested.")

    def __init__(
        self, model_id="OnomaAIResearch/Illustrious-XL-v2.0", output_dir="output_lora"
    ):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        self.accelerator = Accelerator(
            gradient_accumulation_steps=1, mixed_precision="bf16"
        )
        LoRATuner.is_cancelled = False

        # --- NEW: Training Guardrail ---
        if os.path.exists(model_id) and model_id.lower().endswith(
            (".safetensors", ".ckpt")
        ):
            raise ValueError(
                f"LoRA training requires a Diffusers-format folder structure (e.g., a Hugging Face repository ID), "
                f"not a single file: {model_id}. Please select a HF model for training."
            )

        print(f"Loading base model: {model_id}...")

        # Detect SDXL Architecture
        self.is_sdxl = "xl" in model_id.lower() or "animagine" in model_id.lower()
        if self.is_sdxl:
            print(
                "Mode: SDXL (Animagine/Pony/etc) detected. Enabling dual-encoder training."
            )
        else:
            print("Mode: SD1.5/2.1 (Standard) detected.")

        # 1. Load Tokenizers & Encoders
        self.tokenizer_one = CLIPTokenizer.from_pretrained(
            model_id, subfolder="tokenizer"
        )
        self.text_encoder_one = CLIPTextModel.from_pretrained(
            model_id, subfolder="text_encoder"
        )

        if self.is_sdxl:
            # SDXL needs a second set
            self.tokenizer_two = CLIPTokenizer.from_pretrained(
                model_id, subfolder="tokenizer_2"
            )
            self.text_encoder_two = CLIPTextModelWithProjection.from_pretrained(
                model_id, subfolder="text_encoder_2"
            )
            self.text_encoder_two.requires_grad_(False)
            self.text_encoder_two.to(self.accelerator.device)

        # 2. Load VAE & UNet
        self.vae = AutoencoderKL.from_pretrained(model_id, subfolder="vae")
        self.unet = UNet2DConditionModel.from_pretrained(model_id, subfolder="unet")
        self.noise_scheduler = DDPMScheduler.from_pretrained(
            model_id, subfolder="scheduler"
        )

        self.text_encoder_one.requires_grad_(False)
        self.vae.requires_grad_(False)
        self.unet.requires_grad_(False)

        self.text_encoder_one.to(self.accelerator.device)
        self.vae.to(self.accelerator.device)

    def configure_lora(self, rank=4, alpha=32):
        print(f"Configuring LoRA (Rank: {rank}, Alpha: {alpha})...")
        # SDXL typically benefits from targeting more modules, but we keep it standard for stability
        target_modules = ["to_k", "to_q", "to_v", "to_out.0"]
        lora_config = LoraConfig(
            r=rank,
            lora_alpha=alpha,
            init_lora_weights="gaussian",
            target_modules=target_modules,
        )
        self.unet = get_peft_model(self.unet, lora_config)
        self.unet.print_trainable_parameters()

    def create_dataloader(
        self, data_dir, instance_prompt, resolution=512, batch_size=1, pruned_tags=None
    ):
        # Determine the tokenizer to use for the dataset class (primarily for length checks)
        main_tokenizer = self.tokenizer_one

        class SimpleImageDataset(Dataset):
            def __init__(self, root_dir, tokenizer, size=512, pruned_tags=None):
                self.root_dir = root_dir
                self.image_paths = []

                # Recursive search for images
                for root, _, files in os.walk(root_dir):
                    for f in files:
                        if f.lower().endswith((".png", ".jpg", ".jpeg")):
                            self.image_paths.append(os.path.join(root, f))

                if len(self.image_paths) == 0:
                    print(f"WARNING: No images found in {root_dir}")

                self.tokenizer = tokenizer
                self.size = size
                self.instance_prompt = instance_prompt
                self.pruned_tags = [t.strip().lower() for t in pruned_tags] if pruned_tags else []
                self.transforms = transforms.Compose(
                    [
                        transforms.Resize(
                            size, interpolation=transforms.InterpolationMode.BILINEAR
                        ),
                        transforms.CenterCrop(size),
                        transforms.ToTensor(),
                        transforms.Normalize([0.5], [0.5]),
                    ]
                )

            def __len__(self):
                return len(self.image_paths)

            def __getitem__(self, idx):
                img_path = self.image_paths[idx]
                image = Image.open(img_path).convert("RGB")
                pixel_values = self.transforms(image)

                # --- Handle Danbooru-style captions (.txt files) ---
                txt_path = os.path.splitext(img_path)[0] + ".txt"
                tags = []
                if os.path.exists(txt_path):
                    with open(txt_path, "r", encoding="utf-8") as f:
                        # Read and split tags by comma
                        content = f.read().strip()
                        tags = [t.strip() for t in content.split(",") if t.strip()]

                # Prune tags (e.g., remove intrinsic physical traits)
                filtered_tags = [t for t in tags if t.lower() not in self.pruned_tags]

                # Prepend the unique trigger word (instance_prompt)
                final_prompt = f"{self.instance_prompt}, {', '.join(filtered_tags)}" if filtered_tags else self.instance_prompt

                # We return the prompt string directly so we can process it
                # with dual tokenizers in the training loop if needed
                return {"pixel_values": pixel_values, "prompt": final_prompt}

        dataset = SimpleImageDataset(data_dir, main_tokenizer, size=resolution, pruned_tags=pruned_tags)
        if len(dataset) == 0:
            raise ValueError(f"No valid images (.png, .jpg, .jpeg) found in {data_dir}")

        return DataLoader(dataset, batch_size=batch_size, shuffle=True, num_workers=0)

    # --- SDXL Helper: Encode Prompts ---
    def encode_prompt_sdxl(self, prompts):
        # 1. Encode with Tokenizer 1
        text_inputs1 = self.tokenizer_one(
            prompts,
            padding="max_length",
            max_length=self.tokenizer_one.model_max_length,
            truncation=True,
            return_tensors="pt",
        )
        with torch.no_grad():
            prompt_embeds1 = self.text_encoder_one(
                text_inputs1.input_ids.to(self.accelerator.device)
            )[0]

        # 2. Encode with Tokenizer 2
        text_inputs2 = self.tokenizer_two(
            prompts,
            padding="max_length",
            max_length=self.tokenizer_two.model_max_length,
            truncation=True,
            return_tensors="pt",
        )
        with torch.no_grad():
            output2 = self.text_encoder_two(
                text_inputs2.input_ids.to(self.accelerator.device),
                output_hidden_states=True,
            )
            prompt_embeds2 = output2.hidden_states[-2]  # Penultimate layer
            pooled_prompt_embeds = (
                output2.text_embeds
            )  # Pooled outputs for "add_text_embeds"

        # 3. Concatenate
        prompt_embeds = torch.cat([prompt_embeds1, prompt_embeds2], dim=-1)

        return prompt_embeds, pooled_prompt_embeds

    def train(
        self, data_dir, instance_prompt, epochs=1, learning_rate=1e-4, batch_size=2, pruned_tags=None
    ):
        # SDXL usually trains at 1024, but we can respect the input resolution (likely 512 or 1024)
        # Note: If training SDXL at 512, results may be blurry unless adjusted.
        resolution = 1024 if self.is_sdxl else 512
        print(f"Training Resolution: {resolution}x{resolution}")

        # --- VRAM Optimization: Gradient Checkpointing ---
        if hasattr(self.unet, "enable_gradient_checkpointing"):
            print("Enabling gradient checkpointing for VRAM efficiency...")
            self.unet.enable_gradient_checkpointing()

        dataloader = self.create_dataloader(
            data_dir, instance_prompt, resolution=resolution, batch_size=batch_size, pruned_tags=pruned_tags
        )

        optimizer = torch.optim.AdamW(
            self.unet.parameters(),
            lr=learning_rate,
            betas=(0.9, 0.999),
            weight_decay=1e-2,
            eps=1e-08,
        )
        self.unet, optimizer, dataloader = self.accelerator.prepare(
            self.unet, optimizer, dataloader
        )

        print(f"Starting training with batch size {batch_size}...")

        for epoch in range(epochs):
            if self.is_cancelled:
                break

            self.unet.train()
            progress_bar = tqdm(
                total=len(dataloader),
                disable=not self.accelerator.is_local_main_process,
            )
            progress_bar.set_description(f"Epoch {epoch}")

            for step, batch in enumerate(dataloader):
                if self.is_cancelled:
                    progress_bar.close()
                    print("Training stopped by cancellation.")
                    return

                # 1. Convert Images to Latents
                with torch.no_grad():
                    latents = self.vae.encode(
                        batch["pixel_values"].to(dtype=self.text_encoder_one.dtype)
                    ).latent_dist.sample()
                    latents = latents * self.vae.config.scaling_factor

                # 2. Sample Noise
                noise = torch.randn_like(latents)
                bsz = latents.shape[0]
                timesteps = torch.randint(
                    0,
                    self.noise_scheduler.config.num_train_timesteps,
                    (bsz,),
                    device=latents.device,
                ).long()
                noisy_latents = self.noise_scheduler.add_noise(
                    latents, noise, timesteps
                )

                # 3. Get Text Embeddings & Conditions
                added_cond_kwargs = None

                if self.is_sdxl:
                    # SDXL Encoding (Dual)
                    prompt_embeds, pooled_embeds = self.encode_prompt_sdxl(
                        batch["prompt"]
                    )

                    # Create SDXL "Micro-Conditioning" (Time IDs)
                    # [original_h, original_w, crop_top, crop_left, target_h, target_w]
                    # We assume no cropping and standard resolution for simplicity
                    time_ids = torch.tensor(
                        [[resolution, resolution, 0, 0, resolution, resolution]],
                        device=self.accelerator.device,
                        dtype=prompt_embeds.dtype,
                    )
                    time_ids = time_ids.repeat(bsz, 1)

                    added_cond_kwargs = {
                        "text_embeds": pooled_embeds,
                        "time_ids": time_ids,
                    }
                    encoder_hidden_states = prompt_embeds
                else:
                    # SD1.5 Encoding (Single)
                    input_ids = self.tokenizer_one(
                        batch["prompt"],
                        padding="max_length",
                        max_length=self.tokenizer_one.model_max_length,
                        truncation=True,
                        return_tensors="pt",
                    ).input_ids.to(self.accelerator.device)

                    with torch.no_grad():
                        encoder_hidden_states = self.text_encoder_one(input_ids)[0]

                # 4. Prediction & Backprop
                # Pass added_cond_kwargs if it exists (SDXL), otherwise Diffusers ignores it for SD1.5 if not needed
                if added_cond_kwargs:
                    model_pred = self.unet(
                        noisy_latents,
                        timesteps,
                        encoder_hidden_states,
                        added_cond_kwargs=added_cond_kwargs,
                    ).sample
                else:
                    model_pred = self.unet(
                        noisy_latents, timesteps, encoder_hidden_states
                    ).sample

                loss = F.mse_loss(model_pred.float(), noise.float(), reduction="mean")

                self.accelerator.backward(loss)
                optimizer.step()
                optimizer.zero_grad()

                progress_bar.update(1)
                progress_bar.set_postfix({"loss": loss.detach().item()})

        print("Training finished. Saving model...")
        self.unet = self.accelerator.unwrap_model(self.unet)
        self.unet.save_pretrained(self.output_dir)

    # In backend/src/models/lora_diffusion.py

    # ... inside LoRATuner.generate_anime_image static method:

    @staticmethod
    def generate_anime_image(
        prompt,
        negative_prompt=None,
        model_id="stablediffusionapi/anything-v5",
        output_filename="anime_output.png",
        steps=25,
        guidance_scale=7.0,
        lora_path=None,
        batch_size=1,
    ):
        if LoRATuner.is_cancelled:
            return

        print(f"Loading model: {model_id}...")

        PipelineClass = StableDiffusionPipeline
        # Note: Added 'illustrious' to the SDXL detection logic
        if (
            "xl" in model_id.lower()
            or "animagine" in model_id.lower()
            or "illustrious" in model_id.lower()
        ):
            PipelineClass = StableDiffusionXLPipeline

        try:
            # 1. Handle the specific Illustrious Lumina single-file checkpoint
            if model_id == "OnomaAIResearch/Illustrious-Lumina-v0.03":
                # This checkpoint is known to be a single file requiring 'from_single_file'
                checkpoint_filename = (
                    "Illustrious_Lumina_2b_22100_ema_unified_fp32.safetensors"
                )

                print(f"Downloading single checkpoint file: {checkpoint_filename}...")

                # Download the single safetensors file from the repo
                downloaded_file_path = hf_hub_download(
                    repo_id=model_id, filename=checkpoint_filename
                )

                # Load using from_single_file, using the repo ID as the config source
                pipe = PipelineClass.from_single_file(
                    downloaded_file_path,
                    config=model_id,
                    torch_dtype=(
                        torch.float16 if torch.cuda.is_available() else torch.float32
                    ),
                    safety_checker=None,
                    requires_safety_checker=False,
                )

            # 2. Handle the specific Illustrious XL v2.0 single-file checkpoint (NEW FIX)
            elif model_id == "OnomaAIResearch/Illustrious-XL-v2.0":
                checkpoint_filename = "Illustrious-XL-v2.0.safetensors"  #

                print(f"Downloading single checkpoint file: {checkpoint_filename}...")
                downloaded_file_path = hf_hub_download(
                    repo_id=model_id, filename=checkpoint_filename
                )

                pipe = PipelineClass.from_single_file(
                    downloaded_file_path,
                    config=model_id,
                    torch_dtype=(
                        torch.float16 if torch.cuda.is_available() else torch.float32
                    ),
                    safety_checker=None,
                    requires_safety_checker=False,
                )

            # 3. Handle local single file (from previous fix)
            elif os.path.exists(model_id) and model_id.lower().endswith(
                (".safetensors", ".ckpt")
            ):
                print(f"Loading local single-file model: {model_id}...")
                pipe = PipelineClass.from_single_file(
                    model_id,
                    torch_dtype=(
                        torch.float16 if torch.cuda.is_available() else torch.float32
                    ),
                    safety_checker=None,
                    requires_safety_checker=False,
                )

            # 4. Standard Hugging Face multi-folder load (from_pretrained)
            else:
                print(f"Loading Hugging Face model (multi-folder): {model_id}...")
                pipe = PipelineClass.from_pretrained(
                    model_id,
                    torch_dtype=(
                        torch.float16 if torch.cuda.is_available() else torch.float32
                    ),
                    safety_checker=None,
                    requires_safety_checker=False,
                )

        except Exception as e:
            print(f"Error loading model: {e}")
            raise e

        # SDXL scheduler fix usually helps
        pipe.scheduler = DPMSolverMultistepScheduler.from_config(
            pipe.scheduler.config, use_karras_sigmas=True
        )

        if torch.cuda.is_available():
            pipe = pipe.to("cuda")

        if lora_path and os.path.exists(lora_path):
            try:
                print(f"Loading LoRA from {lora_path}")
                pipe.load_lora_weights(lora_path)
            except Exception as e:
                print(f"Failed to load LoRA: {e}")

        full_prompt = f"masterpiece, best quality, {prompt}"
        use_negative = (
            negative_prompt
            if negative_prompt
            else "lowres, bad anatomy, bad hands, text, error..."
        )

        print(f"Generating {batch_size} image(s)...")

        # Dimensions: SDXL likes 1024x1024, SD1.5 likes 512x768 (portrait)
        h = 1024 if PipelineClass == StableDiffusionXLPipeline else 768
        w = 832 if PipelineClass == StableDiffusionXLPipeline else 512

        results = pipe(
            full_prompt,
            negative_prompt=use_negative,
            width=w,
            height=h,
            num_inference_steps=steps,
            guidance_scale=guidance_scale,
            num_images_per_prompt=batch_size,
        ).images

        base_name, ext = os.path.splitext(output_filename)
        for i, image in enumerate(results):
            if LoRATuner.is_cancelled:
                return
            file_path = f"{base_name}_{i+1}{ext}" if batch_size > 1 else output_filename
            image.save(file_path)


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
            from peft.utils import get_peft_model_state_dict
            import safetensors.torch as sf
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
