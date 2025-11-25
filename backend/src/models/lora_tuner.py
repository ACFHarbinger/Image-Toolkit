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
    DPMSolverMultistepScheduler
)
from transformers import CLIPTextModel, CLIPTokenizer
from peft import LoraConfig, get_peft_model, PeftModel
from torch.utils.data import Dataset, DataLoader
from tqdm.auto import tqdm


class LoRATuner:
    def __init__(self, model_id="stablediffusionapi/anything-v5", output_dir="output_lora"):
        """
        Initialize the tuner with the base Anything V5 model.
        """
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

        # 1. Initialize Accelerator (Handles device placement & mixed precision)
        self.accelerator = Accelerator(
            gradient_accumulation_steps=1,
            mixed_precision="fp16"  # Use 'no' if you don't have a GPU
        )
        
        print(f"Loading base model: {model_id}...")
        
        # 2. Load Tokenizer & Encoders
        # We generally freeze these and only train the UNet's new LoRA layers
        self.tokenizer = CLIPTokenizer.from_pretrained(model_id, subfolder="tokenizer")
        self.text_encoder = CLIPTextModel.from_pretrained(model_id, subfolder="text_encoder")
        self.vae = AutoencoderKL.from_pretrained(model_id, subfolder="vae")
        self.unet = UNet2DConditionModel.from_pretrained(model_id, subfolder="unet")
        self.noise_scheduler = DDPMScheduler.from_pretrained(model_id, subfolder="scheduler")

        # Freeze base models to save memory
        self.text_encoder.requires_grad_(False)
        self.vae.requires_grad_(False)
        self.unet.requires_grad_(False)

        # Move to device (Accelerator handles this automatically later for the trained model)
        self.text_encoder.to(self.accelerator.device)
        self.vae.to(self.accelerator.device)

    def configure_lora(self, rank=4, alpha=32):
        """
        Injects LoRA adapters into the UNet.
        """
        print(f"Configuring LoRA (Rank: {rank}, Alpha: {alpha})...")
        
        lora_config = LoraConfig(
            r=rank,
            lora_alpha=alpha,
            init_lora_weights="gaussian",
            target_modules=["to_k", "to_q", "to_v", "to_out.0"], # Standard targets for SD
        )
        
        # Wrap the UNet with LoRA
        self.unet = get_peft_model(self.unet, lora_config)
        self.unet.print_trainable_parameters()

    def create_dataloader(self, data_dir, instance_prompt, resolution=512, batch_size=1):
        """
        Creates a DataLoader for a folder of images.
        Assumes all images in data_dir are training targets for 'instance_prompt'.
        """
        class SimpleImageDataset(Dataset):
            def __init__(self, root_dir, tokenizer, size=512):
                self.root_dir = root_dir
                self.image_paths = [os.path.join(root_dir, f) for f in os.listdir(root_dir) 
                                    if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
                self.tokenizer = tokenizer
                self.size = size
                self.instance_prompt = instance_prompt

                self.transforms = transforms.Compose([
                    transforms.Resize(size, interpolation=transforms.InterpolationMode.BILINEAR),
                    transforms.CenterCrop(size),
                    transforms.ToTensor(),
                    transforms.Normalize([0.5], [0.5]), # Normalize to [-1, 1]
                ])

            def __len__(self):
                return len(self.image_paths)

            def __getitem__(self, idx):
                img_path = self.image_paths[idx]
                image = Image.open(img_path).convert("RGB")
                
                # Preprocess Image
                pixel_values = self.transforms(image)
                
                # Tokenize Prompt
                input_ids = self.tokenizer(
                    self.instance_prompt,
                    padding="max_length",
                    truncation=True,
                    max_length=self.tokenizer.model_max_length,
                    return_tensors="pt",
                ).input_ids[0]

                return {"pixel_values": pixel_values, "input_ids": input_ids}

        dataset = SimpleImageDataset(data_dir, self.tokenizer, size=resolution)
        
        return DataLoader(
            dataset, 
            batch_size=batch_size, 
            shuffle=True, 
            num_workers=0 # Set to 1 or 2 if on Linux
        )

    def train(self, data_dir, instance_prompt, epochs=1, learning_rate=1e-4, batch_size=1):
        """
        Main training loop.
        """
        dataloader = self.create_dataloader(data_dir, instance_prompt, batch_size=batch_size)
        
        # Optimizer
        optimizer = torch.optim.AdamW(
            self.unet.parameters(),
            lr=learning_rate,
            betas=(0.9, 0.999),
            weight_decay=1e-2,
            eps=1e-08,
        )

        # Prepare everything with Accelerator
        self.unet, optimizer, dataloader = self.accelerator.prepare(
            self.unet, optimizer, dataloader
        )

        print("Starting training...")
        global_step = 0
        
        for epoch in range(epochs):
            self.unet.train()
            progress_bar = tqdm(total=len(dataloader), disable=not self.accelerator.is_local_main_process)
            progress_bar.set_description(f"Epoch {epoch}")

            for step, batch in enumerate(dataloader):
                # 1. Convert images to latents
                # The VAE expects inputs in float32, but we might be in mixed precision context.
                # We disable gradient calculation for VAE encoding.
                with torch.no_grad():
                    latents = self.vae.encode(batch["pixel_values"].to(dtype=self.text_encoder.dtype)).latent_dist.sample()
                    latents = latents * self.vae.config.scaling_factor

                # 2. Sample noise
                noise = torch.randn_like(latents)
                bsz = latents.shape[0]
                timesteps = torch.randint(0, self.noise_scheduler.config.num_train_timesteps, (bsz,), device=latents.device)
                timesteps = timesteps.long()

                # 3. Add noise to latents (Forward Diffusion)
                noisy_latents = self.noise_scheduler.add_noise(latents, noise, timesteps)

                # 4. Get text embeddings
                with torch.no_grad():
                    encoder_hidden_states = self.text_encoder(batch["input_ids"])[0]

                # 5. Predict noise (The Model Prediction)
                model_pred = self.unet(noisy_latents, timesteps, encoder_hidden_states).sample

                # 6. Calculate Loss (MSE between actual noise and predicted noise)
                loss = F.mse_loss(model_pred.float(), noise.float(), reduction="mean")

                # 7. Backpropagate
                self.accelerator.backward(loss)
                optimizer.step()
                optimizer.zero_grad()

                progress_bar.update(1)
                global_step += 1
                logs = {"loss": loss.detach().item()}
                progress_bar.set_postfix(**logs)

        # Save the LoRA adapter
        print("Training finished. Saving model...")
        self.unet = self.accelerator.unwrap_model(self.unet)
        self.unet.save_pretrained(self.output_dir)
        print(f"LoRA weights saved to {self.output_dir}")

    @staticmethod
    def generate_anime_image(
        prompt, 
        negative_prompt=None, 
        model_id="stablediffusionapi/anything-v5", 
        output_filename="anime_output.png",
        steps=25,
        guidance_scale=7.0,
        lora_path=None
    ):
        """
        Generates an anime-style image using the Anything V model.
        Can be called without instantiating the class.
        """
        
        print(f"Loading model: {model_id}...")
        
        # 1. Load the Pipeline
        # We use torch.float16 to reduce VRAM usage (requires a GPU)
        try:
            pipe = StableDiffusionPipeline.from_pretrained(
                model_id, 
                torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32
            )
        except Exception as e:
            print(f"Error loading model from Hub: {e}")
            print("Tip: Ensure you have an internet connection and the model ID is correct.")
            return

        # 2. Configure the Scheduler (Sampler)
        # DPM++ 2M Karras is highly recommended for anime models like Anything V
        pipe.scheduler = DPMSolverMultistepScheduler.from_config(
            pipe.scheduler.config, 
            use_karras_sigmas=True
        )

        # 3. Move to GPU (CUDA)
        if torch.cuda.is_available():
            pipe = pipe.to("cuda")
            print("Using CUDA (GPU).")
        else:
            print("CUDA not found. Running on CPU (this will be very slow).")

        # 4. Load LoRA (if provided)
        if lora_path and os.path.exists(lora_path):
            print(f"Loading LoRA weights from {lora_path}...")
            try:
                pipe.load_lora_weights(lora_path)
            except Exception as e:
                print(f"Warning: Failed to load LoRA from {lora_path}. Error: {e}")

        # 5. Define Prompts
        # "Masterpiece, best quality" are standard "magic tags" for high-quality anime gen.
        full_prompt = f"masterpiece, best quality, {prompt}"
        
        # Standard negative prompt for Anything V
        default_negative = (
            "lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, "
            "fewer digits, cropped, worst quality, low quality, normal quality, "
            "jpeg artifacts, signature, watermark, username, blurry, artist name"
        )
        
        use_negative = negative_prompt if negative_prompt else default_negative

        print(f"Generating image for: '{prompt}'...")

        # 6. Run Generation
        image = pipe(
            full_prompt,
            negative_prompt=use_negative,
            width=512,
            height=768, # Portrait aspect ratio works well for characters
            num_inference_steps=steps,
            guidance_scale=guidance_scale
        ).images[0]

        # 7. Save Image
        image.save(output_filename)
        print(f"Image saved successfully to {output_filename}")



if __name__ == "__main__":
    # --- CONFIGURATION ---
    DATASET_FOLDER = "./my_training_images"
    PROMPT = "1girl, style of my_custom_character"
    
    # Create dummy data if missing
    if not os.path.exists(DATASET_FOLDER):
        os.makedirs(DATASET_FOLDER)
        Image.new('RGB', (512, 512), color='red').save(os.path.join(DATASET_FOLDER, "dummy.png"))

    # Example Training
    # tuner = LoRATuner()
    # tuner.configure_lora(rank=4, alpha=32)
    # tuner.train(DATASET_FOLDER, PROMPT, epochs=1)
    
    # Example Generation (Static Method)
    LoRATuner.generate_anime_image("1girl, blue hair")