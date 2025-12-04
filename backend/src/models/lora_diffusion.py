import os
import torch
import torch.nn.functional as F

from PIL import Image
from torchvision import transforms
from accelerate import Accelerator
from diffusers import (
    DDPMScheduler,
    AutoencoderKL,
    UNet2DConditionModel,
    StableDiffusionPipeline,
    StableDiffusionXLPipeline,
    DPMSolverMultistepScheduler,
)
from transformers import CLIPTextModel, CLIPTokenizer, CLIPTextModelWithProjection
from torch.utils.data import Dataset, DataLoader
from huggingface_hub import hf_hub_download
from peft import LoraConfig, get_peft_model
from tqdm.auto import tqdm


class LoRATuner:
    # --- Cancellation Flag ---
    is_cancelled = False

    @staticmethod
    def cancel_process():
        LoRATuner.is_cancelled = True
        print("[CANCELLED] LoRA process cancellation requested.")

    def __init__(
        self, model_id="stablediffusionapi/anything-v5", output_dir="output_lora"
    ):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        self.accelerator = Accelerator(
            gradient_accumulation_steps=1, mixed_precision="fp16"
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
        self, data_dir, instance_prompt, resolution=512, batch_size=1
    ):
        # Determine the tokenizer to use for the dataset class (primarily for length checks)
        main_tokenizer = self.tokenizer_one

        class SimpleImageDataset(Dataset):
            def __init__(self, root_dir, tokenizer, size=512):
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

                # We return the prompt string directly so we can process it
                # with dual tokenizers in the training loop if needed
                return {"pixel_values": pixel_values, "prompt": self.instance_prompt}

        dataset = SimpleImageDataset(data_dir, main_tokenizer, size=resolution)
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
        self, data_dir, instance_prompt, epochs=1, learning_rate=1e-4, batch_size=1
    ):
        # SDXL usually trains at 1024, but we can respect the input resolution (likely 512 or 1024)
        # Note: If training SDXL at 512, results may be blurry unless adjusted.
        resolution = 1024 if self.is_sdxl else 512
        print(f"Training Resolution: {resolution}x{resolution}")

        dataloader = self.create_dataloader(
            data_dir, instance_prompt, resolution=resolution, batch_size=batch_size
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
            print(f"Saved: {file_path}")
