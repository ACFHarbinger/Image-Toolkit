import os
import torch
from diffusers import StableDiffusion3Pipeline
from PIL import Image

class SD3Wrapper:
    is_cancelled = False

    @staticmethod
    def cancel_process():
        SD3Wrapper.is_cancelled = True

    @staticmethod
    def generate_image(
        prompt: str,
        model_path: str,
        output_path: str,
        width: int = 1024,
        height: int = 1024,
        steps: int = 28,
        guidance_scale: float = 7.0,
        batch_size: int = 1,
        controlnet_path: str = None,
        controlnet_image_path: str = None,
    ):
        SD3Wrapper.is_cancelled = False
        print(f"Loading SD3 model from {model_path}...")
        
        try:
            # Assuming model_path is a huggingface repo or finding logic for local files needs to be added similar to LoRATuner if needed.
            # For now, simplest implementation for SD3.
            
            if model_path.endswith(".safetensors"):
                pipe = StableDiffusion3Pipeline.from_single_file(
                    model_path,
                    torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                )
            else:
                pipe = StableDiffusion3Pipeline.from_pretrained(
                    model_path,
                    torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                )

            if torch.cuda.is_available():
                pipe.enable_model_cpu_offload()
            
            # TODO: Add ControlNet support if requested/needed (pipeline might need to be StableDiffusion3ControlNetPipeline)
            
            print(f"Generating {batch_size} image(s)...")
            
            images = pipe(
                prompt=prompt,
                negative_prompt="", # SD3 often doesn't need negative prompt or uses different mechanism
                num_inference_steps=steps,
                guidance_scale=guidance_scale,
                width=width,
                height=height,
                num_images_per_prompt=batch_size,
            ).images
            
            base_name, ext = os.path.splitext(output_path)
            for i, image in enumerate(images):
                if SD3Wrapper.is_cancelled:
                    print("SD3 Generation Cancelled.")
                    return
                file_path = f"{base_name}_{i+1}{ext}" if batch_size > 1 else output_path
                image.save(file_path)
                print(f"Saved SD3 image: {file_path}")

        except Exception as e:
            print(f"SD3 Generation Error: {e}")
            raise e
